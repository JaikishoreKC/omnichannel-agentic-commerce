from __future__ import annotations

import asyncio
import hashlib
from contextlib import suppress
from time import time

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from app.api.routes.admin_routes import router as admin_router
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.cart_routes import router as cart_router
from app.api.routes.interaction_routes import router as interaction_router
from app.api.routes.memory_routes import router as memory_router
from app.api.routes.order_routes import router as order_router
from app.api.routes.product_routes import router as product_router
from app.api.routes.session_routes import router as session_router
from app.container import (
    auth_service,
    mongo_manager,
    metrics_collector,
    orchestrator,
    rate_limiter,
    redis_manager,
    session_service,
    settings,
    state_persistence,
    store,
)
from app.infrastructure.observability import RequestTimer

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(product_router, prefix=settings.api_prefix)
app.include_router(cart_router, prefix=settings.api_prefix)
app.include_router(order_router, prefix=settings.api_prefix)
app.include_router(session_router, prefix=settings.api_prefix)
app.include_router(memory_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(interaction_router, prefix=settings.api_prefix)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _rate_limit_profile(request: Request) -> tuple[str, int]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header.split(" ", 1)[1].strip()
        if raw_token:
            digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:24]
            return (
                f"auth:{digest}",
                settings.rate_limit_authenticated_per_minute,
            )

    client_ip = request.client.host if request.client and request.client.host else "unknown"
    return (
        f"anon:{client_ip}",
        settings.rate_limit_anonymous_per_minute,
    )


def _rate_limit_scope(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "v1":
        return parts[1]
    if parts:
        return parts[0]
    return "root"


def _path_group(path: str) -> str:
    return _rate_limit_scope(path)


@app.middleware("http")
async def enforce_rate_limits(request: Request, call_next):  # type: ignore[no-untyped-def]
    if request.url.path in {"/health", "/metrics"}:
        return await call_next(request)

    subject, limit = _rate_limit_profile(request)
    scope = _rate_limit_scope(request.url.path)
    decision = rate_limiter.check(key=f"{scope}:{subject}", limit=limit)

    rate_headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
        "X-RateLimit-Reset": str(decision.reset_epoch),
    }
    if not decision.allowed:
        retry_after = max(1, decision.reset_epoch - int(time()))
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests. Please wait a moment and retry.",
                    "details": [],
                }
            },
            headers={**rate_headers, "Retry-After": str(retry_after)},
        )

    response = await call_next(request)
    for key, value in rate_headers.items():
        response.headers[key] = value
    return response


@app.middleware("http")
async def persist_state_on_mutation(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    if request.method in MUTATING_METHODS:
        await run_in_threadpool(state_persistence.save, store)
    return response


@app.middleware("http")
async def collect_http_metrics(request: Request, call_next):  # type: ignore[no-untyped-def]
    stopwatch = RequestTimer.start()
    path_group = _path_group(request.url.path)
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = stopwatch.elapsed_ms()
        with suppress(Exception):
            metrics_collector.record_http(
                method=request.method,
                path_group=path_group,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            if request.method == "POST" and request.url.path == f"{settings.api_prefix}/orders":
                metrics_collector.record_checkout(success=200 <= status_code < 400)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "services": {
            "mongo": {"status": mongo_manager.status, "error": mongo_manager.error},
            "redis": {"status": redis_manager.status, "error": redis_manager.error},
            "statePersistence": {"enabled": state_persistence.enabled},
        },
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics_collector.render_prometheus(), media_type="text/plain; version=0.0.4")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = websocket.query_params.get("sessionId")
    if not session_id:
        session = session_service.create_session(channel="websocket", initial_context={})
        session_id = session["id"]
        await asyncio.to_thread(state_persistence.save, store)
        await websocket.send_json(
            {"type": "session", "payload": {"sessionId": session_id, "expiresAt": session["expiresAt"]}}
        )

    user_id: str | None = None
    auth_header = websocket.headers.get("authorization")
    if auth_header:
        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.lower() == "bearer":
                user = auth_service.get_user_from_access_token(token)
                user_id = str(user["id"])
        except Exception:
            user_id = None
    if not user_id:
        try:
            session = session_service.get_session(session_id)
            if session.get("userId"):
                user_id = str(session["userId"])
        except Exception:
            user_id = None

    try:
        while True:
            payload = await websocket.receive_json()
            msg_type = payload.get("type")
            if msg_type == "typing":
                await websocket.send_json({"type": "typing", "payload": payload.get("payload", {})})
                continue
            if msg_type != "message":
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {
                            "code": "UNSUPPORTED_MESSAGE_TYPE",
                            "message": "Only `message` and `typing` event types are supported.",
                        },
                    }
                )
                continue

            message = payload.get("payload", {}).get("content", "").strip()
            if not message:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {"code": "VALIDATION_ERROR", "message": "Message content is required."},
                    }
                )
                continue

            if not user_id:
                try:
                    session = session_service.get_session(session_id)
                    if session.get("userId"):
                        user_id = str(session["userId"])
                except Exception:
                    user_id = None

            response = await orchestrator.process_message(
                message=message,
                session_id=session_id,
                user_id=user_id,
                channel="websocket",
            )
            await asyncio.to_thread(state_persistence.save, store)
            await websocket.send_json({"type": "response", "payload": response})
    except WebSocketDisconnect:
        return

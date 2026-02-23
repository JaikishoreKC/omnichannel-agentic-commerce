from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager, suppress
from time import time

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
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
from app.api.routes.voice_webhook_routes import router as voice_webhook_router
from app.container import (
    auth_service,
    cart_service,
    llm_client,
    mongo_manager,
    metrics_collector,
    orchestrator,
    rate_limiter,
    redis_manager,
    session_service,
    settings,
    state_persistence,
    store,
    voice_recovery_service,
)
from app.infrastructure.observability import RequestTimer

app = FastAPI(title=settings.app_name, version="0.1.0")

_voice_scheduler_task: asyncio.Task[None] | None = None

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
app.include_router(voice_webhook_router, prefix=settings.api_prefix)


async def _voice_recovery_scheduler_loop(stop_event: asyncio.Event, interval_seconds: float) -> None:
    while not stop_event.is_set():
        with suppress(Exception):
            await run_in_threadpool(voice_recovery_service.process_due_work)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    global _voice_scheduler_task
    if settings.voice_recovery_scheduler_enabled:
        if _voice_scheduler_task is None or _voice_scheduler_task.done():
            interval = max(5.0, float(settings.voice_recovery_scan_interval_seconds))
            stop_event = asyncio.Event()
            app.state.voice_recovery_stop_event = stop_event
            _voice_scheduler_task = asyncio.create_task(
                _voice_recovery_scheduler_loop(stop_event, interval)
            )
    try:
        yield
    finally:
        stop_event = getattr(app.state, "voice_recovery_stop_event", None)
        if isinstance(stop_event, asyncio.Event):
            stop_event.set()
        if _voice_scheduler_task:
            _voice_scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await _voice_scheduler_task
        _voice_scheduler_task = None


app.router.lifespan_context = app_lifespan

def _error_code(status_code: int) -> str:
    codes = {
        400: "VALIDATION_ERROR",
        401: "AUTH_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
    }
    return codes.get(status_code, "INTERNAL_ERROR")


def _record_security_event(*, event_type: str, severity: str) -> None:
    with suppress(Exception):
        metrics_collector.record_security_event(event_type=event_type, severity=severity)


@app.exception_handler(HTTPException)
async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 401:
        _record_security_event(event_type="auth_unauthorized", severity="warning")
    elif exc.status_code == 403:
        _record_security_event(event_type="access_forbidden", severity="warning")
    elif exc.status_code == 429:
        _record_security_event(event_type="rate_limit_rejected", severity="warning")

    if isinstance(exc.detail, dict) and isinstance(exc.detail.get("error"), dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    message = str(exc.detail) if exc.detail else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": _error_code(exc.status_code),
                "message": message,
                "details": [],
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for issue in exc.errors():
        loc = issue.get("loc", ())
        field_parts = [str(part) for part in loc[1:]] if len(loc) > 1 else [str(loc[0])] if loc else ["body"]
        details.append(
            {
                "field": ".".join(field_parts),
                "message": str(issue.get("msg", "Invalid value")),
            }
        )
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": details,
            }
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": [],
            }
        },
    )

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
STRICT_JSON_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CRITICAL_DUPLICATE_HEADERS = {
    "authorization",
    "x-session-id",
    "x-anonymous-id",
    "content-length",
    "content-type",
}


def _header_occurrence_count(request: Request, header_name: str) -> int:
    target = header_name.strip().lower().encode("latin-1")
    count = 0
    for key, _ in request.scope.get("headers", []):
        if key.lower() == target:
            count += 1
    return count


def _request_has_body(request: Request) -> bool:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            return int(content_length) > 0
        except ValueError:
            return True
    transfer_encoding = request.headers.get("transfer-encoding", "")
    return bool(str(transfer_encoding).strip())


def _is_mutating_api_request(request: Request) -> bool:
    if request.method.upper() not in STRICT_JSON_METHODS:
        return False
    return request.url.path.startswith(f"{settings.api_prefix}/")


def _rate_limit_profile(request: Request) -> tuple[str, int]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header.split(" ", 1)[1].strip()
        if raw_token:
            digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:24]
            limit = settings.rate_limit_authenticated_per_minute
            subject_prefix = "auth"
            with suppress(Exception):
                user = auth_service.get_user_from_access_token(raw_token)
                if str(user.get("role", "")).strip().lower() == "admin":
                    subject_prefix = "admin"
                    limit = settings.rate_limit_admin_per_minute
            return (
                f"{subject_prefix}:{digest}",
                limit,
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


def _stream_text_chunks(text: str, max_chars: int = 28) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    words = cleaned.split()
    if not words:
        return [cleaned[:max_chars]]
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current + " ")
        current = word
    if current:
        chunks.append(current)
    return chunks


@app.middleware("http")
async def apply_response_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; frame-ancestors 'none'; object-src 'none'",
    )
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    return response


@app.middleware("http")
async def enforce_request_hardening(request: Request, call_next):  # type: ignore[no-untyped-def]
    if request.url.path in {"/health", "/metrics"}:
        return await call_next(request)

    if settings.reject_duplicate_critical_headers:
        for header in CRITICAL_DUPLICATE_HEADERS:
            if _header_occurrence_count(request, header) > 1:
                _record_security_event(event_type="duplicate_header_rejected", severity="warning")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": f"Duplicate `{header}` header is not allowed.",
                            "details": [],
                        }
                    },
                )

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            parsed_length = int(content_length)
        except ValueError:
            _record_security_event(event_type="invalid_content_length", severity="warning")
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid Content-Length header.",
                        "details": [],
                    }
                },
            )
        if parsed_length > max(0, int(settings.request_max_body_bytes)):
            _record_security_event(event_type="request_too_large", severity="warning")
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body is too large.",
                        "details": [],
                    }
                },
            )

    if settings.enforce_json_content_type and _is_mutating_api_request(request) and _request_has_body(request):
        content_type = str(request.headers.get("content-type", "")).split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            _record_security_event(event_type="content_type_rejected", severity="warning")
            return JSONResponse(
                status_code=415,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Unsupported Content-Type. Use application/json.",
                        "details": [],
                    }
                },
            )

    return await call_next(request)


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
        warning = str(decision.warning or "").strip()
        if warning:
            severity = "critical" if decision.penalty_seconds >= 60 * 60 else "warning"
            _record_security_event(event_type=warning, severity=severity)
        else:
            _record_security_event(event_type="rate_limit_block", severity="warning")
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
    llm_snapshot = llm_client.circuit_breaker.snapshot
    return {
        "status": "ok",
        "services": {
            "mongo": {"status": mongo_manager.status, "error": mongo_manager.error},
            "redis": {"status": redis_manager.status, "error": redis_manager.error},
            "statePersistence": {"enabled": state_persistence.enabled},
            "llm": {
                "enabled": llm_client.enabled,
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "circuitBreakerState": llm_snapshot.state,
                "circuitBreakerFailures": llm_snapshot.failure_count,
            },
            "voiceRecovery": {
                "schedulerEnabled": settings.voice_recovery_scheduler_enabled,
                "providerEnabled": voice_recovery_service.superu_client.enabled,
                "runtimeEnabled": bool(voice_recovery_service.get_settings().get("enabled", False)),
            },
        },
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics_collector.render_prometheus(), media_type="text/plain; version=0.0.4")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    origin = str(websocket.headers.get("origin", "")).strip()
    if origin and "*" not in settings.cors_origin_list and origin not in settings.cors_origin_list:
        _record_security_event(event_type="ws_origin_rejected", severity="warning")
        await websocket.close(code=1008, reason="origin not allowed")
        return

    await websocket.accept()
    session_service.cleanup_expired()
    async def _send_session_event(session: dict[str, object]) -> None:
        await websocket.send_json(
            {
                "type": "session",
                "payload": {
                    "sessionId": str(session["id"]),
                    "expiresAt": str(session["expiresAt"]),
                },
            }
        )

    async def _ensure_active_session(
        candidate_session_id: str | None,
        *,
        source: str,
    ) -> tuple[str, dict[str, object]]:
        resolved_session_id = str(candidate_session_id or "").strip()
        if resolved_session_id:
            try:
                existing = session_service.get_session(resolved_session_id)
                return resolved_session_id, existing
            except Exception:
                pass

        created = session_service.create_session(
            channel="websocket",
            initial_context={},
            anonymous_id=websocket.headers.get("x-anonymous-id"),
            user_agent=websocket.headers.get("user-agent"),
            ip_address=websocket.client.host if websocket.client else None,
            metadata={
                "source": source,
                "referrer": websocket.headers.get("origin", ""),
            },
        )
        await asyncio.to_thread(state_persistence.save, store)
        await _send_session_event(created)
        return str(created["id"]), created

    session_id, active_session = await _ensure_active_session(
        websocket.query_params.get("sessionId"),
        source="websocket_connect",
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
    if not user_id and active_session.get("userId"):
        user_id = str(active_session["userId"])
    if user_id:
        anonymous_id = str(active_session.get("anonymousId", "")).strip() or None
        if session_id:
            cart_service.merge_guest_cart_into_user(session_id=session_id, user_id=user_id)
        resolved_session = session_service.resolve_user_session(
            user_id=user_id,
            preferred_session_id=session_id,
            channel="websocket",
            anonymous_id=anonymous_id,
            user_agent=websocket.headers.get("user-agent"),
            ip_address=websocket.client.host if websocket.client else None,
            metadata={
                "source": "websocket_connect",
                "referrer": websocket.headers.get("origin", ""),
            },
        )
        with suppress(Exception):
            auth_service.link_identity(
                user_id=user_id,
                channel="websocket",
                external_id=str(resolved_session["id"]),
                anonymous_id=str(resolved_session.get("anonymousId", "")) or None,
            )
        if str(resolved_session["id"]) != session_id:
            session_id = str(resolved_session["id"])
            active_session = resolved_session
            await asyncio.to_thread(state_persistence.save, store)
            await _send_session_event(resolved_session)

    heartbeat_state = {"last_pong": time()}
    heartbeat_interval = max(0.0, float(settings.ws_heartbeat_interval_seconds))
    heartbeat_timeout = max(0.0, float(settings.ws_heartbeat_timeout_seconds))
    stop_heartbeat = asyncio.Event()

    async def heartbeat_loop() -> None:
        if heartbeat_interval <= 0.0 or heartbeat_timeout <= 0.0:
            return
        while not stop_heartbeat.is_set():
            await asyncio.sleep(heartbeat_interval)
            if stop_heartbeat.is_set():
                return
            if time() - heartbeat_state["last_pong"] > heartbeat_timeout:
                with suppress(Exception):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "payload": {
                                "code": "SESSION_EXPIRED",
                                "message": "Connection closed due to heartbeat timeout.",
                            },
                        }
                    )
                with suppress(Exception):
                    await websocket.close(code=1001, reason="heartbeat timeout")
                return
            with suppress(Exception):
                await websocket.send_json(
                    {"type": "ping", "payload": {"timestamp": int(time() * 1000)}}
                )

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        while True:
            payload = await websocket.receive_json()
            msg_type = payload.get("type")
            if msg_type == "pong":
                heartbeat_state["last_pong"] = time()
                continue
            if msg_type == "ping":
                heartbeat_state["last_pong"] = time()
                await websocket.send_json(
                    {"type": "pong", "payload": {"timestamp": int(time() * 1000)}}
                )
                continue
            if msg_type == "typing":
                await websocket.send_json({"type": "typing", "payload": payload.get("payload", {})})
                continue
            if msg_type != "message":
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {
                            "code": "UNSUPPORTED_MESSAGE_TYPE",
                            "message": "Only `message`, `typing`, `ping`, and `pong` event types are supported.",
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

            session_id, active_session = await _ensure_active_session(
                session_id,
                source="websocket_message",
            )
            if not user_id and active_session.get("userId"):
                user_id = str(active_session["userId"])
            if user_id:
                anonymous_id = str(active_session.get("anonymousId", "")).strip() or None
                if session_id:
                    cart_service.merge_guest_cart_into_user(session_id=session_id, user_id=user_id)
                resolved_session = session_service.resolve_user_session(
                    user_id=user_id,
                    preferred_session_id=session_id,
                    channel="websocket",
                    anonymous_id=anonymous_id,
                    user_agent=websocket.headers.get("user-agent"),
                    ip_address=websocket.client.host if websocket.client else None,
                    metadata={
                        "source": "websocket_message",
                        "referrer": websocket.headers.get("origin", ""),
                    },
                )
                with suppress(Exception):
                    auth_service.link_identity(
                        user_id=user_id,
                        channel="websocket",
                        external_id=str(resolved_session["id"]),
                        anonymous_id=str(resolved_session.get("anonymousId", "")) or None,
                    )
                if str(resolved_session["id"]) != session_id:
                    session_id = str(resolved_session["id"])
                    active_session = resolved_session
                    await asyncio.to_thread(state_persistence.save, store)
                    await _send_session_event(resolved_session)

            heartbeat_state["last_pong"] = time()
            assistant_typing_requested = bool(payload.get("payload", {}).get("typing", False))
            if assistant_typing_requested:
                await websocket.send_json(
                    {"type": "typing", "payload": {"actor": "assistant", "isTyping": True}}
                )
            try:
                response = await orchestrator.process_message(
                    message=message,
                    session_id=session_id,
                    user_id=user_id,
                    channel="websocket",
                )
            finally:
                if assistant_typing_requested:
                    await websocket.send_json(
                        {"type": "typing", "payload": {"actor": "assistant", "isTyping": False}}
                    )
            stream_requested = bool(payload.get("payload", {}).get("stream", False))
            stream_id = f"stream_{int(time() * 1000)}" if stream_requested else ""
            if stream_requested:
                chunks = _stream_text_chunks(str(response.get("message", "")))
                await websocket.send_json(
                    {
                        "type": "stream_start",
                        "payload": {
                            "streamId": stream_id,
                            "agent": response.get("agent", "assistant"),
                        },
                    }
                )
                for chunk in chunks:
                    await websocket.send_json(
                        {
                            "type": "stream_delta",
                            "payload": {
                                "streamId": stream_id,
                                "delta": chunk,
                            },
                        }
                    )
                    await asyncio.sleep(0.01)
                await websocket.send_json(
                    {
                        "type": "stream_end",
                        "payload": {"streamId": stream_id},
                    }
                )
            await asyncio.to_thread(state_persistence.save, store)
            envelope: dict[str, object] = {"type": "response", "payload": response}
            if stream_requested:
                envelope["streamId"] = stream_id
            await websocket.send_json(envelope)
    except WebSocketDisconnect:
        return
    finally:
        stop_heartbeat.set()
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task


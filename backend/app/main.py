from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
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
from app.api.routes.ws_route import websocket_endpoint

from app.middleware import (
    apply_response_security_headers,
    enforce_request_hardening,
    enforce_rate_limits,
    collect_http_metrics,
)

from app.container import (
    container,
    llm_client,
    mongo_manager,
    metrics_collector,
    redis_manager,
    settings,
    voice_recovery_service,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize structured logging
    from app.infrastructure.logging import setup_logging
    setup_logging()
    
    # Startup: Initialize container and connect to external services
    await container.start()
    
    # Start the voice recovery scheduler if enabled
    voice_task = None
    stop_event = asyncio.Event()
    if settings.voice_recovery_scheduler_enabled:
        interval = max(5.0, float(settings.voice_recovery_scan_interval_seconds))
        voice_task = asyncio.create_task(
            _voice_recovery_scheduler_loop(stop_event, interval)
        )
    
    yield
    
    # Shutdown: Stop the scheduler and disconnect services
    if voice_task:
        stop_event.set()
        voice_task.cancel()
        with suppress(asyncio.CancelledError):
            await voice_task
            
    await container.stop()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register custom middlewares
app.middleware("http")(apply_response_security_headers)
app.middleware("http")(enforce_request_hardening)
app.middleware("http")(enforce_rate_limits)
app.middleware("http")(collect_http_metrics)

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
        with suppress(RuntimeError, asyncio.CancelledError):
            await run_in_threadpool(voice_recovery_service.process_due_work)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue

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
    with suppress(RuntimeError):
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

@app.get("/health")
def health() -> dict[str, object]:
    llm_snapshot = llm_client.circuit_breaker.snapshot
    return {
        "status": "ok",
        "services": {
            "mongo": {"status": mongo_manager.status, "error": mongo_manager.error},
            "redis": {"status": redis_manager.status, "error": redis_manager.error},
            # Note: statePersistence and other service info derived from container
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
                "runtimeEnabled": bool(voice_recovery_service.get_settings().get("enabled", False)) if mongo_manager.status == "connected" else False,
            },
        },
    }

@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics_collector.render_prometheus(), media_type="text/plain; version=0.0.4")

# WebSocket Route
app.add_api_websocket_route("/ws", websocket_endpoint)

from __future__ import annotations
from app.infrastructure.logging import get_logger
import asyncio
from time import time
from contextlib import suppress
from urllib.parse import urlsplit
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from starlette.websockets import WebSocketState
from app.api.deps import (
    get_auth_service,
    get_cart_service,
    get_container,
    get_metrics_collector,
    get_orchestrator,
    get_session_service,
    get_settings,
)
from app.application.session_workflows import (
    get_or_create_session,
    resolve_user_session_and_link_identity,
)

logger = get_logger(__name__)
auth_service = get_auth_service()
cart_service = get_cart_service()
app_container = get_container()
metrics_collector = get_metrics_collector()
orchestrator = get_orchestrator()
session_service = get_session_service()
settings = get_settings()
GENERAL_FALLBACK_MESSAGE = "I'm sorry, I couldn't provide a detailed answer at the moment."


def _normalize_origin(origin: str) -> str | None:
    value = str(origin or "").strip()
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    scheme = str(parsed.scheme or "").lower()
    hostname = str(parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not hostname:
        return None
    port = parsed.port
    if port is not None:
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{hostname}"


def _error_code(status_code: int) -> str:
    codes = {
        400: "VALIDATION_ERROR",
        401: "AUTH_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }
    return codes.get(int(status_code), "INTERNAL_ERROR")


def _is_socket_connected(websocket: WebSocket) -> bool:
    return (
        websocket.application_state == WebSocketState.CONNECTED
        and websocket.client_state == WebSocketState.CONNECTED
    )


async def _safe_send_json(websocket: WebSocket, payload: dict[str, object]) -> bool:
    if not _is_socket_connected(websocket):
        return False
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError, OSError):
        return False


async def _safe_close(websocket: WebSocket, *, code: int, reason: str) -> None:
    if websocket.application_state == WebSocketState.DISCONNECTED:
        return
    with suppress(WebSocketDisconnect, RuntimeError, OSError):
        await websocket.close(code=code, reason=reason)

def _record_security_event(*, event_type: str, severity: str) -> None:
    with suppress(RuntimeError):
        metrics_collector.record_security_event(event_type=event_type, severity=severity)


def _record_chat_event(*, event_type: str, status: str = "observed") -> None:
    with suppress(RuntimeError):
        metrics_collector.record_chat_event(event_type=event_type, status=status)

async def _send_session_event(websocket: WebSocket, session: dict[str, object]) -> None:
    await _safe_send_json(
        websocket,
        {
            "type": "session",
            "payload": {
                "sessionId": str(session["id"]),
                "expiresAt": str(session["expiresAt"]),
            },
        },
        )

async def _ensure_active_session(
    websocket: WebSocket,
    candidate_session_id: str | None,
    *,
    source: str,
) -> tuple[str, dict[str, object]]:
    resolved_session_id = str(candidate_session_id or "").strip()
    cookie_session_id = str(websocket.cookies.get("session_id") or "").strip()
    logger.info("_ensure_active_session called", source=source)

    if resolved_session_id and cookie_session_id and resolved_session_id != cookie_session_id:
        logger.warning(
            "WebSocket session mismatch detected; keeping explicit session id",
            source=source,
            candidate_session_id=resolved_session_id,
            cookie_session_id=cookie_session_id,
        )

    if not resolved_session_id and cookie_session_id:
        resolved_session_id = cookie_session_id

    if resolved_session_id:
        try:
            existing = await asyncio.to_thread(session_service.get_session, resolved_session_id)
            logger.info("Found existing websocket session")
            return resolved_session_id, existing
        except HTTPException as e:
            logger.warning(f"Session not found or invalid: {resolved_session_id}, error: {e}")
            resolved_session_id = ""

    created = await get_or_create_session(
        session_service=session_service,
        session_id=None,
        channel="websocket",
        anonymous_id=websocket.headers.get("x-anonymous-id"),
        user_agent=websocket.headers.get("user-agent"),
        ip_address=websocket.client.host if websocket.client else None,
        source=source,
        referrer=websocket.headers.get("origin", ""),
    )
    logger.info("Session active for websocket")
    await _send_session_event(websocket, created)
    return str(created["id"]), created

async def _resolve_and_sync_user_session(
    *,
    websocket: WebSocket,
    session_id: str,
    active_session: dict[str, object],
    source: str,
    current_user_id: str | None = None,
) -> tuple[str, dict[str, object], str | None]:
    user_id = current_user_id
    
    if not user_id:
        auth_header = websocket.headers.get("authorization")
        if auth_header:
            try:
                scheme, token = auth_header.split(" ", 1)
                if scheme.lower() == "bearer":
                    user = await asyncio.to_thread(auth_service.get_user_from_access_token, token)
                    user_id = str(user["id"])
            except (ValueError, HTTPException):
                user_id = None
                
    if not user_id and active_session.get("userId"):
        user_id = str(active_session["userId"])
        
    if user_id:
        resolved_session = active_session
        with suppress(LookupError, ValueError):
            resolved_session = await resolve_user_session_and_link_identity(
                session_service=session_service,
                cart_service=cart_service,
                auth_service=auth_service,
                user_id=user_id,
                session=active_session,
                preferred_session_id=session_id,
                channel="websocket",
                user_agent=websocket.headers.get("user-agent"),
                ip_address=websocket.client.host if websocket.client else None,
                source=source,
                referrer=websocket.headers.get("origin", ""),
            )
            
        if str(resolved_session["id"]) != session_id:
            session_id = str(resolved_session["id"])
            active_session = resolved_session
            # await asyncio.to_thread(state_persistence.save, store) # Removed for Phase 6
            await _send_session_event(websocket, resolved_session)
            
    return session_id, active_session, user_id

async def websocket_endpoint(websocket: WebSocket) -> None:
    app_container.ensure_external_baseline()
    origin = str(websocket.headers.get("origin", "")).strip()
    logger.info("WebSocket connection attempt")

    allowed_origins = {
        normalized
        for normalized in (_normalize_origin(item) for item in settings.cors_origin_list)
        if normalized
    }
    normalized_origin = _normalize_origin(origin)
    if (
        origin
        and "*" not in settings.cors_origin_list
        and (normalized_origin is None or normalized_origin not in allowed_origins)
    ):
        logger.warning("WebSocket rejected due to origin policy")
        _record_security_event(event_type="ws_origin_rejected", severity="warning")
        await _safe_close(websocket, code=1008, reason="origin not allowed")
        return

    await websocket.accept()
    logger.info("WebSocket connection accepted")
    await asyncio.to_thread(session_service.cleanup_expired, force=False)
    
    session_id, active_session = await _ensure_active_session(
        websocket,
        websocket.query_params.get("sessionId"),
        source="websocket_connect",
    )

    session_id, active_session, user_id = await _resolve_and_sync_user_session(
        websocket=websocket,
        session_id=session_id,
        active_session=active_session,
        source="websocket_connect",
    )

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
            if not _is_socket_connected(websocket):
                return
            if time() - heartbeat_state["last_pong"] > heartbeat_timeout:
                await _safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "payload": {
                            "code": "SESSION_EXPIRED",
                            "message": "Connection closed due to heartbeat timeout.",
                        },
                    },
                )
                await _safe_close(websocket, code=1001, reason="heartbeat timeout")
                return
            if not await _safe_send_json(
                websocket,
                {"type": "ping", "payload": {"timestamp": int(time() * 1000)}},
            ):
                return

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
                if not await _safe_send_json(
                    websocket,
                    {"type": "pong", "payload": {"timestamp": int(time() * 1000)}},
                ):
                    return
                continue
            if msg_type == "typing":
                if not await _safe_send_json(
                    websocket,
                    {"type": "typing", "payload": payload.get("payload", {})},
                ):
                    return
                continue
            if msg_type != "message":
                if not await _safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "payload": {
                            "code": "UNSUPPORTED_MESSAGE_TYPE",
                            "message": "Only `message`, `typing`, `ping`, and `pong` event types are supported.",
                        },
                    },
                ):
                    return
                continue

            message = payload.get("payload", {}).get("content", "").strip()
            if not message:
                if not await _safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "payload": {"code": "VALIDATION_ERROR", "message": "Message content is required."},
                    },
                ):
                    return
                continue

            if len(message) > settings.ws_max_message_chars:
                if not await _safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "payload": {
                            "code": "MESSAGE_TOO_LONG",
                            "message": f"Message exceeds {settings.ws_max_message_chars} characters.",
                        },
                    },
                ):
                    return
                continue

            session_id, active_session = await _ensure_active_session(
                websocket,
                session_id,
                source="websocket_message",
            )
            
            session_id, active_session, user_id = await _resolve_and_sync_user_session(
                websocket=websocket,
                session_id=session_id,
                active_session=active_session,
                source="websocket_message",
                current_user_id=user_id,
            )

            assistant_typing_requested = bool(payload.get("payload", {}).get("typing", False))
            try:
                if assistant_typing_requested:
                    if not await _safe_send_json(
                        websocket,
                        {"type": "typing", "payload": {"actor": "assistant", "isTyping": True}},
                    ):
                        return

                stream_requested = bool(payload.get("payload", {}).get("stream", False))
                response = None
                current_stream_id = ""
                streamed_any_delta = False

                try:
                    async for chunk in orchestrator.process_message_stream(
                        message=message,
                        session_id=session_id,
                        user_id=user_id,
                        channel="websocket",
                        stream=stream_requested,
                    ):
                        chunk_type = chunk.get("type")
                        if chunk_type == "stream_start":
                            current_stream_id = f"stream_{int(time() * 1000)}"
                            if not await _safe_send_json(
                                websocket,
                                {
                                    "type": "stream_start",
                                    "payload": {
                                        "streamId": current_stream_id,
                                        "agent": chunk["payload"].get("agent", "assistant"),
                                    },
                                },
                            ):
                                return
                        elif chunk_type == "stream_delta":
                            if not await _safe_send_json(
                                websocket,
                                {
                                    "type": "stream_delta",
                                    "payload": {
                                        "streamId": current_stream_id,
                                        "delta": chunk["payload"].get("delta", ""),
                                    },
                                },
                            ):
                                return
                            streamed_any_delta = True
                        elif chunk_type == "stream_end":
                            if not await _safe_send_json(
                                websocket,
                                {
                                    "type": "stream_end",
                                    "payload": {"streamId": current_stream_id},
                                },
                            ):
                                return
                        elif chunk_type == "final_response":
                            response = chunk["payload"]
                finally:
                    if assistant_typing_requested:
                        await _safe_send_json(
                            websocket,
                            {"type": "typing", "payload": {"actor": "assistant", "isTyping": False}}
                        )

                if response:
                    # await asyncio.to_thread(state_persistence.save, store) # Removed for Phase 6
                    response_message = str(response.get("message", "")).strip()
                    if response_message == GENERAL_FALLBACK_MESSAGE:
                        _record_chat_event(event_type="provider_busy_fallback", status="observed")
                        await _safe_send_json(
                            websocket,
                            {
                                "type": "status",
                                "payload": {
                                    "code": "provider_busy",
                                    "message": "AI provider is busy right now. Please retry in a moment.",
                                },
                            },
                        )
                    envelope: dict[str, object] = {"type": "response", "payload": response}
                    if stream_requested and streamed_any_delta:
                        envelope["streamId"] = current_stream_id
                        # Keep legacy stream behavior only when deltas were already emitted.
                        envelope["payload"] = {**response, "message": ""}
                    if stream_requested and (not streamed_any_delta) and not response_message:
                        _record_chat_event(event_type="stream_contract_mismatch", status="observed")
                    if not await _safe_send_json(websocket, envelope):
                        return
            except HTTPException as exc:
                _record_chat_event(event_type="ws_exception_contained", status="http_exception")
                logger.warning("WebSocket request failed with HTTPException", status_code=exc.status_code, detail=str(exc.detail))
                await _safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "payload": {
                            "code": _error_code(exc.status_code),
                            "message": str(exc.detail) if exc.detail else "Request failed.",
                        },
                    },
                )
                await _safe_close(websocket, code=1011, reason="request failed")
                return
            except Exception as exc:
                _record_chat_event(event_type="ws_exception_contained", status="unexpected_exception")
                logger.exception("Unhandled websocket request error", exc_info=exc)
                await _safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "payload": {
                            "code": "INTERNAL_ERROR",
                            "message": "Unexpected websocket error.",
                        },
                    },
                )
                await _safe_close(websocket, code=1011, reason="internal error")
                return
    except WebSocketDisconnect:
        return
    except HTTPException as exc:
        _record_chat_event(event_type="ws_exception_contained", status="endpoint_http_exception")
        logger.warning("WebSocket endpoint failed with HTTPException", status_code=exc.status_code, detail=str(exc.detail))
        await _safe_send_json(
            websocket,
            {
                "type": "error",
                "payload": {
                    "code": _error_code(exc.status_code),
                    "message": str(exc.detail) if exc.detail else "WebSocket failed.",
                },
            },
        )
        await _safe_close(websocket, code=1011, reason="endpoint failed")
        return
    except RuntimeError as exc:
        if 'Cannot call "send" once a close message has been sent.' in str(exc):
            return
        _record_chat_event(event_type="ws_exception_contained", status="endpoint_runtime_exception")
        logger.exception("Unhandled websocket runtime error", exc_info=exc)
        await _safe_send_json(
            websocket,
            {
                "type": "error",
                "payload": {
                    "code": "INTERNAL_ERROR",
                    "message": "WebSocket runtime error.",
                },
            },
        )
        await _safe_close(websocket, code=1011, reason="runtime error")
        return
    except Exception as exc:
        _record_chat_event(event_type="ws_exception_contained", status="endpoint_unexpected_exception")
        logger.exception("Unhandled websocket endpoint error", exc_info=exc)
        await _safe_send_json(
            websocket,
            {
                "type": "error",
                "payload": {
                    "code": "INTERNAL_ERROR",
                    "message": "WebSocket endpoint error.",
                },
            },
        )
        await _safe_close(websocket, code=1011, reason="endpoint error")
        return
    finally:
        stop_heartbeat.set()
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task

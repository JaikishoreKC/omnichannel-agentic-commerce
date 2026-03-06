from __future__ import annotations
import hashlib
from time import time
from contextlib import suppress
from fastapi import Request
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from app.api.deps import (
    get_auth_service,
    get_metrics_collector,
    get_rate_limiter,
    get_settings,
)

auth_service = get_auth_service()
metrics_collector = get_metrics_collector()
rate_limiter = get_rate_limiter()
settings = get_settings()

def _rate_limit_profile(request: Request) -> tuple[str, int]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header.split(" ", 1)[1].strip()
        if raw_token:
            digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:24]
            limit = settings.rate_limit_authenticated_per_minute
            subject_prefix = "auth"
            subject_id = digest
            with suppress(HTTPException):
                user = auth_service.get_user_from_access_token(raw_token)
                user_id = str(user.get("id", "")).strip()
                if user_id:
                    subject_id = user_id
                if str(user.get("role", "")).strip().lower() == "admin":
                    subject_prefix = "admin"
                    limit = settings.rate_limit_admin_per_minute
            return (
                f"{subject_prefix}:{subject_id}",
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

def _record_security_event(*, event_type: str, severity: str) -> None:
    with suppress(RuntimeError):
        metrics_collector.record_security_event(event_type=event_type, severity=severity)

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

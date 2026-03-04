from __future__ import annotations
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.config import Settings
from app.api.deps import get_metrics_collector, get_settings
from contextlib import suppress

metrics_collector = get_metrics_collector()
settings = get_settings()

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

def _record_security_event(*, event_type: str, severity: str) -> None:
    with suppress(RuntimeError):
        metrics_collector.record_security_event(event_type=event_type, severity=severity)

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

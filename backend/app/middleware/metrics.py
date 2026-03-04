from __future__ import annotations
from contextlib import suppress
from fastapi import Request
from app.api.deps import get_metrics_collector, get_settings
from app.infrastructure.observability import RequestTimer

metrics_collector = get_metrics_collector()
settings = get_settings()

def _rate_limit_scope(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "v1":
        return parts[1]
    if parts:
        return parts[0]
    return "root"

def _path_group(path: str) -> str:
    return _rate_limit_scope(path)

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
        with suppress(RuntimeError):
            metrics_collector.record_http(
                method=request.method,
                path_group=path_group,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            if request.method == "POST" and request.url.path == f"{settings.api_prefix}/orders":
                metrics_collector.record_checkout(success=200 <= status_code < 400)

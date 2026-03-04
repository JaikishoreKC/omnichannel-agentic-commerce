from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request, Response

from app.container import container


ACCESS_COOKIE_KEY = "access_token"


def get_container() -> Any:
    return container


def get_settings() -> Any:
    return container.settings


def get_auth_service() -> Any:
    return container.auth_service


def get_session_service() -> Any:
    return container.session_service


def get_cart_service() -> Any:
    return container.cart_service


def get_order_service() -> Any:
    return container.order_service


def get_product_service() -> Any:
    return container.product_service


def get_memory_service() -> Any:
    return container.memory_service


def get_interaction_service() -> Any:
    return container.interaction_service


def get_support_service() -> Any:
    return container.support_service


def get_admin_service() -> Any:
    return container.admin_service


def get_admin_activity_service() -> Any:
    return container.admin_activity_service


def get_auth_repository() -> Any:
    return container.auth_repository


def get_order_repository() -> Any:
    return container.order_repository


def get_product_repository() -> Any:
    return container.product_repository


def get_category_service() -> Any:
    return container.category_service


def get_inventory_service() -> Any:
    return container.inventory_service


def get_voice_recovery_service() -> Any:
    return container.voice_recovery_service


def get_superu_client() -> Any:
    return container.superu_client


def get_metrics_collector() -> Any:
    return container.metrics_collector


def get_rate_limiter() -> Any:
    return container.rate_limiter


def get_orchestrator() -> Any:
    return container.orchestrator


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1]


def _extract_access_token(request: Request) -> str | None:
    bearer_token = _extract_bearer_token(request)
    if bearer_token:
        return bearer_token
    cookie_token = str(request.cookies.get(ACCESS_COOKIE_KEY) or "").strip()
    return cookie_token or None


def get_current_user(request: Request) -> dict[str, Any]:
    token = _extract_access_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    auth_service = get_auth_service()
    return auth_service.get_user_from_access_token(token)


def get_optional_user(request: Request) -> dict[str, Any] | None:
    token = _extract_access_token(request)
    if not token:
        return None
    auth_service = get_auth_service()
    return auth_service.get_user_from_access_token(token)


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def resolve_session_id(
    request: Request,
    response: Response,
    x_session_id: str | None = Header(default=None),
) -> str:
    session_service = get_session_service()
    settings = get_settings()
    session_id = x_session_id or request.cookies.get("session_id")
    if session_id:
        try:
            session_service.touch(session_id)
            session_service.get_session(session_id)
            return session_id
        except HTTPException:
            pass

    created = session_service.create_session(
        channel="web",
        initial_context={},
        anonymous_id=request.headers.get("X-Anonymous-Id"),
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        metadata={
            "source": "http_dependency",
            "referrer": request.headers.get("referer", ""),
        },
    )
    session_id = created["id"]
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite,
    )
    return session_id

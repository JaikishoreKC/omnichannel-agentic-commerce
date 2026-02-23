from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request, Response

from app.container import auth_service, session_service


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1]


def get_current_user(request: Request) -> dict[str, Any]:
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return auth_service.get_user_from_access_token(token)


def get_optional_user(request: Request) -> dict[str, Any] | None:
    token = _extract_bearer_token(request)
    if not token:
        return None
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
    session_service.cleanup_expired()
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
        secure=False,
        samesite="lax",
    )
    return session_id

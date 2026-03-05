from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response

from app.api.deps import (
    ACCESS_COOKIE_KEY,
    get_auth_service,
    get_cart_service,
    get_current_user,
    get_session_service,
    get_settings,
)
from app.models.schemas import (
    AuthProfileUpdateRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = get_auth_service()
cart_service = get_cart_service()
session_service = get_session_service()
settings = get_settings()
REFRESH_COOKIE_KEY = "refresh_token"


def _set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_KEY,
        value=access_token,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_KEY,
        value=refresh_token,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_COOKIE_KEY,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite,
    )
    response.delete_cookie(
        key=REFRESH_COOKIE_KEY,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite,
    )


def _resolve_user_session_context(
    *,
    request: Request,
    user_id: str,
    channel: str,
    source: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    session_id = request.headers.get("X-Session-Id") or request.cookies.get("session_id")
    anonymous_id = None
    if session_id:
        try:
            guest_session = session_service.get_session(session_id)
            anonymous_id = guest_session.get("anonymousId")
        except HTTPException:
            anonymous_id = None
    if session_id:
        cart_service.merge_guest_cart_into_user(session_id=session_id, user_id=user_id)

    resolved = session_service.resolve_user_session(
        user_id=user_id,
        preferred_session_id=session_id,
        channel=channel,
        anonymous_id=str(anonymous_id) if anonymous_id else None,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        metadata={
            "source": source,
            "referrer": request.headers.get("referer", ""),
        },
    )
    linked_user = auth_service.link_identity(
        user_id=user_id,
        channel=channel,
        external_id=str(resolved["id"]),
        anonymous_id=str(resolved.get("anonymousId", "")) or None,
    )
    return resolved, linked_user


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response) -> dict[str, object]:
    channel = request.headers.get("X-Channel", "web").strip().lower() or "web"
    result = auth_service.register(
        email=payload.email,
        password=payload.password,
        name=payload.name,
        phone=payload.phone,
        timezone=payload.timezone,
    )
    resolved, linked_user = _resolve_user_session_context(
        request=request,
        user_id=str(result["user"]["id"]),
        channel=channel,
        source="auth_register",
    )
    result["user"]["identity"] = linked_user.get("identity")
    result["sessionId"] = str(resolved["id"])
    _set_auth_cookies(
        response,
        access_token=str(result.get("accessToken", "")),
        refresh_token=str(result.get("refreshToken", "")),
    )
    return result


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    channel = request.headers.get("X-Channel", "web").strip().lower() or "web"
    result = auth_service.login(email=payload.email, password=payload.password, otp=payload.otp)
    resolved, linked_user = _resolve_user_session_context(
        request=request,
        user_id=str(result["user"]["id"]),
        channel=channel,
        source="auth_login",
    )
    result["user"]["identity"] = linked_user.get("identity")
    result["sessionId"] = str(resolved["id"])
    _set_auth_cookies(
        response,
        access_token=str(result.get("accessToken", "")),
        refresh_token=str(result.get("refreshToken", "")),
    )
    return result


@router.post("/refresh")
def refresh(
    payload: RefreshRequest,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE_KEY),
) -> dict[str, object]:
    refresh_token = str(payload.refreshToken or refresh_cookie or "").strip()
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token is required")
    result = auth_service.refresh(refresh_token=refresh_token)
    _set_auth_cookies(
        response,
        access_token=str(result.get("accessToken", "")),
        refresh_token=str(result.get("refreshToken", "")),
    )
    return result


@router.get("/profile")
def get_profile(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, object]:
    profile = auth_service.get_profile(user_id=str(user["id"]))
    return {"user": profile}


@router.patch("/profile")
def update_profile(
    payload: AuthProfileUpdateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, object]:
    updates = payload.model_dump(exclude_unset=True)
    profile = auth_service.update_profile(
        user_id=str(user["id"]),
        updates=updates,
    )
    return {"user": profile}


@router.post("/logout", status_code=204, response_class=Response)
def logout(
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE_KEY),
) -> Response:
    refresh_token = str(refresh_cookie or "").strip() or None
    auth_service.logout(refresh_token)
    _clear_auth_cookies(response)
    response.status_code = 204
    return response

@router.post("/reset-password-request", status_code=202)
def request_password_reset(payload: PasswordResetRequest) -> dict[str, object]:
    auth_service.request_password_reset(email=payload.email)
    return {"message": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password", status_code=200)
def confirm_password_reset(payload: PasswordResetConfirmRequest) -> dict[str, object]:
    auth_service.confirm_password_reset(token=payload.token, new_password=payload.newPassword)
    return {"message": "Password successfully reset."}

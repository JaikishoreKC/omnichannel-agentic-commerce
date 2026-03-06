from __future__ import annotations

import hashlib

from starlette.requests import Request

from app.middleware import rate_limiting


def _make_request(*, authorization: str | None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/orders",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_rate_limit_profile_prefers_user_id_for_authenticated_subject(monkeypatch) -> None:
    request = _make_request(authorization="Bearer token-user-1")

    monkeypatch.setattr(
        rate_limiting.auth_service,
        "get_user_from_access_token",
        lambda token: {"id": "user_abc", "role": "customer"},
    )

    subject, limit = rate_limiting._rate_limit_profile(request)
    assert subject == "auth:user_abc"
    assert limit == rate_limiting.settings.rate_limit_authenticated_per_minute


def test_rate_limit_profile_uses_admin_bucket_for_admin_user(monkeypatch) -> None:
    request = _make_request(authorization="Bearer token-admin-1")

    monkeypatch.setattr(
        rate_limiting.auth_service,
        "get_user_from_access_token",
        lambda token: {"id": "admin_xyz", "role": "admin"},
    )

    subject, limit = rate_limiting._rate_limit_profile(request)
    assert subject == "admin:admin_xyz"
    assert limit == rate_limiting.settings.rate_limit_admin_per_minute


def test_rate_limit_profile_falls_back_to_token_digest_for_invalid_token(monkeypatch) -> None:
    raw_token = "broken-token"
    request = _make_request(authorization=f"Bearer {raw_token}")

    def _raise(_token: str):
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid access token")

    monkeypatch.setattr(rate_limiting.auth_service, "get_user_from_access_token", _raise)

    subject, limit = rate_limiting._rate_limit_profile(request)
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:24]
    assert subject == f"auth:{digest}"
    assert limit == rate_limiting.settings.rate_limit_authenticated_per_minute

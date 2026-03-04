from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.services.auth_service import AuthService


class _FakeAuthRepository:
    def __init__(self, user: dict[str, Any] | None = None) -> None:
        self._user = user
        self.reset_token_payload: dict[str, Any] | None = None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        if self._user is None:
            return None
        if str(self._user.get("email", "")).strip().lower() == email.strip().lower():
            return self._user
        return None

    def set_password_reset_token(self, token_hash: str, payload: dict[str, Any]) -> None:
        self.reset_token_payload = {"tokenHash": token_hash, **payload}


class _FakeLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, Any]]] = []

    def info(self, message: str, **kwargs: Any) -> None:
        self.messages.append((message, kwargs))


def test_validate_security_rejects_default_token_secret_in_production() -> None:
    settings = Settings(environment="production", token_secret="replace-with-strong-secret")
    with pytest.raises(ValueError):
        settings.validate_security()


def test_validate_security_rejects_default_admin_mfa_secret_when_required() -> None:
    settings = Settings(
        environment="production",
        token_secret="x" * 48,
        admin_mfa_required=True,
        admin_mfa_totp_secret="JBSWY3DPEHPK3PXP",
    )
    with pytest.raises(ValueError):
        settings.validate_security()


def test_password_reset_does_not_log_or_store_raw_token() -> None:
    settings = Settings(token_secret="x" * 48)
    repository = _FakeAuthRepository(
        user={
            "id": "user_1",
            "email": "customer@example.com",
        }
    )
    service = AuthService(settings=settings, auth_repository=repository)  # type: ignore[arg-type]
    fake_logger = _FakeLogger()
    service.logger = fake_logger

    service.request_password_reset("customer@example.com")

    assert repository.reset_token_payload is not None
    token_hash = str(repository.reset_token_payload.get("tokenHash", ""))
    assert len(token_hash) == 64
    assert all(character in "0123456789abcdef" for character in token_hash)
    assert all("Token:" not in message for message, _ in fake_logger.messages)

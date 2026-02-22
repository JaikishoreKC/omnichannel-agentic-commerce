from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any

from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.repositories.auth_repository import AuthRepository
from app.store.in_memory import InMemoryStore


class AuthService:
    def __init__(
        self,
        store: InMemoryStore,
        settings: Settings,
        auth_repository: AuthRepository,
    ) -> None:
        self.store = store
        self.settings = settings
        self.auth_repository = auth_repository

    def register(
        self,
        email: str,
        password: str,
        name: str,
        phone: str | None = None,
        timezone: str | None = None,
    ) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        with self.store.lock:
            if self.auth_repository.get_user_by_email(normalized_email):
                raise HTTPException(status_code=409, detail="Email already registered")

            user_id = self.store.next_id("user")
            now = datetime.now(dt_timezone.utc).isoformat()
            user = {
                "id": user_id,
                "email": normalized_email,
                "name": name.strip(),
                "passwordHash": hash_password(password),
                "role": "customer",
                "createdAt": now,
                "updatedAt": now,
                "lastLoginAt": now,
                "phone": phone.strip() if isinstance(phone, str) and phone.strip() else None,
                "timezone": timezone.strip() if isinstance(timezone, str) and timezone.strip() else None,
            }
            self.auth_repository.create_user(user)
            return self._issue_tokens(user)

    def login(self, email: str, password: str) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        with self.store.lock:
            user = self.auth_repository.get_user_by_email(normalized_email)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid credentials")

            if not verify_password(password, user["passwordHash"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            user["lastLoginAt"] = datetime.now(dt_timezone.utc).isoformat()
            self.auth_repository.update_user(user)
            return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        try:
            payload = decode_token(
                token=refresh_token,
                secret=self.settings.token_secret,
                expected_type="refresh",
            )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

        with self.store.lock:
            token_record = self.auth_repository.get_refresh_token(refresh_token)
            if not token_record:
                raise HTTPException(status_code=401, detail="Refresh token revoked")

            user_id = payload.get("sub")
            user = self.auth_repository.get_user_by_id(str(user_id))
            if not user:
                raise HTTPException(status_code=401, detail="User not found")

            # Rotation: revoke old refresh token and issue a new pair.
            self.auth_repository.revoke_refresh_token(refresh_token)
            return self._issue_tokens(user)

    def get_user_from_access_token(self, access_token: str) -> dict[str, Any]:
        try:
            payload = decode_token(
                token=access_token,
                secret=self.settings.token_secret,
                expected_type="access",
            )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid access token") from exc

        user_id = str(payload.get("sub", ""))
        user = self.auth_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    def _issue_tokens(self, user: dict[str, Any]) -> dict[str, Any]:
        access_token = create_token(
            subject=user["id"],
            token_type="access",
            ttl_seconds=self.settings.access_token_ttl_seconds,
            secret=self.settings.token_secret,
            extra_claims={"role": user["role"], "email": user["email"]},
        )
        refresh_token = create_token(
            subject=user["id"],
            token_type="refresh",
            ttl_seconds=self.settings.refresh_token_ttl_seconds,
            secret=self.settings.token_secret,
        )

        self.auth_repository.set_refresh_token(
            refresh_token,
            {
                "userId": user["id"],
                "createdAt": datetime.now(dt_timezone.utc).isoformat(),
            },
        )

        public_user = {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "createdAt": user["createdAt"],
            "phone": user.get("phone"),
            "timezone": user.get("timezone"),
        }
        return {
            "user": public_user,
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresIn": self.settings.access_token_ttl_seconds,
        }

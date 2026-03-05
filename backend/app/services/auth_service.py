from __future__ import annotations

import hashlib
import secrets
from copy import deepcopy
from datetime import datetime, timezone as dt_timezone
from typing import Any
from app.infrastructure.logging import get_logger

from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.repositories.auth_repository import AuthRepository
from app.core.utils import generate_id, iso_now


class AuthService:
    def __init__(
        self,
        settings: Settings,
        auth_repository: AuthRepository,
    ) -> None:
        self.settings = settings
        self.auth_repository = auth_repository
        self.logger = get_logger(__name__)

    def register(
        self,
        email: str,
        password: str,
        name: str,
        phone: str | None = None,
        timezone: str | None = None,
    ) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        if self.auth_repository.get_user_by_email(normalized_email):
            raise HTTPException(status_code=409, detail="Email already registered")

        user_id = generate_id("user")
        now = iso_now()
        user = {
            "id": user_id,
            "email": normalized_email,
            "name": name.strip(),
            "passwordHash": hash_password(password),
            "role": "customer",
            "status": "active",
            "identity": {"anonymousId": None, "linkedChannels": []},
            "createdAt": now,
            "updatedAt": now,
            "lastLoginAt": now,
            "phone": phone.strip() if isinstance(phone, str) and phone.strip() else None,
            "timezone": timezone.strip() if isinstance(timezone, str) and timezone.strip() else None,
            "defaultShippingAddress": None,
        }
        self.auth_repository.create_user(user)
        return self._issue_tokens(user)

    def login(self, email: str, password: str, otp: str | None = None) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        user = self.auth_repository.get_user_by_email(normalized_email)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(password, user["passwordHash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if str(user.get("role", "")).lower() == "admin" and self.settings.admin_mfa_required:
            try:
                import pyotp
                supplied = str(otp or "").strip()
                totp = pyotp.TOTP(self.settings.admin_mfa_totp_secret)
                if not supplied or not totp.verify(supplied):
                    raise HTTPException(status_code=401, detail="Invalid Admin OTP")
            except ImportError:
                raise HTTPException(status_code=503, detail="Admin MFA is unavailable")

        user["lastLoginAt"] = iso_now()
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

    def request_password_reset(self, email: str) -> None:
        normalized_email = email.strip().lower()
        user = self.auth_repository.get_user_by_email(normalized_email)
        if not user:
            # Important: Do not throw error here to prevent email enumeration
            return

        reset_token = secrets.token_urlsafe(32)
        reset_token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(dt_timezone.utc).timestamp() + 3600
        self.auth_repository.set_password_reset_token(
            token_hash=reset_token_hash,
            payload={
                "userId": str(user["id"]),
                "email": normalized_email,
                "expiresAt": float(expires_at),
                "createdAt": iso_now(),
            },
        )
        self.logger.info("Password reset requested", email=normalized_email)

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        token_hash = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
        token_payload = self.auth_repository.get_password_reset_token(token_hash)
        if not token_payload:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        expires_at = float(token_payload.get("expiresAt", 0))
        if expires_at <= datetime.now(dt_timezone.utc).timestamp():
            self.auth_repository.delete_password_reset_token(token_hash)
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        user_id = token_payload.get("userId")
        user = self.auth_repository.get_user_by_id(str(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User no longer exists")

        user["passwordHash"] = hash_password(new_password)
        user["updatedAt"] = iso_now()
        self.auth_repository.update_user(user)
        self.auth_repository.delete_password_reset_token(token_hash)

    def logout(self, refresh_token: str | None) -> None:
        # This method was part of the provided code edit, but its implementation
        # was incomplete/incorrect. Assuming the intent was to revoke the token.
        if refresh_token:
            self.auth_repository.revoke_refresh_token(refresh_token)

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

    def link_identity(
        self,
        *,
        user_id: str,
        channel: str,
        external_id: str,
        anonymous_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.auth_repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        identity = user.get("identity", {})
        if not isinstance(identity, dict):
            identity = {}
        linked_channels = identity.get("linkedChannels")
        if not isinstance(linked_channels, list):
            linked_channels = []

        provider = channel.strip().lower() if channel else "web"
        ext_id = external_id.strip()
        if ext_id:
            already = any(
                isinstance(item, dict)
                and str(item.get("provider", "")).strip().lower() == provider
                and str(item.get("externalId", "")).strip() == ext_id
                for item in linked_channels
            )
            if not already:
                linked_channels.append({"provider": provider, "externalId": ext_id})

        if anonymous_id and str(anonymous_id).strip():
            identity["anonymousId"] = str(anonymous_id).strip()
        elif identity.get("anonymousId") is None:
            identity["anonymousId"] = None
        identity["linkedChannels"] = linked_channels
        user["identity"] = identity
        user["updatedAt"] = iso_now()
        self.auth_repository.update_user(user)
        return user

    def get_profile(self, user_id: str) -> dict[str, Any]:
        user = self.auth_repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return self._to_public_user(user)

    def update_profile(
        self,
        user_id: str,
        *,
        name: str | None,
        phone: str | None,
        timezone: str | None,
        default_shipping_address: dict[str, Any] | None,
    ) -> dict[str, Any]:
        user = self.auth_repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if isinstance(name, str) and name.strip():
            user["name"] = name.strip()
        user["phone"] = self._normalize_text(phone)
        user["timezone"] = self._normalize_text(timezone)
        user["defaultShippingAddress"] = self._normalize_profile_address(default_shipping_address)
        user["updatedAt"] = iso_now()
        self.auth_repository.update_user(user)
        return self._to_public_user(user)

    def _normalize_text(self, value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed if trimmed else None

    def _normalize_profile_address(self, address: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(address, dict):
            return None
        normalized: dict[str, Any] = {}
        for key in ("name", "line1", "line2", "city", "state", "postalCode", "country"):
            value = address.get(key)
            if isinstance(value, str):
                text = value.strip()
                if text:
                    normalized[key] = text
            elif value is not None and key == "line2":
                normalized[key] = value

        required = ("name", "line1", "city", "state", "postalCode", "country")
        if not all(isinstance(normalized.get(field), str) and str(normalized.get(field)).strip() for field in required):
            return None
        return normalized

    def _is_profile_complete(self, user: dict[str, Any]) -> bool:
        phone = user.get("phone")
        default_address = user.get("defaultShippingAddress")
        if not isinstance(phone, str) or not phone.strip():
            return False
        if not isinstance(default_address, dict):
            return False
        required = ("name", "line1", "city", "state", "postalCode", "country")
        return all(isinstance(default_address.get(field), str) and str(default_address.get(field)).strip() for field in required)

    def _to_public_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "status": user.get("status", "active"),
            "createdAt": user["createdAt"],
            "phone": user.get("phone"),
            "timezone": user.get("timezone"),
            "defaultShippingAddress": deepcopy(user.get("defaultShippingAddress"))
            if isinstance(user.get("defaultShippingAddress"), dict)
            else None,
            "profileComplete": self._is_profile_complete(user),
            "identity": deepcopy(user.get("identity")) if isinstance(user.get("identity"), dict) else None,
        }

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
                "createdAt": iso_now(),
            },
        )

        public_user = self._to_public_user(user)
        return {
            "user": public_user,
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresIn": self.settings.access_token_ttl_seconds,
        }

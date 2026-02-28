from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.core.utils import generate_id, iso_now, utc_now
from app.infrastructure.superu_client import SuperUClient
from app.services.notification_service import NotificationService
from app.services.support_service import SupportService
from app.repositories.voice_repository import VoiceRepository
from app.repositories.auth_repository import AuthRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository

from app.services.voice import settings as voice_settings
from app.services.voice import jobs as voice_jobs
from app.services.voice import calls as voice_calls
from app.services.voice import alerts as voice_alerts
from app.services.voice import helpers as voice_helpers

class VoiceRecoveryService:
    def __init__(
        self,
        *,
        settings: Settings,
        superu_client: SuperUClient,
        support_service: SupportService,
        notification_service: NotificationService,
        voice_repository: VoiceRepository,
        user_repository: AuthRepository,
        cart_repository: CartRepository,
        order_repository: OrderRepository,
    ) -> None:
        self.settings = settings
        self.superu_client = superu_client
        self.support_service = support_service
        self.notification_service = notification_service
        self.voice_repository = voice_repository
        self.user_repository = user_repository
        self.cart_repository = cart_repository
        self.order_repository = order_repository

    def process_due_work(self) -> dict[str, Any]:
        now = utc_now()
        settings = self.get_settings()
        enqueued = voice_jobs.enqueue_abandoned_cart_jobs(
            now=now,
            voice_repository=self.voice_repository,
            cart_repository=self.cart_repository,
            settings=settings,
            voice_service=self,
        )
        processed = voice_jobs.process_due_jobs(
            now=now, voice_repository=self.voice_repository, voice_service=self
        )
        polled = self._poll_provider_updates(now=now)
        generated_alerts = voice_alerts.evaluate_alerts(
            now=now, settings=settings, voice_service=self
        )
        return {
            "enqueued": enqueued,
            "processed": processed,
            "polled": polled,
            "alertsGenerated": generated_alerts,
            "settingsEnabled": bool(settings.get("enabled", False)),
        }

    def get_settings(self) -> dict[str, Any]:
        return voice_settings.get_settings(self.voice_repository)

    def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        return voice_settings.update_settings(self.voice_repository, updates)

    def list_calls(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        return voice_calls.list_calls(self.voice_repository, limit=limit, status=status)

    def list_jobs(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        return self.voice_repository.list_jobs(limit=limit, status=status)

    def suppress_user(self, *, user_id: str, reason: str) -> dict[str, Any]:
        payload = {
            "userId": user_id,
            "reason": reason.strip() or "manual_suppression",
            "createdAt": iso_now(),
        }
        self.voice_repository.upsert_suppression(user_id, payload)
        return payload

    def unsuppress_user(self, *, user_id: str) -> None:
        self.voice_repository.delete_suppression(user_id)

    def list_suppressions(self) -> list[dict[str, Any]]:
        return self.voice_repository.list_suppressions()

    def list_alerts(self, *, limit: int = 50, severity: str | None = None) -> list[dict[str, Any]]:
        return self.voice_repository.list_alerts(limit=limit, severity=severity)

    def stats(self) -> dict[str, Any]:
        return voice_alerts.get_stats(
            now=utc_now(),
            settings=self.get_settings(),
            voice_service=self,
        )

    def _poll_provider_updates(self, *, now: datetime) -> int:
        if not self.superu_client.enabled:
            return 0
        
        active_calls = [
            call for call in self.voice_repository.list_calls(limit=1000)
            if str(call.get("status", "")) in {"initiated", "ringing", "in_progress"}
            and str(call.get("providerCallId", "")).strip()
        ]
        
        updates = 0
        for call in active_calls:
            provider_call_id = str(call.get("providerCallId", "")).strip()
            try:
                rows = self.superu_client.fetch_call_logs(call_id=provider_call_id, limit=1)
            except RuntimeError as exc:
                voice_alerts.append_alert(
                    code="VOICE_POLL_FAILED",
                    message=f"Failed to poll SuperU call logs: {exc}",
                    severity="warning",
                    details={"callId": call.get("id"), "providerCallId": provider_call_id},
                    voice_repository=self.voice_repository,
                )
                continue
            if not rows:
                continue
            latest = rows[-1]
            normalized_status = voice_helpers.normalize_provider_status(latest)
            outcome = voice_helpers.extract_outcome(latest)
            if normalized_status in {"completed", "failed"}:
                voice_calls.update_call_terminal(
                    voice_repository=self.voice_repository,
                    call_id=str(call["id"]),
                    status=normalized_status,
                    outcome=outcome,
                    payload=latest,
                    voice_service=self,
                )
                updates += 1
            elif normalized_status in {"ringing", "in_progress"}:
                voice_calls.update_call_progress(
                    voice_repository=self.voice_repository,
                    call_id=str(call["id"]),
                    status=normalized_status,
                    payload=latest,
                )
                updates += 1
        return updates

    def ingest_provider_callback(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        provider_call_id = voice_helpers.extract_provider_call_id(payload)
        if not provider_call_id:
            return {
                "accepted": False,
                "matched": False,
                "idempotent": False,
                "reason": "missing_provider_call_id",
            }

        matched_call_id: str | None = None
        # Efficient lookup by provider_call_id would be better
        # For now, list recent calls.
        calls = self.voice_repository.list_calls(limit=1000)
        for call in calls:
            if str(call.get("providerCallId", "")).strip() == provider_call_id:
                matched_call_id = str(call.get("id", "")).strip() or None
                break
                
        if not matched_call_id:
            return {
                "accepted": True,
                "matched": False,
                "idempotent": False,
                "reason": "call_not_found",
                "providerCallId": provider_call_id,
            }

        event_key = voice_helpers.provider_event_key(payload, self.superu_client)
        current = self.voice_repository.get_call(matched_call_id)
        if not isinstance(current, dict):
            return {
                "accepted": True,
                "matched": False,
                "idempotent": False,
                "reason": "call_not_found",
                "providerCallId": provider_call_id,
            }

        seen_keys = {
            str(value).strip()
            for value in current.get("providerEventKeys", [])
            if isinstance(value, str) and value.strip()
        }
        if event_key in seen_keys:
            return {
                "accepted": True,
                "matched": True,
                "idempotent": True,
                "callId": matched_call_id,
                "providerCallId": provider_call_id,
                "status": str(current.get("status", "")),
                "outcome": str(current.get("outcome", "")),
            }

        normalized_status = voice_helpers.normalize_provider_status(payload)
        outcome = voice_helpers.extract_outcome(payload)
        if normalized_status in {"completed", "failed"}:
            voice_calls.update_call_terminal(
                voice_repository=self.voice_repository,
                call_id=matched_call_id,
                status=normalized_status,
                outcome=outcome,
                payload=payload,
                voice_service=self,
            )
        else:
            voice_calls.update_call_progress(
                voice_repository=self.voice_repository,
                call_id=matched_call_id,
                status=normalized_status,
                payload=payload,
            )

        latest = self.voice_repository.get_call(matched_call_id)
        if isinstance(latest, dict):
            keys = [
                str(value).strip()
                for value in latest.get("providerEventKeys", [])
                if isinstance(value, str) and value.strip()
            ]
            if event_key not in keys:
                keys.append(event_key)
            if len(keys) > 200:
                keys = keys[-200:]
            latest["providerEventKeys"] = keys

            events = latest.get("providerEvents", [])
            if not isinstance(events, list):
                events = []
            events.append(
                {
                    "key": event_key,
                    "status": normalized_status,
                    "outcome": outcome,
                    "receivedAt": iso_now(),
                }
            )
            if len(events) > 200:
                events = events[-200:]
            latest["providerEvents"] = events
            latest["updatedAt"] = iso_now()
            self.voice_repository.upsert_call(latest)

        return {
            "accepted": True,
            "matched": True,
            "idempotent": False,
            "callId": matched_call_id,
            "providerCallId": provider_call_id,
            "status": normalized_status,
            "outcome": outcome,
        }

    def _record_call_event(self, **kwargs: Any) -> None:
        voice_calls.record_call_event(voice_repository=self.voice_repository, voice_service=self, **kwargs)

    def _get_user(self, user_id: Any) -> dict[str, Any] | None:
        key = str(user_id or "").strip()
        if not key:
            return None
        return self.user_repository.get_by_id(key)

    def _get_cart(self, cart_id: Any) -> dict[str, Any] | None:
        key = str(cart_id or "").strip()
        if not key:
            return None
        return self.cart_repository.get_by_id(key)

    def _has_newer_order(self, *, user_id: str, since: datetime) -> bool:
        orders = self.order_repository.list_all()
        for order in orders:
            if str(order.get("userId", "")) != user_id:
                continue
            created_at = voice_helpers.parse_iso(order.get("createdAt"))
            if created_at and created_at > since:
                return True
        return False

    def _suppressed_users(self) -> set[str]:
        suppressions = self.voice_repository.list_suppressions()
        return {str(s.get("userId")) for s in suppressions}

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.config import Settings
from app.services.voice_recovery_service import VoiceRecoveryService
from app.store.in_memory import InMemoryStore


class _FakeSupportService:
    def __init__(self) -> None:
        self.tickets: list[dict[str, Any]] = []

    def create_ticket(
        self,
        *,
        user_id: str | None,
        session_id: str,
        issue: str,
        priority: str = "normal",
    ) -> dict[str, Any]:
        payload = {
            "userId": user_id,
            "sessionId": session_id,
            "issue": issue,
            "priority": priority,
        }
        self.tickets.append(payload)
        return payload


class _FakeNotificationService:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def send_voice_recovery_followup(
        self,
        *,
        user_id: str,
        call_id: str,
        message: str,
        disposition: str,
    ) -> dict[str, Any]:
        payload = {
            "userId": user_id,
            "callId": call_id,
            "message": message,
            "disposition": disposition,
        }
        self.rows.append(payload)
        return payload


class _SuperUSuccess:
    enabled = True

    def start_outbound_call(self, **_kwargs: Any) -> dict[str, Any]:
        return {"call_id": "superu_call_123", "status": "queued"}

    def fetch_call_logs(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return []


class _SuperUFailure:
    enabled = True

    def start_outbound_call(self, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("provider failure")

    def fetch_call_logs(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return []


def _seed_user_and_cart(store: InMemoryStore, *, user_id: str, minutes_old: int = 45) -> None:
    now = store.iso_now()
    store.users_by_id[user_id] = {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "name": "Voice Shopper",
        "passwordHash": "hash",
        "role": "customer",
        "createdAt": now,
        "updatedAt": now,
        "lastLoginAt": now,
        "phone": "+15550003333",
        "timezone": "UTC",
    }
    store.user_ids_by_email[f"{user_id}@example.com"] = user_id

    cart_id = store.next_id("cart")
    store.carts_by_id[cart_id] = {
        "id": cart_id,
        "userId": user_id,
        "sessionId": "session_voice",
        "items": [
            {
                "itemId": store.next_id("item"),
                "productId": "prod_001",
                "variantId": "var_001",
                "name": "Running Shoes Pro",
                "price": 129.99,
                "quantity": 1,
                "image": "https://cdn.example.com/products/prod_001/main.jpg",
            }
        ],
        "subtotal": 129.99,
        "tax": 10.40,
        "shipping": 5.99,
        "discount": 0.0,
        "total": 146.38,
        "itemCount": 1,
        "currency": "USD",
        "appliedDiscount": None,
        "createdAt": now,
        "updatedAt": (store.utc_now() - timedelta(minutes=minutes_old)).isoformat(),
    }


def _service(
    *,
    superu_client: Any,
    support_service: _FakeSupportService | None = None,
    notification_service: _FakeNotificationService | None = None,
) -> VoiceRecoveryService:
    store = InMemoryStore()
    user_id = store.next_id("user")
    _seed_user_and_cart(store, user_id=user_id)
    support = support_service or _FakeSupportService()
    notifications = notification_service or _FakeNotificationService()
    service = VoiceRecoveryService(
        store=store,
        settings=Settings(superu_enabled=True, superu_api_key="superu-key"),
        superu_client=superu_client,
        support_service=support,
        notification_service=notifications,
    )
    service.update_settings(
        {
            "enabled": True,
            "abandonmentMinutes": 30,
            "assistantId": "assistant_123",
            "fromPhoneNumber": "+15550004444",
            "maxCallsPerDay": 50,
            "maxCallsPerUserPerDay": 5,
            "dailyBudgetUsd": 100.0,
            "quietHoursStart": 0,
            "quietHoursEnd": 0,
        }
    )
    return service


def test_voice_recovery_processes_abandoned_cart_successfully() -> None:
    service = _service(superu_client=_SuperUSuccess())
    result = service.process_due_work()
    assert result["enqueued"] >= 1
    assert int(result["processed"]["completed"]) >= 1

    calls = service.list_calls(limit=10)
    assert len(calls) >= 1
    assert calls[0]["providerCallId"] == "superu_call_123"

    jobs = service.list_jobs(limit=10, status="completed")
    assert len(jobs) >= 1


def test_voice_recovery_dead_letters_after_max_attempts() -> None:
    service = _service(superu_client=_SuperUFailure())
    service.update_settings({"maxAttemptsPerCart": 1})
    result = service.process_due_work()
    assert int(result["processed"]["deadLetter"]) >= 1

    jobs = service.list_jobs(limit=10, status="dead_letter")
    assert len(jobs) >= 1

    alerts = service.list_alerts(limit=50)
    assert any(alert["code"] == "VOICE_DEAD_LETTER" for alert in alerts)


def test_voice_recovery_kill_switch_cancels_due_jobs() -> None:
    service = _service(superu_client=_SuperUSuccess())
    service.update_settings({"killSwitch": True})
    result = service.process_due_work()
    assert int(result["processed"]["cancelled"]) >= 1
    alerts = service.list_alerts(limit=20)
    assert any(alert["code"] == "VOICE_KILL_SWITCH_ACTIVE" for alert in alerts)


def test_voice_recovery_poll_updates_terminal_and_applies_followup_actions() -> None:
    support = _FakeSupportService()
    notifications = _FakeNotificationService()
    service = _service(
        superu_client=_SuperUSuccess(),
        support_service=support,
        notification_service=notifications,
    )

    first = service.process_due_work()
    assert int(first["processed"]["completed"]) >= 1
    calls = service.list_calls(limit=10)
    assert len(calls) >= 1
    call_id = str(calls[0]["id"])

    class _PollingClient(_SuperUSuccess):
        def fetch_call_logs(self, **_kwargs: Any) -> list[dict[str, Any]]:
            return [{"status": "completed", "outcome": "requested_callback"}]

    service.superu_client = _PollingClient()
    polled = service._poll_provider_updates(now=service.store.utc_now())
    assert polled >= 1

    updated = next(call for call in service.list_calls(limit=10) if call["id"] == call_id)
    assert updated["status"] == "completed"
    assert updated["outcome"] == "requested_callback"
    assert len(support.tickets) >= 1
    assert len(notifications.rows) >= 1


def test_voice_recovery_suppression_roundtrip() -> None:
    service = _service(superu_client=_SuperUSuccess())
    user_id = next(
        row["id"]
        for row in service.store.users_by_id.values()
        if row.get("role") == "customer"
    )
    suppressed = service.suppress_user(user_id=user_id, reason="manual_dnc")
    assert suppressed["userId"] == user_id
    assert user_id in {row["userId"] for row in service.list_suppressions()}

    service.unsuppress_user(user_id=user_id)
    assert user_id not in {row["userId"] for row in service.list_suppressions()}

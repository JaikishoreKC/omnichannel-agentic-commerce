from __future__ import annotations

import json
from copy import deepcopy
from datetime import timedelta
from typing import Any

from app.core.config import Settings
from app.services.voice_recovery_service import VoiceRecoveryService
from app.repositories.voice_repository import VoiceRepository
from app.repositories.auth_repository import AuthRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.core.utils import utc_now, iso_now, generate_id


class _FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
    def get(self, key: str) -> Any:
        return self.store.get(key)
    def delete(self, key: str) -> None:
        self.store.pop(key, None)
    def scan_iter(self, match: str = "*") -> Any:
        prefix = match.replace("*", "")
        for k in self.store:
            if k.startswith(prefix):
                yield k

class _FakeMongoCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
    def find(self, filter: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> Any:
        from copy import deepcopy
        def match_doc(doc, f):
            if not f: return True
            for k, v in f.items():
                if doc.get(k) != v: return False
            return True
        results = [deepcopy(doc) for doc in self.docs if match_doc(doc, filter)]
        class FakeCursor(list):
            def sort(self, key_or_list, direction=1):
                if isinstance(key_or_list, list):
                    # Handle multiple sort keys, apply in reverse order
                    for field, d in reversed(key_or_list):
                        super().sort(key=lambda x: x.get(str(field)), reverse=(d == -1))
                else:
                    # Single sort key
                    super().sort(key=lambda x: x.get(str(key_or_list)), reverse=(direction == -1))
                return self
            def limit(self, n: int) -> "FakeCursor":
                return FakeCursor(self[:n])
        return FakeCursor(results)

    def find_one(self, filter: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        if filter is None:
            filter = {}
        res = self.find(filter)
        sort = kwargs.get("sort")
        if sort:
            # Apply sort using the FakeCursor's sort method
            res = res.sort(sort)
        return res[0] if res else None

    def insert_one(self, doc: dict[str, Any]) -> Any:
        self.docs.append(doc)
        class Res: inserted_id = doc.get("id", "new")
        return Res()

    def update_one(self, filter, update, upsert=False):
        found_idx = -1
        def match_doc(d, f):
            if not f: return True
            for k, v in f.items():
                if d.get(k) != v: return False
            return True
        for i, d in enumerate(self.docs):
            if match_doc(d, filter):
                found_idx = i
                break
        if found_idx == -1 and upsert:
            new_doc = {**filter}
            if "$set" in update:
                new_doc.update(deepcopy(update["$set"]))
            self.docs.append(new_doc)
            class ResUpsert: matched_count = 0; upserted_id = "new"
            return ResUpsert()
        elif found_idx != -1:
            if "$set" in update:
                self.docs[found_idx].update(deepcopy(update["$set"]))
            class ResMatch: matched_count = 1; upserted_id = None
            return ResMatch()
        class ResNoMatch: matched_count = 0; upserted_id = None
        return ResNoMatch()
    def delete_one(self, filter):
        doc = self.find_one(filter)
        if doc: self.docs.remove(doc)
        class Res: deleted_count = 1 if doc else 0
        return Res()
    def count_documents(self, filter):
        return len(self.find(filter))

class _FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeMongoCollection] = {}
    def __getitem__(self, name: str) -> _FakeMongoCollection:
        if name not in self.collections:
            self.collections[name] = _FakeMongoCollection()
        return self.collections[name]

class _FakeMongoClient:
    def __init__(self):
        self._db = _FakeDatabase()
    def get_default_database(self) -> _FakeDatabase:
        return self._db
    def __getitem__(self, item: str) -> _FakeDatabase:
        return self._db

def _fake_managers() -> tuple[MongoClientManager, RedisClientManager]:
    mongo = MongoClientManager(uri="mongodb://localhost", enabled=True)
    mongo._client = _FakeMongoClient()
    redis = RedisClientManager(url="redis://localhost", enabled=True)
    redis._client = _FakeRedisClient()
    return mongo, redis


class _FakeSupportService:
    def __init__(self) -> None:
        self.tickets: list[dict[str, Any]] = []
    def create_ticket(self, *, user_id: str | None, session_id: str, issue: str, priority: str = "normal") -> dict[str, Any]:
        payload = {"userId": user_id, "sessionId": session_id, "issue": issue, "priority": priority}
        self.tickets.append(payload)
        return payload

class _FakeNotificationService:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
    def send_voice_recovery_followup(self, *, user_id: str, call_id: str, message: str, disposition: str) -> dict[str, Any]:
        payload = {"userId": user_id, "callId": call_id, "message": message, "disposition": disposition}
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


def _seed_user_and_cart(
    auth_repo: AuthRepository, 
    cart_repo: CartRepository, 
    *, 
    user_id: str, 
    minutes_old: int = 45
) -> None:
    now = iso_now()
    user = {
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
    auth_repo.create_user(user)

    cart_id = generate_id("cart")
    cart = {
        "id": cart_id,
        "userId": user_id,
        "sessionId": "session_voice",
        "items": [
            {
                "itemId": generate_id("item"),
                "productId": "prod_001",
                "variantId": "var_001",
                "name": "Running Shoes Pro",
                "price": 129.99,
                "quantity": 1,
            }
        ],
        "subtotal": 129.99,
        "tax": 10.40,
        "shipping": 5.99,
        "discount": 0.0,
        "total": 146.38,
        "itemCount": 1,
        "currency": "USD",
        "createdAt": now,
        "updatedAt": (utc_now() - timedelta(minutes=minutes_old)).isoformat(),
    }
    cart_repo.create(cart)


def _service(
    *,
    superu_client: Any,
    support_service: _FakeSupportService | None = None,
    notification_service: _FakeNotificationService | None = None,
) -> VoiceRecoveryService:
    mongo, redis = _fake_managers()
    voice_repo = VoiceRepository(mongo_manager=mongo)
    auth_repo = AuthRepository(mongo_manager=mongo, redis_manager=redis)
    cart_repo = CartRepository(mongo_manager=mongo, redis_manager=redis)
    order_repo = OrderRepository(mongo_manager=mongo)
    
    user_id = generate_id("user")
    _seed_user_and_cart(auth_repo, cart_repo, user_id=user_id)
    
    support = support_service or _FakeSupportService()
    notifications = notification_service or _FakeNotificationService()
    
    service = VoiceRecoveryService(
        settings=Settings(superu_enabled=True, superu_api_key="superu-key"),
        superu_client=superu_client,
        support_service=support,
        notification_service=notifications,
        voice_repository=voice_repo,
        user_repository=auth_repo,
        cart_repository=cart_repo,
        order_repository=order_repo,
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
    assert calls[0].get("providerCallId") == "superu_call_123"


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


def test_voice_recovery_suppression_roundtrip() -> None:
    service = _service(superu_client=_SuperUSuccess())
    # Find customers from the repo directly
    users = service.user_repository.mongo_manager.client.get_default_database()["users"].docs
    user_id = next(row["id"] for row in users if row.get("role") == "customer")
    
    suppressed = service.suppress_user(user_id=user_id, reason="manual_dnc")
    assert suppressed["userId"] == user_id
    assert user_id in {row["userId"] for row in service.list_suppressions()}

    service.unsuppress_user(user_id=user_id)
    assert user_id not in {row["userId"] for row in service.list_suppressions()}


def test_voice_recovery_ingests_provider_callback_idempotently() -> None:
    service = _service(superu_client=_SuperUSuccess())
    processed = service.process_due_work()
    assert int(processed["processed"]["completed"]) >= 1

    call = service.list_calls(limit=1)[0]
    provider_call_id = str(call["providerCallId"])
    payload = {
        "event_id": "evt_001",
        "call_id": provider_call_id,
        "status": "completed",
        "outcome": "converted",
    }

    first = service.ingest_provider_callback(payload=payload)
    assert first["accepted"] is True
    assert first["matched"] is True
    assert first["idempotent"] is False

    second = service.ingest_provider_callback(payload=payload)
    assert second["accepted"] is True
    assert second["idempotent"] is True

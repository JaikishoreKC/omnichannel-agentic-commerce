from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.repositories.auth_repository import AuthRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.session_repository import SessionRepository
from app.store.in_memory import InMemoryStore
from app.core.utils import utc_now, iso_now


class _FakeCursor(list[dict[str, Any]]):
    def sort(self, field: str, direction: int) -> "_FakeCursor":
        reverse = direction < 0
        return _FakeCursor(sorted(self, key=lambda row: row.get(field, ""), reverse=reverse))


class _FakeCollection:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def update_one(self, filt: dict[str, Any], update: dict[str, Any], upsert: bool) -> None:
        target = self.find_one(filt)
        if target is None:
            if not upsert:
                return
            target = dict(filt)
            self.rows.append(target)
        target.update(deepcopy(update.get("$set", {})))

    def find_one(self, filt: dict[str, Any]) -> dict[str, Any] | None:
        for row in self.rows:
            if all(row.get(key) == value for key, value in filt.items()):
                return row
        return None

    def delete_one(self, filt: dict[str, Any]) -> None:
        self.rows = [row for row in self.rows if not all(row.get(key) == value for key, value in filt.items())]

    def find(self, filt: dict[str, Any]) -> _FakeCursor:
        matches = [row for row in self.rows if all(row.get(key) == value for key, value in filt.items())]
        return _FakeCursor(deepcopy(matches))

    def count_documents(self, filt: dict[str, Any]) -> int:
        return len([row for row in self.rows if all(row.get(key) == value for key, value in filt.items())])


class _FakeMongoDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeCollection] = {}

    def __getitem__(self, name: str) -> _FakeCollection:
        if name not in self.collections:
            self.collections[name] = _FakeCollection()
        return self.collections[name]


class _FakeMongoClient:
    def __init__(self) -> None:
        self.db = _FakeMongoDatabase()

    def get_default_database(self) -> _FakeMongoDatabase:
        return self.db

    def __getitem__(self, _name: str) -> _FakeMongoDatabase:
        return self.db


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


def _managers() -> tuple[MongoClientManager, RedisClientManager]:
    mongo = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=True)
    redis = RedisClientManager(url="redis://localhost:6379/0", enabled=True)
    mongo._client = _FakeMongoClient()
    redis._client = _FakeRedisClient()
    return mongo, redis


def test_auth_repository_external_fallbacks_and_revocation() -> None:
    mongo, redis = _managers()
    repo = AuthRepository(mongo_manager=mongo, redis_manager=redis)

    user = {
        "id": "user_ext_1",
        "email": "external@example.com",
        "name": "External",
        "passwordHash": "hash",
        "role": "customer",
        "createdAt": iso_now(),
        "updatedAt": iso_now(),
        "lastLoginAt": iso_now(),
    }
    redis.client.set("user:id:user_ext_1", json.dumps(user), ex=3600)
    redis.client.set("user:email:external@example.com", json.dumps(user), ex=3600)

    by_id = repo.get_user_by_id("user_ext_1")
    assert by_id is not None
    assert by_id["email"] == "external@example.com"

    # Force mongo fallback for email lookup.
    redis.client.delete("user:email:mongo@example.com")
    mongo_user = {
        "userId": "user_ext_2",
        "id": "user_ext_2",
        "email": "mongo@example.com",
        "name": "Mongo External",
        "passwordHash": "hash",
        "role": "customer",
        "createdAt": iso_now(),
        "updatedAt": iso_now(),
        "lastLoginAt": iso_now(),
        "_id": "oid",
    }
    mongo.client.get_default_database()["users"].rows.append(mongo_user)
    by_email = repo.get_user_by_email("mongo@example.com")
    assert by_email is not None
    assert by_email["id"] == "user_ext_2"

    # Invalid redis JSON should fall through to mongo for refresh tokens.
    token_hash = hashlib.sha256("tok_1".encode("utf-8")).hexdigest()
    redis.client.set(f"refresh:{token_hash}", "{bad-json", ex=3600)
    mongo.client.get_default_database()["refresh_tokens"].rows.append(
        {"tokenHash": token_hash, "userId": "user_ext_2", "createdAt": iso_now(), "_id": "oid2"}
    )
    refresh = repo.get_refresh_token("tok_1")
    assert refresh is not None
    assert refresh["userId"] == "user_ext_2"

    repo.revoke_refresh_token("tok_1")
    assert repo.get_refresh_token("tok_1") is None
    assert mongo.client.get_default_database()["refresh_tokens"].find_one({"tokenHash": token_hash}) is None


def test_session_repository_external_fallbacks_delete_and_count() -> None:
    mongo, redis = _managers()
    repo = SessionRepository(mongo_manager=mongo, redis_manager=redis)

    redis_payload = {
        "id": "session_ext_1",
        "userId": None,
        "channel": "web",
        "createdAt": iso_now(),
        "lastActivity": iso_now(),
        "expiresAt": (utc_now() + timedelta(minutes=30)).isoformat() if "timedelta" in globals() else iso_now(),
        "context": {},
    }
    # Fix for missing timedelta in test scope above
    from datetime import timedelta
    redis_payload["expiresAt"] = (utc_now() + timedelta(minutes=30)).isoformat()

    redis.client.set("session:session_ext_1", json.dumps(redis_payload), ex=3600)
    from_redis = repo.get("session_ext_1")
    assert from_redis is not None
    assert from_redis["id"] == "session_ext_1"

    repo.delete("session_ext_1")
    assert repo.get("session_ext_1") is None
    assert repo.count() == 0


def test_order_repository_external_fallbacks_and_idempotency() -> None:
    mongo, _redis = _managers()
    repo = OrderRepository(mongo_manager=mongo)

    order_payload = {
        "orderId": "order_ext_1",
        "id": "order_ext_1",
        "userId": "user_ext_9",
        "status": "confirmed",
        "items": [],
        "subtotal": 0.0,
        "tax": 0.0,
        "shipping": 0.0,
        "discount": 0.0,
        "total": 0.0,
        "shippingAddress": {},
        "payment": {},
        "timeline": [],
        "tracking": {"updates": []},
        "estimatedDelivery": iso_now(),
        "createdAt": iso_now(),
        "updatedAt": iso_now(),
        "_id": "oid",
    }
    mongo.client.get_default_database()["orders"].rows.append(order_payload)

    loaded = repo.get("order_ext_1")
    assert loaded is not None
    assert loaded["id"] == "order_ext_1"

    by_user = repo.list_by_user("user_ext_9")
    assert len(by_user) == 1
    assert by_user[0]["id"] == "order_ext_1"

    all_orders = repo.list_all()
    assert len(all_orders) >= 1

    mongo.client.get_default_database()["idempotency_keys"].rows.append(
        {"key": "user_ext_9:key_a", "orderId": "order_ext_1", "_id": "oid2"}
    )
    assert repo.get_idempotent("user_ext_9:key_a") == "order_ext_1"
    repo.set_idempotent(key="user_ext_9:key_b", order_id="order_ext_2")
    assert repo.get_idempotent("user_ext_9:key_b") == "order_ext_2"

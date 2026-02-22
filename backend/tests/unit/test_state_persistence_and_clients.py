from __future__ import annotations

import json
import types
from typing import Any

import pytest

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.infrastructure.state_persistence import StatePersistence
from app.store.in_memory import InMemoryStore


class _FakeAdmin:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def command(self, value: str) -> dict[str, int]:
        if self.should_fail:
            raise RuntimeError("ping failed")
        if value != "ping":
            raise RuntimeError("unexpected command")
        return {"ok": 1}


class _FakeCollection:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        key = str(query.get("_id"))
        row = self.rows.get(key)
        return dict(row) if row is not None else None

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool) -> None:
        assert upsert is True
        key = str(query.get("_id"))
        row = self.rows.get(key, {"_id": key})
        row.update(update.get("$set", {}))
        self.rows[key] = row


class _FakeMongoDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeCollection] = {}

    def __getitem__(self, name: str) -> _FakeCollection:
        if name not in self.collections:
            self.collections[name] = _FakeCollection()
        return self.collections[name]


class _FakeMongoClient:
    def __init__(self, should_fail_ping: bool = False, has_default_db: bool = True) -> None:
        self.admin = _FakeAdmin(should_fail=should_fail_ping)
        self.default_db = _FakeMongoDatabase() if has_default_db else None
        self.named_dbs: dict[str, _FakeMongoDatabase] = {}

    def get_default_database(self) -> _FakeMongoDatabase | None:
        return self.default_db

    def __getitem__(self, name: str) -> _FakeMongoDatabase:
        if name not in self.named_dbs:
            self.named_dbs[name] = _FakeMongoDatabase()
        return self.named_dbs[name]


class _FakeRedisPipeline:
    def __init__(self, parent: "_FakeRedisClient") -> None:
        self.parent = parent
        self.ops: list[tuple[str, str, int | None]] = []

    def set(self, key: str, value: str, ex: int | None = None) -> "_FakeRedisPipeline":
        self.ops.append((key, value, ex))
        return self

    def execute(self) -> list[bool]:
        for key, value, ex in self.ops:
            self.parent.set(key, value, ex=ex)
        return [True for _ in self.ops]


class _FakeRedisClient:
    def __init__(self, should_fail_ping: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.should_fail_ping = should_fail_ping

    def ping(self) -> bool:
        if self.should_fail_ping:
            raise RuntimeError("redis ping failed")
        return True

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def pipeline(self) -> _FakeRedisPipeline:
        return _FakeRedisPipeline(self)


def test_mongo_client_manager_connect_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(MongoClient=lambda *_a, **_k: _FakeMongoClient())
    monkeypatch.setitem(__import__("sys").modules, "pymongo", fake_module)

    manager = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=True)
    manager.connect()
    assert manager.status == "connected"
    assert manager.error is None
    assert manager.client is not None

    fake_fail_module = types.SimpleNamespace(
        MongoClient=lambda *_a, **_k: _FakeMongoClient(should_fail_ping=True)
    )
    monkeypatch.setitem(__import__("sys").modules, "pymongo", fake_fail_module)
    failing = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=True)
    failing.connect()
    assert failing.status == "unavailable"
    assert failing.error is not None

    disabled = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=False)
    disabled.connect()
    assert disabled.status == "disabled"


def test_redis_client_manager_connect_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(from_url=lambda *_a, **_k: _FakeRedisClient())
    monkeypatch.setitem(__import__("sys").modules, "redis", fake_module)

    manager = RedisClientManager(url="redis://localhost:6379/0", enabled=True)
    manager.connect()
    assert manager.status == "connected"
    assert manager.error is None
    assert manager.client is not None

    fake_fail_module = types.SimpleNamespace(
        from_url=lambda *_a, **_k: _FakeRedisClient(should_fail_ping=True)
    )
    monkeypatch.setitem(__import__("sys").modules, "redis", fake_fail_module)
    failing = RedisClientManager(url="redis://localhost:6379/0", enabled=True)
    failing.connect()
    assert failing.status == "unavailable"
    assert failing.error is not None

    disabled = RedisClientManager(url="redis://localhost:6379/0", enabled=False)
    disabled.connect()
    assert disabled.status == "disabled"


def test_state_persistence_save_and_load_roundtrip() -> None:
    store = InMemoryStore()
    mongo_manager = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=True)
    redis_manager = RedisClientManager(url="redis://localhost:6379/0", enabled=True)
    mongo_manager._client = _FakeMongoClient()
    redis_manager._client = _FakeRedisClient()
    persistence = StatePersistence(mongo_manager=mongo_manager, redis_manager=redis_manager)

    assert persistence.enabled is True
    assert persistence.save(store) is True

    # Validate singleton state document exists.
    db = mongo_manager.client.get_default_database()
    row = db["runtime_state"].find_one({"_id": "singleton"})
    assert row is not None
    assert isinstance(row.get("state"), dict)
    assert isinstance(row.get("updatedAt"), str)

    # Validate redis mirror for sessions was written.
    session_id = store.next_id("session")
    store.sessions_by_id[session_id] = {
        "id": session_id,
        "expiresAt": store.iso_now(),
        "context": {},
    }
    persistence.save(store)
    key = f"session:{session_id}"
    cached = redis_manager.client.get(key)
    assert cached is not None
    assert json.loads(cached)["id"] == session_id

    # Load into a fresh store from saved runtime state.
    fresh = InMemoryStore()
    fresh.users_by_id.clear()
    fresh.user_ids_by_email.clear()
    assert persistence.load(fresh) is True
    assert len(fresh.products_by_id) >= 1


def test_state_persistence_handles_disabled_or_bad_payloads() -> None:
    store = InMemoryStore()
    mongo_manager = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=False)
    redis_manager = RedisClientManager(url="redis://localhost:6379/0", enabled=False)
    persistence = StatePersistence(mongo_manager=mongo_manager, redis_manager=redis_manager)
    assert persistence.enabled is False
    assert persistence.save(store) is False
    assert persistence.load(store) is False

    # Connected mongo with malformed rows.
    mongo_connected = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=True)
    redis_connected = RedisClientManager(url="redis://localhost:6379/0", enabled=True)
    mongo_connected._client = _FakeMongoClient()
    redis_connected._client = _FakeRedisClient()
    db = mongo_connected.client.get_default_database()
    db["runtime_state"].rows["singleton"] = {"_id": "singleton", "state": "bad"}
    persistence2 = StatePersistence(mongo_manager=mongo_connected, redis_manager=redis_connected)
    assert persistence2.load(store) is False

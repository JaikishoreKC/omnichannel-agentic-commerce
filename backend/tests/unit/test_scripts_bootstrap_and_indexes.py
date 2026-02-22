from __future__ import annotations

from typing import Any

import pytest

from app.scripts import bootstrap_db, create_indexes


class _FakeAdmin:
    def __init__(self, *, fail_ping: bool = False) -> None:
        self.fail_ping = fail_ping

    def command(self, value: str) -> dict[str, int]:
        if self.fail_ping:
            raise RuntimeError("ping failed")
        if value != "ping":
            raise RuntimeError("unexpected command")
        return {"ok": 1}


class _FakeCollection:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def update_one(self, filt: dict[str, Any], update: dict[str, Any], upsert: bool) -> None:
        assert upsert is True
        existing = next(
            (
                row
                for row in self.rows
                if all(row.get(key) == value for key, value in filt.items())
            ),
            None,
        )
        if existing is None:
            existing = dict(filt)
            self.rows.append(existing)
        existing.update(update.get("$set", {}))


class _FakeDB:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeCollection] = {}

    def __getitem__(self, name: str) -> _FakeCollection:
        if name not in self.collections:
            self.collections[name] = _FakeCollection()
        return self.collections[name]


class _FakeMongoClient:
    def __init__(self, *, fail_ping: bool = False) -> None:
        self.admin = _FakeAdmin(fail_ping=fail_ping)
        self.db = _FakeDB()
        self.closed = False

    def get_default_database(self) -> _FakeDB:
        return self.db

    def __getitem__(self, _name: str) -> _FakeDB:
        return self.db

    def close(self) -> None:
        self.closed = True


def test_connect_with_retry_success_after_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_mongo_client(*_args: Any, **_kwargs: Any) -> _FakeMongoClient:
        calls["count"] += 1
        return _FakeMongoClient(fail_ping=calls["count"] == 1)

    monkeypatch.setattr(create_indexes, "MongoClient", fake_mongo_client)
    monkeypatch.setattr(create_indexes.time, "sleep", lambda _s: None)

    client = create_indexes._connect_with_retry(
        uri="mongodb://localhost:27017/commerce",
        retries=3,
        retry_delay=0.01,
        timeout_ms=500,
    )
    assert isinstance(client, _FakeMongoClient)
    assert calls["count"] == 2


def test_connect_with_retry_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(create_indexes, "MongoClient", lambda *_a, **_k: _FakeMongoClient(fail_ping=True))
    monkeypatch.setattr(create_indexes.time, "sleep", lambda _s: None)

    with pytest.raises(RuntimeError):
        create_indexes._connect_with_retry(
            uri="mongodb://localhost:27017/commerce",
            retries=2,
            retry_delay=0.01,
            timeout_ms=500,
        )


def test_create_indexes_run_uses_connector_and_closes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeMongoClient()
    monkeypatch.setattr(create_indexes, "_connect_with_retry", lambda **_kwargs: fake_client)
    monkeypatch.setattr(
        create_indexes,
        "ensure_mongo_indexes",
        lambda **_kwargs: {"users": ["users_user_id_unique"], "orders": ["orders_order_id_unique"]},
    )

    summary = create_indexes.run(
        mongo_uri="mongodb://localhost:27017/commerce",
        database="commerce",
        retries=1,
        retry_delay=0.01,
        timeout_ms=500,
    )
    assert summary["collections"] == 2
    assert summary["indexes"]["users"] == ["users_user_id_unique"]
    assert fake_client.closed is True


def test_bootstrap_upsert_helpers_skip_invalid_rows() -> None:
    collection = _FakeCollection()
    count_map = bootstrap_db._upsert_map(
        collection=collection,
        key_field="userId",
        rows={"ok": {"id": "user_1", "name": "A"}, "bad": "skip"},  # type: ignore[arg-type]
    )
    assert count_map == 1

    count_list = bootstrap_db._upsert_list(
        collection=collection,
        unique_field="messageId",
        rows=[{"id": "msg_1"}, {"id": ""}, "skip"],  # type: ignore[list-item]
        key_mapper=lambda row: row.get("id"),
    )
    assert count_list == 1


def test_bootstrap_run_seeds_state_and_runtime_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeMongoClient()
    monkeypatch.setattr(bootstrap_db, "_connect_with_retry", lambda **_kwargs: fake_client)
    monkeypatch.setattr(
        bootstrap_db,
        "ensure_mongo_indexes",
        lambda **_kwargs: {"users": ["users_user_id_unique"]},
    )
    monkeypatch.setattr(bootstrap_db, "resolve_database", lambda _client, _db: fake_client.db)

    summary = bootstrap_db.run(
        mongo_uri="mongodb://localhost:27017/commerce",
        database="commerce",
        retries=1,
        retry_delay=0.01,
        timeout_ms=500,
        seed_runtime_state=True,
    )
    assert summary["collections"] == 1
    assert summary["seedRuntimeState"] is True
    assert summary["seeded"]["users"] >= 1
    assert summary["seeded"]["products"] >= 1
    assert summary["seeded"]["inventory"] >= 1
    assert summary["seeded"]["sessions"] >= 0
    assert summary["seeded"]["refresh_tokens"] >= 0
    assert summary["seeded"]["idempotency_keys"] >= 0
    assert summary["seeded"]["interactions"] >= 0
    assert summary["seeded"]["support_tickets"] >= 0
    assert summary["seeded"]["notifications"] >= 0
    assert fake_client.closed is True

    runtime_state_rows = fake_client.db["runtime_state"].rows
    assert any(row.get("_id") == "singleton" for row in runtime_state_rows)

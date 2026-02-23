from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class SessionRepository:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.store = store
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def create(self, session: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.sessions_by_id[session["id"]] = deepcopy(session)
        self._write_through(session)
        return deepcopy(session)

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self.store.lock:
            session = self.store.sessions_by_id.get(session_id)
            if session is not None:
                return deepcopy(session)

        cached = self._read_from_redis(session_id)
        if cached is not None:
            with self.store.lock:
                self.store.sessions_by_id[session_id] = deepcopy(cached)
            return deepcopy(cached)

        persisted = self._read_from_mongo(session_id)
        if persisted is not None:
            with self.store.lock:
                self.store.sessions_by_id[session_id] = deepcopy(persisted)
            self._write_to_redis(persisted)
            return deepcopy(persisted)
        return None

    def update(self, session: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.sessions_by_id[session["id"]] = deepcopy(session)
        self._write_through(session)
        return deepcopy(session)

    def delete(self, session_id: str) -> None:
        with self.store.lock:
            self.store.sessions_by_id.pop(session_id, None)
        self._delete_from_redis(session_id)
        self._delete_from_mongo(session_id)

    def find_latest_for_user(self, user_id: str) -> dict[str, Any] | None:
        with self.store.lock:
            matching = [
                deepcopy(session)
                for session in self.store.sessions_by_id.values()
                if str(session.get("userId", "")) == user_id
            ]
        if matching:
            matching.sort(
                key=lambda session: (
                    str(session.get("lastActivityAt", "")),
                    str(session.get("lastActivity", "")),
                    str(session.get("createdAt", "")),
                ),
                reverse=True,
            )
            return deepcopy(matching[0])

        persisted = self._read_latest_for_user_from_mongo(user_id)
        if persisted is not None:
            with self.store.lock:
                self.store.sessions_by_id[persisted["id"]] = deepcopy(persisted)
            self._write_to_redis(persisted)
            return deepcopy(persisted)
        return None

    def count(self) -> int:
        with self.store.lock:
            cached_count = len(self.store.sessions_by_id)
        if cached_count:
            return cached_count

        collection = self._mongo_collection()
        if collection is None:
            return 0
        return int(collection.count_documents({}))

    def _write_through(self, session: dict[str, Any]) -> None:
        self._write_to_redis(session)
        self._write_to_mongo(session)

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["sessions"]

    def _redis_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _write_to_redis(self, session: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_key(session["id"]), json.dumps(session), ex=60 * 60)

    def _read_from_redis(self, session_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_key(session_id))
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def _delete_from_redis(self, session_id: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_key(session_id))

    def _write_to_mongo(self, session: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"sessionId": session["id"]},
            {"$set": {"sessionId": session["id"], **deepcopy(session)}},
            upsert=True,
        )

    def _read_from_mongo(self, session_id: str) -> dict[str, Any] | None:
        collection = self._mongo_collection()
        if collection is None:
            return None
        payload = collection.find_one({"sessionId": session_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("sessionId", None)
        return payload if isinstance(payload, dict) else None

    def _read_latest_for_user_from_mongo(self, user_id: str) -> dict[str, Any] | None:
        collection = self._mongo_collection()
        if collection is None:
            return None
        payload = collection.find_one(
            {"userId": user_id},
            sort=[("lastActivityAt", -1), ("lastActivity", -1)],
        )
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("sessionId", None)
        return payload if isinstance(payload, dict) else None

    def _delete_from_mongo(self, session_id: str) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.delete_one({"sessionId": session_id})

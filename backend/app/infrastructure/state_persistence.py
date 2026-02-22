from __future__ import annotations

import json
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class StatePersistence:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
        collection_name: str = "runtime_state",
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager
        self.collection_name = collection_name

    @property
    def enabled(self) -> bool:
        return self.mongo_manager.status == "connected"

    def load(self, store: InMemoryStore) -> bool:
        collection = self._mongo_collection()
        if collection is None:
            return False

        payload = collection.find_one({"_id": "singleton"})
        if not payload:
            return False
        state = payload.get("state")
        if not isinstance(state, dict):
            return False

        store.import_state(state)
        self._cache_sessions_to_redis(store)
        return True

    def save(self, store: InMemoryStore) -> bool:
        collection = self._mongo_collection()
        if collection is None:
            return False

        state = store.export_state()
        collection.update_one(
            {"_id": "singleton"},
            {"$set": {"state": state, "updatedAt": store.iso_now()}},
            upsert=True,
        )
        self._cache_sessions_to_redis(store)
        return True

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database[self.collection_name]

    def _cache_sessions_to_redis(self, store: InMemoryStore) -> None:
        client = self.redis_manager.client
        if client is None:
            return

        sessions = store.export_state().get("sessions_by_id", {})
        if not isinstance(sessions, dict):
            return

        pipe = client.pipeline()
        for session_id, payload in sessions.items():
            key = f"session:{session_id}"
            pipe.set(key, json.dumps(payload), ex=60 * 60)
        pipe.execute()

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class CategoryRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
        store: InMemoryStore | None = None,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager
        self.store = store

    def list_all(self) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return self._list_from_in_memory()
        rows = list(collection.find({}).sort("name", 1))
        categories: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("categoryId", None)
            if not isinstance(row, dict):
                continue
            categories.append(row)
            self._write_to_redis(row)
        return categories

    def get(self, category_id: str) -> dict[str, Any] | None:
        cached = self._read_from_redis(category_id)
        if cached is not None:
            return cached

        collection = self._mongo_collection()
        if collection is None:
            return self._read_from_in_memory(category_id)
        payload = collection.find_one({"$or": [{"categoryId": category_id}, {"slug": category_id}]})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("categoryId", None)
        if not isinstance(payload, dict):
            return None
        self._write_to_redis(payload)
        return payload

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        use_in_memory_fallback = self._mongo_collection() is None
        self._write_to_redis(payload)
        self._write_to_mongo(payload)
        if use_in_memory_fallback:
            self._write_to_in_memory(payload)
        return deepcopy(payload)

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        use_in_memory_fallback = self._mongo_collection() is None
        self._write_to_redis(payload)
        self._write_to_mongo(payload)
        if use_in_memory_fallback:
            self._write_to_in_memory(payload)
        return deepcopy(payload)

    def delete(self, category_id: str) -> None:
        use_in_memory_fallback = self._mongo_collection() is None
        # We need the slug to properly clear Redis cache
        collection = self._mongo_collection()
        slug_value = ""
        if collection is not None:
            row = collection.find_one({"$or": [{"categoryId": category_id}, {"slug": category_id}]})
            if row:
                slug_value = str(row.get("slug", ""))

        self._delete_from_redis(category_id)
        if slug_value and slug_value != category_id:
            self._delete_from_redis(slug_value)
        self._delete_from_mongo(category_id)
        if use_in_memory_fallback:
            self._delete_from_in_memory(category_id)

    def active_slugs(self) -> set[str]:
        rows = self.list_all()
        return {
            str(row.get("slug", "")).strip().lower()
            for row in rows
            if str(row.get("status", "active")).lower() == "active"
        }

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["categories"]

    def _redis_key(self, category_id: str) -> str:
        return f"category:{category_id}"

    def _write_to_redis(self, payload: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        category_id = str(payload["id"])
        slug = str(payload.get("slug", "")).strip()
        encoded = json.dumps(payload)
        client.set(self._redis_key(category_id), encoded, ex=60 * 60)
        if slug and slug != category_id:
            client.set(self._redis_key(slug), encoded, ex=60 * 60)

    def _read_from_redis(self, category_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_key(category_id))
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def _delete_from_redis(self, category_id: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_key(category_id))

    def _write_to_mongo(self, payload: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"categoryId": payload["id"]},
            {"$set": {"categoryId": payload["id"], **deepcopy(payload)}},
            upsert=True,
        )

    def _delete_from_mongo(self, category_id: str) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.delete_one({"$or": [{"categoryId": category_id}, {"slug": category_id}]})

    def _write_to_in_memory(self, payload: dict[str, Any]) -> None:
        if self.store is None:
            return
        category_id = str(payload.get("id", "")).strip()
        if not category_id:
            return
        with self.store.lock:
            self.store.categories_by_id[category_id] = deepcopy(payload)

    def _read_from_in_memory(self, category_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        key = str(category_id).strip().lower()
        with self.store.lock:
            direct = self.store.categories_by_id.get(category_id)
            if isinstance(direct, dict):
                return deepcopy(direct)
            for row in self.store.categories_by_id.values():
                if str(row.get("slug", "")).strip().lower() == key:
                    return deepcopy(row)
        return None

    def _list_from_in_memory(self) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        with self.store.lock:
            rows = [deepcopy(row) for row in self.store.categories_by_id.values() if isinstance(row, dict)]
        rows.sort(key=lambda row: str(row.get("name", "")).lower())
        return rows

    def _delete_from_in_memory(self, category_id: str) -> None:
        if self.store is None:
            return
        key = str(category_id).strip().lower()
        with self.store.lock:
            remove_keys = [
                cat_id
                for cat_id, row in self.store.categories_by_id.items()
                if str(cat_id) == category_id or str(row.get("slug", "")).strip().lower() == key
            ]
            for cat_id in remove_keys:
                self.store.categories_by_id.pop(cat_id, None)

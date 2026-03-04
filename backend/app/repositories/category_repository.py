from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
class CategoryRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def list_all(self) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
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
            return None
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
        self._write_to_redis(payload)
        self._write_to_mongo(payload)
        return deepcopy(payload)

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._write_to_redis(payload)
        self._write_to_mongo(payload)
        return deepcopy(payload)

    def delete(self, category_id: str) -> None:
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

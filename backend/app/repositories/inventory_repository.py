from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class InventoryRepository:
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

    def get(self, variant_id: str) -> dict[str, Any] | None:
        cached = self._read_from_redis(variant_id)
        if cached is not None:
            return cached

        collection = self._mongo_collection()
        if collection is None:
            return self._read_from_in_memory(variant_id)
        payload = collection.find_one({"variantId": variant_id})
        if not payload:
            return None
        payload.pop("_id", None)
        if not isinstance(payload, dict):
            return None
        self._write_to_redis(payload)
        return payload

    def upsert(self, stock: dict[str, Any]) -> dict[str, Any]:
        use_in_memory_fallback = self._mongo_collection() is None
        self._write_to_redis(stock)
        self._write_to_mongo(stock)
        if use_in_memory_fallback:
            self._write_to_in_memory(stock)
        return deepcopy(stock)

    def delete(self, variant_id: str) -> None:
        use_in_memory_fallback = self._mongo_collection() is None
        self._delete_from_redis(variant_id)
        self._delete_from_mongo(variant_id)
        if use_in_memory_fallback:
            self._delete_from_in_memory(variant_id)

    def list_by_product(self, product_id: str) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return self._list_from_in_memory(product_id)
        rows = list(collection.find({"productId": product_id}).sort("variantId", 1))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            if isinstance(row, dict):
                output.append(row)
                self._write_to_redis(row)
        return output

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["inventory"]

    def _redis_key(self, variant_id: str) -> str:
        return f"inventory:{variant_id}"

    def _write_to_redis(self, stock: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_key(str(stock["variantId"])), json.dumps(stock), ex=60 * 60)

    def _read_from_redis(self, variant_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_key(variant_id))
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def _delete_from_redis(self, variant_id: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_key(variant_id))

    def _write_to_mongo(self, stock: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"variantId": stock["variantId"]},
            {"$set": deepcopy(stock)},
            upsert=True,
        )

    def _delete_from_mongo(self, variant_id: str) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.delete_one({"variantId": variant_id})

    def _write_to_in_memory(self, stock: dict[str, Any]) -> None:
        if self.store is None:
            return
        variant_id = str(stock.get("variantId", "")).strip()
        if not variant_id:
            return
        with self.store.lock:
            self.store.inventory_by_variant[variant_id] = deepcopy(stock)

    def _read_from_in_memory(self, variant_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        with self.store.lock:
            row = self.store.inventory_by_variant.get(variant_id)
            return deepcopy(row) if isinstance(row, dict) else None

    def _delete_from_in_memory(self, variant_id: str) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.inventory_by_variant.pop(variant_id, None)

    def _list_from_in_memory(self, product_id: str) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        with self.store.lock:
            rows = [
                deepcopy(row)
                for row in self.store.inventory_by_variant.values()
                if isinstance(row, dict) and str(row.get("productId", "")) == product_id
            ]
        rows.sort(key=lambda row: str(row.get("variantId", "")))
        return rows

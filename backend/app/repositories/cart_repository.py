from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class CartRepository:
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

    def create(self, cart: dict[str, Any]) -> dict[str, Any]:
        self._write_through(cart)
        return deepcopy(cart)

    def update(self, cart: dict[str, Any]) -> dict[str, Any]:
        self._write_through(cart)
        return deepcopy(cart)

    def delete(self, cart_id: str) -> None:
        self._delete_from_redis(cart_id)
        self._delete_from_mongo(cart_id)
        self._delete_from_in_memory(cart_id)

    def get_for_user_or_session(self, *, user_id: str | None, session_id: str) -> dict[str, Any] | None:
        # Check Mongo as source of truth
        persisted = self._read_from_mongo(user_id=user_id, session_id=session_id)
        if persisted is not None:
            self._write_to_redis(persisted)
            return deepcopy(persisted)
        return None

    def clear_for_user(self, user_id: str) -> dict[str, Any] | None:
        cart = self.get_for_user_or_session(user_id=user_id, session_id="")
        if not cart:
            return None
        cart["items"] = []
        cart["appliedDiscount"] = None
        cart["status"] = "active"
        cart["updatedAt"] = "2024-01-01T00:00:00Z" # Will be updated by service usually
        self._write_through(cart)
        return deepcopy(cart)

    def get_by_id(self, cart_id: str) -> dict[str, Any] | None:
        mirrored = self._read_from_in_memory(cart_id)
        if mirrored is not None:
            return mirrored
        collection = self._mongo_collection()
        if collection is None:
            return None
        payload = collection.find_one({"cartId": cart_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("cartId", None)
        return deepcopy(payload) if isinstance(payload, dict) else None

    def list_all(self) -> list[dict[str, Any]]:
        mirrored = self._list_from_in_memory()
        if mirrored:
            return mirrored
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({}).sort("updatedAt", -1))
        carts: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("cartId", None)
            if isinstance(row, dict):
                carts.append(deepcopy(row))
        return carts

    def _write_through(self, cart: dict[str, Any]) -> None:
        self._write_to_redis(cart)
        self._write_to_mongo(cart)
        self._write_to_in_memory(cart)

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["carts"]

    def _redis_key(self, cart_id: str) -> str:
        return f"cart:{cart_id}"

    def _write_to_redis(self, cart: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_key(cart["id"]), json.dumps(cart), ex=60 * 60)

    def _write_to_mongo(self, cart: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"cartId": cart["id"]},
            {"$set": {"cartId": cart["id"], **deepcopy(cart)}},
            upsert=True,
        )

    def _delete_from_redis(self, cart_id: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_key(cart_id))

    def _delete_from_mongo(self, cart_id: str) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.delete_one({"cartId": cart_id})

    def _read_from_mongo(self, *, user_id: str | None, session_id: str) -> dict[str, Any] | None:
        collection = self._mongo_collection()
        if collection is None:
            return None

        if user_id:
            payload = collection.find_one(
                {
                    "userId": user_id,
                    "$or": [{"status": "active"}, {"status": {"$exists": False}}],
                },
                sort=[("updatedAt", -1)],
            )
        else:
            payload = collection.find_one(
                {
                    "sessionId": session_id,
                    "$and": [
                        {"$or": [{"userId": None}, {"userId": {"$exists": False}}]},
                        {"$or": [{"status": "active"}, {"status": {"$exists": False}}]},
                    ],
                },
                sort=[("updatedAt", -1)],
            )
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("cartId", None)
        return payload if isinstance(payload, dict) else None

    def _write_to_in_memory(self, cart: dict[str, Any]) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.carts_by_id[str(cart["id"])] = deepcopy(cart)

    def _read_from_in_memory(self, cart_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        with self.store.lock:
            row = self.store.carts_by_id.get(cart_id)
            return deepcopy(row) if isinstance(row, dict) else None

    def _list_from_in_memory(self) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        with self.store.lock:
            rows = list(self.store.carts_by_id.values())
        rows = [deepcopy(row) for row in rows if isinstance(row, dict)]
        rows.sort(key=lambda row: str(row.get("updatedAt", "")), reverse=True)
        return rows

    def _delete_from_in_memory(self, cart_id: str) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.carts_by_id.pop(cart_id, None)

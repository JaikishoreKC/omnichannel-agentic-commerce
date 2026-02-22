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
        store: InMemoryStore,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.store = store
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def create(self, cart: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.carts_by_id[cart["id"]] = deepcopy(cart)
        self._write_through(cart)
        return deepcopy(cart)

    def update(self, cart: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.carts_by_id[cart["id"]] = deepcopy(cart)
        self._write_through(cart)
        return deepcopy(cart)

    def get_for_user_or_session(self, *, user_id: str | None, session_id: str) -> dict[str, Any] | None:
        with self.store.lock:
            for cart in self.store.carts_by_id.values():
                if user_id and cart.get("userId") == user_id:
                    return deepcopy(cart)
                if not user_id and cart.get("sessionId") == session_id and not cart.get("userId"):
                    return deepcopy(cart)

        persisted = self._read_from_mongo(user_id=user_id, session_id=session_id)
        if persisted is not None:
            with self.store.lock:
                self.store.carts_by_id[persisted["id"]] = deepcopy(persisted)
            self._write_to_redis(persisted)
            return deepcopy(persisted)
        return None

    def clear_for_user(self, user_id: str) -> dict[str, Any] | None:
        cart = self.get_for_user_or_session(user_id=user_id, session_id="")
        if not cart:
            return None
        cart["items"] = []
        cart["appliedDiscount"] = None
        with self.store.lock:
            self.store.carts_by_id[cart["id"]] = deepcopy(cart)
        self._write_through(cart)
        return deepcopy(cart)

    def _write_through(self, cart: dict[str, Any]) -> None:
        self._write_to_redis(cart)
        self._write_to_mongo(cart)

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

    def _read_from_mongo(self, *, user_id: str | None, session_id: str) -> dict[str, Any] | None:
        collection = self._mongo_collection()
        if collection is None:
            return None

        if user_id:
            payload = collection.find_one({"userId": user_id}, sort=[("updatedAt", -1)])
        else:
            payload = collection.find_one(
                {"sessionId": session_id, "$or": [{"userId": None}, {"userId": {"$exists": False}}]},
                sort=[("updatedAt", -1)],
            )
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("cartId", None)
        return payload if isinstance(payload, dict) else None

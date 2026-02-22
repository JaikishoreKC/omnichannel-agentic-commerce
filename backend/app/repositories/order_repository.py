from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
from app.store.in_memory import InMemoryStore


class OrderRepository:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.store = store
        self.mongo_manager = mongo_manager

    def create(self, order: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.orders_by_id[order["id"]] = deepcopy(order)
        self._write_to_mongo(order)
        return deepcopy(order)

    def update(self, order: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.orders_by_id[order["id"]] = deepcopy(order)
        self._write_to_mongo(order)
        return deepcopy(order)

    def get(self, order_id: str) -> dict[str, Any] | None:
        with self.store.lock:
            order = self.store.orders_by_id.get(order_id)
            if order is not None:
                return deepcopy(order)

        collection = self._orders_collection()
        if collection is None:
            return None
        payload = collection.find_one({"orderId": order_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("orderId", None)
        with self.store.lock:
            self.store.orders_by_id[order_id] = deepcopy(payload)
        return deepcopy(payload)

    def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        with self.store.lock:
            cached = [deepcopy(order) for order in self.store.orders_by_id.values() if order.get("userId") == user_id]
        if cached:
            return cached

        collection = self._orders_collection()
        if collection is None:
            return []
        payloads = list(collection.find({"userId": user_id}).sort("createdAt", -1))
        orders: list[dict[str, Any]] = []
        for payload in payloads:
            payload.pop("_id", None)
            payload.pop("orderId", None)
            if isinstance(payload, dict):
                orders.append(payload)
                with self.store.lock:
                    self.store.orders_by_id[payload["id"]] = deepcopy(payload)
        return [deepcopy(order) for order in orders]

    def get_idempotent(self, key: str) -> str | None:
        with self.store.lock:
            order_id = self.store.idempotency_keys.get(key)
            if order_id:
                return str(order_id)

        collection = self._idempotency_collection()
        if collection is None:
            return None
        payload = collection.find_one({"key": key})
        if not payload:
            return None
        order_id = str(payload.get("orderId", ""))
        if not order_id:
            return None
        with self.store.lock:
            self.store.idempotency_keys[key] = order_id
        return order_id

    def set_idempotent(self, *, key: str, order_id: str) -> None:
        with self.store.lock:
            self.store.idempotency_keys[key] = order_id

        collection = self._idempotency_collection()
        if collection is None:
            return
        collection.update_one(
            {"key": key},
            {"$set": {"key": key, "orderId": order_id}},
            upsert=True,
        )

    def _orders_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["orders"]

    def _idempotency_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["idempotency_keys"]

    def _write_to_mongo(self, order: dict[str, Any]) -> None:
        collection = self._orders_collection()
        if collection is None:
            return
        collection.update_one(
            {"orderId": order["id"]},
            {"$set": {"orderId": order["id"], **deepcopy(order)}},
            upsert=True,
        )

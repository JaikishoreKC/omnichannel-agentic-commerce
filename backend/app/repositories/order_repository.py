from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
class OrderRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self._fallback_lock = Lock()
        self._fallback_orders: dict[str, dict[str, Any]] = {}
        self._fallback_idempotency: dict[str, str] = {}

    def create(self, order: dict[str, Any]) -> dict[str, Any]:
        order_id = str(order.get("id", "")).strip()
        if order_id:
            with self._fallback_lock:
                self._fallback_orders[order_id] = deepcopy(order)
        self._write_to_mongo(order)
        return deepcopy(order)

    def update(self, order: dict[str, Any]) -> dict[str, Any]:
        order_id = str(order.get("id", "")).strip()
        if order_id:
            with self._fallback_lock:
                self._fallback_orders[order_id] = deepcopy(order)
        self._write_to_mongo(order)
        return deepcopy(order)

    def get(self, order_id: str) -> dict[str, Any] | None:
        collection = self._orders_collection()
        if collection is None:
            with self._fallback_lock:
                payload = self._fallback_orders.get(order_id)
                return deepcopy(payload) if isinstance(payload, dict) else None
        payload = collection.find_one({"orderId": order_id})
        if not payload:
            with self._fallback_lock:
                fallback = self._fallback_orders.get(order_id)
                return deepcopy(fallback) if isinstance(fallback, dict) else None
        payload.pop("_id", None)
        payload.pop("orderId", None)
        if isinstance(payload, dict):
            with self._fallback_lock:
                self._fallback_orders[order_id] = deepcopy(payload)
        return deepcopy(payload)

    def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        collection = self._orders_collection()
        if collection is None:
            with self._fallback_lock:
                rows = [
                    deepcopy(order)
                    for order in self._fallback_orders.values()
                    if isinstance(order, dict) and str(order.get("userId", "")).strip() == user_id
                ]
            rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
            return rows
        payloads = list(collection.find({"userId": user_id}).sort("createdAt", -1))
        orders: list[dict[str, Any]] = []
        for payload in payloads:
            payload.pop("_id", None)
            payload.pop("orderId", None)
            if isinstance(payload, dict):
                orders.append(payload)
                order_id = str(payload.get("id", "")).strip()
                if order_id:
                    with self._fallback_lock:
                        self._fallback_orders[order_id] = deepcopy(payload)
        return orders

    def list_all(self) -> list[dict[str, Any]]:
        collection = self._orders_collection()
        if collection is None:
            with self._fallback_lock:
                rows = [deepcopy(order) for order in self._fallback_orders.values() if isinstance(order, dict)]
            rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
            return rows
        payloads = list(collection.find({}).sort("createdAt", -1))
        orders: list[dict[str, Any]] = []
        for payload in payloads:
            payload.pop("_id", None)
            payload.pop("orderId", None)
            if isinstance(payload, dict):
                orders.append(payload)
                order_id = str(payload.get("id", "")).strip()
                if order_id:
                    with self._fallback_lock:
                        self._fallback_orders[order_id] = deepcopy(payload)
        return orders

    def get_idempotent(self, key: str) -> str | None:
        collection = self._idempotency_collection()
        if collection is None:
            with self._fallback_lock:
                order_id = self._fallback_idempotency.get(key)
                return str(order_id) if order_id else None
        payload = collection.find_one({"key": key})
        if not payload:
            with self._fallback_lock:
                order_id = self._fallback_idempotency.get(key)
                return str(order_id) if order_id else None
        order_id = str(payload.get("orderId", ""))
        if order_id:
            with self._fallback_lock:
                self._fallback_idempotency[key] = order_id
        return order_id

    def set_idempotent(self, *, key: str, order_id: str) -> None:
        with self._fallback_lock:
            self._fallback_idempotency[key] = order_id
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

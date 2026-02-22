from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.repositories.memory_repository import MemoryRepository
from app.store.in_memory import InMemoryStore


class MemoryService:
    def __init__(self, store: InMemoryStore, memory_repository: MemoryRepository) -> None:
        self.store = store
        self.memory_repository = memory_repository

    def _default_memory(self) -> dict[str, Any]:
        return {
            "preferences": {
                "size": None,
                "brandPreferences": [],
                "categories": [],
                "priceRange": {"min": 0, "max": 0},
            },
            "interactionHistory": [],
            "productAffinities": {
                "categories": {},
                "products": {},
            },
            "updatedAt": self.store.iso_now(),
        }

    def get_memory_snapshot(self, user_id: str) -> dict[str, Any]:
        payload = self.memory_repository.get(user_id)
        if payload is None:
            payload = self._default_memory()
            self.memory_repository.upsert(user_id, payload)
        return deepcopy(payload)

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        return {"preferences": deepcopy(payload["preferences"])}

    def update_preferences(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        prefs = payload["preferences"]
        for key, value in updates.items():
            if value is not None:
                prefs[key] = value
        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)
        return {"success": True}

    def record_interaction(
        self,
        *,
        user_id: str | None,
        intent: str,
        message: str,
        response: dict[str, Any],
    ) -> None:
        if not user_id:
            return
        payload = self.get_memory_snapshot(user_id)
        history = payload["interactionHistory"]
        history.append(
            {
                "type": intent,
                "timestamp": self.store.iso_now(),
                "summary": {
                    "query": message[:180],
                    "action": intent,
                    "response": str(response.get("message", ""))[:180],
                },
            }
        )
        payload["interactionHistory"] = history[-200:]
        affinities = payload.setdefault("productAffinities", {"categories": {}, "products": {}})
        category_scores = affinities.setdefault("categories", {})
        product_scores = affinities.setdefault("products", {})

        data = response.get("data", {})
        products: list[dict[str, Any]] = []
        raw_products = data.get("products")
        if isinstance(raw_products, list):
            products.extend([item for item in raw_products if isinstance(item, dict)])

        order = data.get("order")
        if isinstance(order, dict):
            order_items = order.get("items", [])
            if isinstance(order_items, list):
                for item in order_items:
                    if not isinstance(item, dict):
                        continue
                    product_id = str(item.get("productId", ""))
                    if product_id:
                        product_scores[product_id] = int(product_scores.get(product_id, 0)) + int(
                            item.get("quantity", 1)
                        )

        for product in products:
            product_id = str(product.get("id", ""))
            category = str(product.get("category", "")).strip().lower()
            if product_id:
                product_scores[product_id] = int(product_scores.get(product_id, 0)) + 1
            if category:
                category_scores[category] = int(category_scores.get(category, 0)) + 1

        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)

    def get_history(self, *, user_id: str, limit: int = 20) -> dict[str, Any]:
        payload = self.memory_repository.get(user_id) or {}
        history = payload.get("interactionHistory", [])
        return {"history": deepcopy(history[-max(1, min(limit, 100)) :])}

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
                "stylePreferences": [],
                "colorPreferences": [],
                "priceRange": {"min": 0, "max": 0},
            },
            "interactionHistory": [],
            "productAffinities": {
                "brands": {},
                "categories": {},
                "products": {},
                "priceRanges": {},
                "features": {},
            },
            "updatedAt": self.store.iso_now(),
        }

    def get_memory_snapshot(self, user_id: str) -> dict[str, Any]:
        payload = self.memory_repository.get(user_id)
        if payload is None:
            payload = self._default_memory()
            self.memory_repository.upsert(user_id, payload)
        payload["preferences"] = self._ensure_preferences(payload.get("preferences"))
        return deepcopy(payload)

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        return {"preferences": deepcopy(payload["preferences"])}

    def update_preferences(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        prefs = self._ensure_preferences(payload.get("preferences"))
        for key, value in updates.items():
            if value is not None:
                prefs[key] = value
        payload["preferences"] = self._normalize_preferences(prefs)
        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)
        return {"success": True, "preferences": deepcopy(payload["preferences"])}

    def save_preference_updates(self, *, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        prefs = self._normalize_preferences(self._ensure_preferences(payload.get("preferences")))

        size = updates.get("size")
        if isinstance(size, str) and size.strip():
            prefs["size"] = size.strip()

        price_range = updates.get("priceRange")
        if isinstance(price_range, dict):
            current_price = prefs.get("priceRange", {"min": 0.0, "max": 0.0})
            min_value = self._coerce_float(price_range.get("min"), default=current_price.get("min", 0.0))
            max_value = self._coerce_float(price_range.get("max"), default=current_price.get("max", 0.0))
            prefs["priceRange"] = {"min": min_value, "max": max_value}

        for key in ("brandPreferences", "categories", "stylePreferences", "colorPreferences"):
            raw = updates.get(key)
            tokens = self._normalize_list(raw if isinstance(raw, list) else [raw] if raw is not None else [])
            if tokens:
                prefs[key] = self._dedupe_preserve_order([*prefs.get(key, []), *tokens])

        payload["preferences"] = prefs
        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)
        return {"success": True, "preferences": deepcopy(prefs)}

    def forget_preference(self, *, user_id: str, key: str | None, value: str | None) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        prefs = self._normalize_preferences(self._ensure_preferences(payload.get("preferences")))

        normalized_key = (key or "").strip()
        normalized_value = self._normalize_token(value) if value else ""
        list_fields = ("brandPreferences", "categories", "stylePreferences", "colorPreferences")

        if normalized_key in list_fields:
            if normalized_value:
                prefs[normalized_key] = [item for item in prefs.get(normalized_key, []) if item != normalized_value]
            else:
                prefs[normalized_key] = []
        elif normalized_key == "size":
            prefs["size"] = None
        elif normalized_key == "priceRange":
            prefs["priceRange"] = {"min": 0.0, "max": 0.0}
        elif normalized_value:
            for field in list_fields:
                prefs[field] = [item for item in prefs.get(field, []) if item != normalized_value]

        payload["preferences"] = prefs
        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)
        return {"success": True, "preferences": deepcopy(prefs)}

    def clear_preferences(self, *, user_id: str) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        payload["preferences"] = self._default_memory()["preferences"]
        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)
        return {"success": True, "preferences": deepcopy(payload["preferences"])}

    def clear_history(self, *, user_id: str) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        payload["interactionHistory"] = []
        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)
        return {"success": True}

    def clear_memory(self, *, user_id: str) -> dict[str, Any]:
        payload = self._default_memory()
        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)
        return {"success": True}

    def summarize_memory(self, *, user_id: str) -> dict[str, Any]:
        payload = self.get_memory_snapshot(user_id)
        preferences = self._normalize_preferences(self._ensure_preferences(payload.get("preferences")))
        affinities = payload.get("productAffinities", {}) if isinstance(payload, dict) else {}
        category_scores = affinities.get("categories", {}) if isinstance(affinities, dict) else {}
        brand_scores = affinities.get("brands", {}) if isinstance(affinities, dict) else {}
        top_category = None
        top_brand = None
        if isinstance(category_scores, dict) and category_scores:
            top_category = max(category_scores.items(), key=lambda item: int(item[1]))[0]
        if isinstance(brand_scores, dict) and brand_scores:
            top_brand = max(brand_scores.items(), key=lambda item: int(item[1]))[0]
        recent = payload.get("interactionHistory", []) if isinstance(payload, dict) else []

        highlights: list[str] = []
        if preferences.get("size"):
            highlights.append(f"Saved size: {preferences['size']}")
        if preferences.get("categories"):
            highlights.append(f"Preferred categories: {', '.join(preferences['categories'])}")
        if preferences.get("brandPreferences"):
            highlights.append(f"Preferred brands: {', '.join(preferences['brandPreferences'])}")
        if preferences.get("stylePreferences"):
            highlights.append(f"Style preferences: {', '.join(preferences['stylePreferences'])}")
        if preferences.get("colorPreferences"):
            highlights.append(f"Color preferences: {', '.join(preferences['colorPreferences'])}")
        if top_category:
            highlights.append(f"Top affinity category: {top_category}")
        if top_brand:
            highlights.append(f"Top affinity brand: {top_brand}")
        if not highlights:
            highlights.append("No explicit preferences saved yet.")

        return {
            "preferences": preferences,
            "highlights": highlights,
            "recentInteractions": deepcopy(recent[-5:]),
            "updatedAt": payload.get("updatedAt"),
        }

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
        affinities = payload.setdefault(
            "productAffinities",
            {"brands": {}, "categories": {}, "products": {}, "priceRanges": {}, "features": {}},
        )
        brand_scores = affinities.setdefault("brands", {})
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
            brand = str(product.get("brand", "")).strip().lower()
            if product_id:
                product_scores[product_id] = int(product_scores.get(product_id, 0)) + 1
            if category:
                category_scores[category] = int(category_scores.get(category, 0)) + 1
            if brand:
                brand_scores[brand] = int(brand_scores.get(brand, 0)) + 1

        payload["updatedAt"] = self.store.iso_now()
        self.memory_repository.upsert(user_id, payload)

    def get_history(self, *, user_id: str, limit: int = 20) -> dict[str, Any]:
        payload = self.memory_repository.get(user_id) or {}
        history = payload.get("interactionHistory", [])
        return {"history": deepcopy(history[-max(1, min(limit, 100)) :])}

    def _ensure_preferences(self, payload: Any) -> dict[str, Any]:
        defaults = self._default_memory()["preferences"]
        if not isinstance(payload, dict):
            return deepcopy(defaults)
        merged = deepcopy(defaults)
        for key, value in payload.items():
            merged[key] = value
        return merged

    def _normalize_preferences(self, prefs: dict[str, Any]) -> dict[str, Any]:
        normalized = self._ensure_preferences(prefs)
        normalized["size"] = str(normalized["size"]).strip() if normalized.get("size") else None
        for key in ("brandPreferences", "categories", "stylePreferences", "colorPreferences"):
            normalized[key] = self._normalize_list(normalized.get(key, []))
        price_range = normalized.get("priceRange")
        if isinstance(price_range, dict):
            normalized["priceRange"] = {
                "min": self._coerce_float(price_range.get("min"), default=0.0),
                "max": self._coerce_float(price_range.get("max"), default=0.0),
            }
        else:
            normalized["priceRange"] = {"min": 0.0, "max": 0.0}
        return normalized

    def _normalize_list(self, values: list[Any]) -> list[str]:
        cleaned = [self._normalize_token(value) for value in values if self._normalize_token(value)]
        return self._dedupe_preserve_order(cleaned)

    @staticmethod
    def _normalize_token(value: Any) -> str:
        return str(value).strip().lower()

    @staticmethod
    def _dedupe_preserve_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    @staticmethod
    def _coerce_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

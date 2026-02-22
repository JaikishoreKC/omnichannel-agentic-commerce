from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

from app.core.security import hash_password


class InMemoryStore:
    STATE_KEYS = (
        "users_by_id",
        "user_ids_by_email",
        "sessions_by_id",
        "carts_by_id",
        "orders_by_id",
        "refresh_tokens",
        "idempotency_keys",
        "memories_by_user_id",
        "messages_by_session",
        "support_tickets",
        "notifications",
        "products_by_id",
        "inventory_by_variant",
    )

    def __init__(self) -> None:
        self.lock = RLock()
        self._counters = {
            "user": 0,
            "session": 0,
            "cart": 0,
            "order": 0,
            "item": 0,
            "payment": 0,
        }

        self.users_by_id: dict[str, dict[str, Any]] = {}
        self.user_ids_by_email: dict[str, str] = {}
        self.sessions_by_id: dict[str, dict[str, Any]] = {}
        self.carts_by_id: dict[str, dict[str, Any]] = {}
        self.orders_by_id: dict[str, dict[str, Any]] = {}
        self.refresh_tokens: dict[str, dict[str, Any]] = {}
        self.idempotency_keys: dict[str, str] = {}
        self.memories_by_user_id: dict[str, dict[str, Any]] = {}
        self.messages_by_session: dict[str, list[dict[str, Any]]] = {}
        self.support_tickets: list[dict[str, Any]] = []
        self.notifications: list[dict[str, Any]] = []
        self.products_by_id: dict[str, dict[str, Any]] = self._seed_products()
        self.inventory_by_variant: dict[str, dict[str, Any]] = self._seed_inventory()
        self._seed_admin_user()

    def next_id(self, prefix: str) -> str:
        with self.lock:
            self._counters[prefix] += 1
            return f"{prefix}_{self._counters[prefix]:06d}"

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def iso_now() -> str:
        return InMemoryStore.utc_now().isoformat()

    @staticmethod
    def default_session_expiry(minutes: int = 30) -> str:
        return (InMemoryStore.utc_now() + timedelta(minutes=minutes)).isoformat()

    def _seed_products(self) -> dict[str, dict[str, Any]]:
        raw = [
            {
                "id": "prod_001",
                "name": "Running Shoes Pro",
                "description": "High-performance running shoes for daily training.",
                "category": "shoes",
                "price": 129.99,
                "currency": "USD",
                "images": ["https://cdn.example.com/products/prod_001/main.jpg"],
                "variants": [
                    {"id": "var_001", "size": "10", "color": "blue", "inStock": True},
                    {"id": "var_002", "size": "10", "color": "black", "inStock": True},
                ],
                "rating": 4.5,
                "reviewCount": 234,
            },
            {
                "id": "prod_002",
                "name": "Trail Runner X",
                "description": "Grip-focused trail shoes with reinforced toe box.",
                "category": "shoes",
                "price": 149.99,
                "currency": "USD",
                "images": ["https://cdn.example.com/products/prod_002/main.jpg"],
                "variants": [
                    {"id": "var_003", "size": "9", "color": "green", "inStock": True},
                    {"id": "var_004", "size": "10", "color": "gray", "inStock": False},
                ],
                "rating": 4.3,
                "reviewCount": 157,
            },
            {
                "id": "prod_003",
                "name": "Performance Hoodie",
                "description": "Lightweight hoodie built for active movement.",
                "category": "clothing",
                "price": 79.99,
                "currency": "USD",
                "images": ["https://cdn.example.com/products/prod_003/main.jpg"],
                "variants": [
                    {"id": "var_005", "size": "M", "color": "navy", "inStock": True},
                    {"id": "var_006", "size": "L", "color": "black", "inStock": True},
                ],
                "rating": 4.2,
                "reviewCount": 88,
            },
            {
                "id": "prod_004",
                "name": "Everyday Joggers",
                "description": "Soft stretch joggers for training and recovery.",
                "category": "clothing",
                "price": 64.5,
                "currency": "USD",
                "images": ["https://cdn.example.com/products/prod_004/main.jpg"],
                "variants": [
                    {"id": "var_007", "size": "M", "color": "charcoal", "inStock": True},
                    {"id": "var_008", "size": "L", "color": "charcoal", "inStock": True},
                ],
                "rating": 4.1,
                "reviewCount": 73,
            },
            {
                "id": "prod_005",
                "name": "Support Socks Pack",
                "description": "Compression support socks, 3-pack.",
                "category": "accessories",
                "price": 24.99,
                "currency": "USD",
                "images": ["https://cdn.example.com/products/prod_005/main.jpg"],
                "variants": [
                    {"id": "var_009", "size": "M", "color": "white", "inStock": True},
                    {"id": "var_010", "size": "L", "color": "white", "inStock": True},
                ],
                "rating": 4.0,
                "reviewCount": 44,
            },
            {
                "id": "prod_006",
                "name": "Training Backpack",
                "description": "Water-resistant backpack with shoe compartment.",
                "category": "accessories",
                "price": 89.0,
                "currency": "USD",
                "images": ["https://cdn.example.com/products/prod_006/main.jpg"],
                "variants": [
                    {"id": "var_011", "size": "one-size", "color": "black", "inStock": True}
                ],
                "rating": 4.6,
                "reviewCount": 102,
            },
        ]
        return {item["id"]: deepcopy(item) for item in raw}

    def _seed_inventory(self) -> dict[str, dict[str, Any]]:
        inventory: dict[str, dict[str, Any]] = {}
        for product in self.products_by_id.values():
            for variant in product["variants"]:
                base_qty = 20 if variant.get("inStock", False) else 0
                inventory[variant["id"]] = {
                    "variantId": variant["id"],
                    "productId": product["id"],
                    "totalQuantity": base_qty,
                    "reservedQuantity": 0,
                    "availableQuantity": base_qty,
                    "updatedAt": self.iso_now(),
                }
        return inventory

    def _seed_admin_user(self) -> None:
        admin_id = self.next_id("user")
        now = self.iso_now()
        admin = {
            "id": admin_id,
            "email": "admin@example.com",
            "name": "Platform Admin",
            "passwordHash": hash_password("AdminPass123!"),
            "role": "admin",
            "createdAt": now,
            "updatedAt": now,
            "lastLoginAt": now,
        }
        self.users_by_id[admin_id] = admin
        self.user_ids_by_email[admin["email"]] = admin_id

    def export_state(self) -> dict[str, Any]:
        with self.lock:
            state = {"_counters": deepcopy(self._counters)}
            for key in self.STATE_KEYS:
                state[key] = deepcopy(getattr(self, key))
            return state

    def import_state(self, state: dict[str, Any]) -> None:
        with self.lock:
            counters = state.get("_counters")
            if isinstance(counters, dict):
                self._counters.update({k: int(v) for k, v in counters.items()})

            for key in self.STATE_KEYS:
                value = state.get(key)
                if value is not None:
                    setattr(self, key, deepcopy(value))

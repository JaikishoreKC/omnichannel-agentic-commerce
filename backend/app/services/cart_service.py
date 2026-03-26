from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock
from time import monotonic
from typing import Any

from fastapi import HTTPException

from app.core.config import Settings
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.core.utils import generate_id, iso_now, utc_now


class CartService:
    def __init__(
        self,
        settings: Settings,
        cart_repository: CartRepository,
        product_repository: ProductRepository,
        session_repository: Any,
    ) -> None:
        self.settings = settings
        self.cart_repository = cart_repository
        self.product_repository = product_repository
        self.session_repository = session_repository
        self._cart_ttl_hours = 24
        self._read_cache_ttl_seconds = 2.0
        self._cart_read_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._cart_read_cache_lock = RLock()

    def get_cart(self, user_id: str | None, session_id: str) -> dict[str, Any]:
        cache_key = self._cache_key(user_id=user_id, session_id=session_id)
        cached = self._read_cache_get(cache_key)
        if cached is not None:
            return cached

        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        self._read_cache_set(cache_key, cart)
        return deepcopy(cart)

    def add_item(
        self,
        user_id: str | None,
        session_id: str,
        product_id: str,
        variant_id: str,
        quantity: int,
    ) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        product, variant = self._resolve_product_variant(product_id, variant_id)
        if not variant["inStock"]:
            raise HTTPException(status_code=409, detail="Variant is out of stock")

        existing = next(
            (
                item
                for item in cart["items"]
                if item["productId"] == product_id and item["variantId"] == variant_id
            ),
            None,
        )
        if existing:
            existing["quantity"] += quantity
        else:
            item = {
                "itemId": generate_id("item"),
                "productId": product["id"],
                "variantId": variant["id"],
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "image": product["images"][0] if product.get("images") else "",
                "metadata": {"brand": product.get("brand", "")},
            }
            cart["items"].append(item)
        self._recalculate_cart(cart)
        self.cart_repository.update(cart)
        self._invalidate_cache(user_id=user_id, session_id=session_id)
        return deepcopy(cart)

    def update_item(
        self, user_id: str | None, session_id: str, item_id: str, quantity: int
    ) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        target = next((item for item in cart["items"] if item["itemId"] == item_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Cart item not found")
        target["quantity"] = quantity
        self._recalculate_cart(cart)
        self.cart_repository.update(cart)
        self._invalidate_cache(user_id=user_id, session_id=session_id)
        return deepcopy(cart)

    def remove_item(self, user_id: str | None, session_id: str, item_id: str) -> None:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        before = len(cart["items"])
        cart["items"] = [item for item in cart["items"] if item["itemId"] != item_id]
        if len(cart["items"]) == before:
            raise HTTPException(status_code=404, detail="Cart item not found")
        self._recalculate_cart(cart)
        self.cart_repository.update(cart)
        self._invalidate_cache(user_id=user_id, session_id=session_id)

    def clear_cart(self, user_id: str | None, session_id: str) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        cart["items"] = []
        cart["appliedDiscount"] = None
        self._recalculate_cart(cart)
        self.cart_repository.update(cart)
        self._invalidate_cache(user_id=user_id, session_id=session_id)
        return deepcopy(cart)

    def apply_discount(
        self, user_id: str | None, session_id: str, discount_code: str
    ) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        normalized = discount_code.strip().upper()
        if normalized == "SAVE20":
            cart["appliedDiscount"] = {
                "code": "SAVE20",
                "type": "percentage",
                "value": 20,
            }
            self._recalculate_cart(cart)
            self.cart_repository.update(cart)
            self._invalidate_cache(user_id=user_id, session_id=session_id)
            return deepcopy(cart)
        raise HTTPException(status_code=400, detail="Invalid discount code")

    def attach_cart_to_user(self, session_id: str, user_id: str) -> None:
        session_cart = self.cart_repository.get_for_user_or_session(user_id=None, session_id=session_id)
        if not session_cart:
            return
        session_cart["userId"] = user_id
        session_cart["status"] = "active"
        session_cart["expiresAt"] = self._next_cart_expiry()
        self._recalculate_cart(session_cart)
        self.cart_repository.update(session_cart)
        self._invalidate_cache(user_id=None, session_id=session_id)
        self._invalidate_cache(user_id=user_id, session_id="")

    def merge_guest_cart_into_user(self, *, session_id: str, user_id: str) -> dict[str, Any] | None:
        guest_cart = self.cart_repository.get_for_user_or_session(user_id=None, session_id=session_id)
        if not guest_cart:
            return None

        user_cart = self.cart_repository.get_for_user_or_session(user_id=user_id, session_id="")
        if not user_cart:
            guest_cart["userId"] = user_id
            guest_cart["status"] = "active"
            guest_cart["expiresAt"] = self._next_cart_expiry()
            self._recalculate_cart(guest_cart)
            self.cart_repository.update(guest_cart)
            self._invalidate_cache(user_id=None, session_id=session_id)
            self._invalidate_cache(user_id=user_id, session_id="")
            return deepcopy(guest_cart)

        by_key: dict[tuple[str, str], dict[str, Any]] = {
            (str(item["productId"]), str(item["variantId"])): item for item in user_cart["items"]
        }
        for source in guest_cart.get("items", []):
            key = (str(source.get("productId", "")), str(source.get("variantId", "")))
            if not key[0] or not key[1]:
                continue
            existing = by_key.get(key)
            quantity = max(1, min(50, int(source.get("quantity", 1))))
            if existing:
                existing["quantity"] = max(1, min(50, int(existing.get("quantity", 1)) + quantity))
                continue
            user_cart["items"].append(
                {
                    "itemId": generate_id("item"),
                    "productId": key[0],
                    "variantId": key[1],
                    "name": str(source.get("name", "item")),
                    "price": float(source.get("price", 0.0)),
                    "quantity": quantity,
                    "image": str(source.get("image", "")),
                    "metadata": deepcopy(source.get("metadata", {})),
                }
            )
        if not user_cart.get("appliedDiscount") and guest_cart.get("appliedDiscount"):
            user_cart["appliedDiscount"] = deepcopy(guest_cart["appliedDiscount"])
        user_cart["status"] = "active"
        user_cart["expiresAt"] = self._next_cart_expiry()
        self._recalculate_cart(user_cart)
        self.cart_repository.update(user_cart)
        self.cart_repository.delete(str(guest_cart["id"]))
        self._invalidate_cache(user_id=None, session_id=session_id)
        self._invalidate_cache(user_id=user_id, session_id="")
        return deepcopy(user_cart)

    def clear_cart_for_user(self, user_id: str) -> dict[str, Any] | None:
        cart = self.cart_repository.get_for_user_or_session(user_id=user_id, session_id="")
        if not cart:
            return None
        cart["items"] = []
        cart["appliedDiscount"] = None
        cart["status"] = "active"
        cart["expiresAt"] = self._next_cart_expiry()
        self._recalculate_cart(cart)
        self.cart_repository.update(cart)
        self._invalidate_cache(user_id=user_id, session_id="")
        return deepcopy(cart)

    def mark_cart_converted_for_user(self, user_id: str) -> dict[str, Any] | None:
        cart = self.cart_repository.get_for_user_or_session(user_id=user_id, session_id="")
        if not cart:
            return None
        cart["status"] = "converted"
        cart["updatedAt"] = iso_now()
        cart["expiresAt"] = self._next_cart_expiry()
        self.cart_repository.update(cart)
        self._invalidate_cache(user_id=user_id, session_id="")
        return deepcopy(cart)

    def _cache_key(self, *, user_id: str | None, session_id: str) -> str:
        if user_id:
            return f"user:{user_id}"
        return f"session:{session_id}"

    def _read_cache_get(self, cache_key: str) -> dict[str, Any] | None:
        now = monotonic()
        with self._cart_read_cache_lock:
            entry = self._cart_read_cache.get(cache_key)
            if not entry:
                return None
            expires_at, cart = entry
            if expires_at <= now:
                self._cart_read_cache.pop(cache_key, None)
                return None
            return deepcopy(cart)

    def _read_cache_set(self, cache_key: str, cart: dict[str, Any]) -> None:
        with self._cart_read_cache_lock:
            self._cart_read_cache[cache_key] = (
                monotonic() + self._read_cache_ttl_seconds,
                deepcopy(cart),
            )

    def _invalidate_cache(self, *, user_id: str | None, session_id: str) -> None:
        cache_key = self._cache_key(user_id=user_id, session_id=session_id)
        with self._cart_read_cache_lock:
            self._cart_read_cache.pop(cache_key, None)

    def _get_or_create_cart(self, user_id: str | None, session_id: str) -> dict[str, Any]:
        existing = self.cart_repository.get_for_user_or_session(user_id=user_id, session_id=session_id)
        if user_id and not existing:
            guest_cart = self.cart_repository.get_for_user_or_session(user_id=None, session_id=session_id)
            if guest_cart:
                guest_cart["userId"] = user_id
                guest_cart["status"] = "active"
                guest_cart["expiresAt"] = self._next_cart_expiry()
                self._recalculate_cart(guest_cart)
                self.cart_repository.update(guest_cart)
                self._invalidate_cache(user_id=None, session_id=session_id)
                self._invalidate_cache(user_id=user_id, session_id="")
                return guest_cart
        if existing:
            if self._is_cart_expired(existing):
                existing["status"] = "abandoned"
                existing["updatedAt"] = iso_now()
                self.cart_repository.update(existing)
            else:
                existing["status"] = "active"
                existing["expiresAt"] = self._next_cart_expiry()
                self.cart_repository.update(existing)
                return existing

        cart_id = generate_id("cart")
        now = iso_now()
        cart = {
            "id": cart_id,
            "userId": user_id,
            "sessionId": session_id,
            "anonymousId": self._resolve_anonymous_id(session_id=session_id),
            "items": [],
            "subtotal": 0.0,
            "tax": 0.0,
            "shipping": 0.0,
            "discount": 0.0,
            "total": 0.0,
            "itemCount": 0,
            "currency": "USD",
            "appliedDiscount": None,
            "status": "active",
            "createdAt": now,
            "updatedAt": now,
            "expiresAt": self._next_cart_expiry(),
        }
        return self.cart_repository.create(cart)

    def _resolve_product_variant(
        self, product_id: str, variant_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        product = self.product_repository.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        variant = next((v for v in product["variants"] if v["id"] == variant_id), None)
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")
        return product, variant

    def _resolve_anonymous_id(self, *, session_id: str) -> str | None:
        session = self.session_repository.get(session_id)
        if not isinstance(session, dict):
            return None
        value = str(session.get("anonymousId", "")).strip()
        return value or None

    def _next_cart_expiry(self) -> str:
        return (utc_now() + timedelta(hours=self._cart_ttl_hours)).isoformat()

    def _is_cart_expired(self, cart: dict[str, Any]) -> bool:
        expires_at = str(cart.get("expiresAt", "")).strip()
        if not expires_at:
            return False
        try:
            parsed = datetime.fromisoformat(expires_at)
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= utc_now()

    def _recalculate_cart(self, cart: dict[str, Any]) -> None:
        subtotal = sum(item["price"] * item["quantity"] for item in cart["items"])
        discount = 0.0
        applied = cart.get("appliedDiscount")
        if applied and applied.get("type") == "percentage":
            discount = round(subtotal * (applied["value"] / 100), 2)

        taxable_base = max(0.0, subtotal - discount)
        tax = round(taxable_base * self.settings.cart_tax_rate, 2)
        shipping = self.settings.default_shipping_fee if cart["items"] else 0.0
        total = round(taxable_base + tax + shipping, 2)

        cart["subtotal"] = round(subtotal, 2)
        cart["tax"] = tax
        cart["shipping"] = shipping
        cart["discount"] = discount
        cart["total"] = total
        cart["itemCount"] = sum(item["quantity"] for item in cart["items"])
        if str(cart.get("status", "active")).strip().lower() != "converted":
            cart["status"] = "active"
        cart["expiresAt"] = self._next_cart_expiry()
        cart["updatedAt"] = iso_now()

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.core.config import Settings
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.store.in_memory import InMemoryStore


class CartService:
    def __init__(
        self,
        store: InMemoryStore,
        settings: Settings,
        cart_repository: CartRepository,
        product_repository: ProductRepository,
    ) -> None:
        self.store = store
        self.settings = settings
        self.cart_repository = cart_repository
        self.product_repository = product_repository
        self._cart_ttl_hours = 24

    def get_cart(self, user_id: str | None, session_id: str) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
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

        with self.store.lock:
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
                    "itemId": self.store.next_id("item"),
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
            return deepcopy(cart)

    def update_item(
        self, user_id: str | None, session_id: str, item_id: str, quantity: int
    ) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        with self.store.lock:
            target = next((item for item in cart["items"] if item["itemId"] == item_id), None)
            if not target:
                raise HTTPException(status_code=404, detail="Cart item not found")
            target["quantity"] = quantity
            self._recalculate_cart(cart)
            self.cart_repository.update(cart)
            return deepcopy(cart)

    def remove_item(self, user_id: str | None, session_id: str, item_id: str) -> None:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        with self.store.lock:
            before = len(cart["items"])
            cart["items"] = [item for item in cart["items"] if item["itemId"] != item_id]
            if len(cart["items"]) == before:
                raise HTTPException(status_code=404, detail="Cart item not found")
            self._recalculate_cart(cart)
            self.cart_repository.update(cart)

    def clear_cart(self, user_id: str | None, session_id: str) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        with self.store.lock:
            cart["items"] = []
            cart["appliedDiscount"] = None
            self._recalculate_cart(cart)
            self.cart_repository.update(cart)
            return deepcopy(cart)

    def apply_discount(
        self, user_id: str | None, session_id: str, discount_code: str
    ) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        normalized = discount_code.strip().upper()
        if normalized == "SAVE20":
            with self.store.lock:
                cart["appliedDiscount"] = {
                    "code": "SAVE20",
                    "type": "percentage",
                    "value": 20,
                }
                self._recalculate_cart(cart)
                self.cart_repository.update(cart)
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
                    "itemId": self.store.next_id("item"),
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
        return deepcopy(cart)

    def mark_cart_converted_for_user(self, user_id: str) -> dict[str, Any] | None:
        cart = self.cart_repository.get_for_user_or_session(user_id=user_id, session_id="")
        if not cart:
            return None
        cart["status"] = "converted"
        cart["updatedAt"] = self.store.iso_now()
        cart["expiresAt"] = self._next_cart_expiry()
        self.cart_repository.update(cart)
        return deepcopy(cart)

    def _get_or_create_cart(self, user_id: str | None, session_id: str) -> dict[str, Any]:
        existing = self.cart_repository.get_for_user_or_session(user_id=user_id, session_id=session_id)
        if existing:
            if self._is_cart_expired(existing):
                existing["status"] = "abandoned"
                existing["updatedAt"] = self.store.iso_now()
                self.cart_repository.update(existing)
            else:
                existing["status"] = "active"
                existing["expiresAt"] = self._next_cart_expiry()
                self.cart_repository.update(existing)
                return existing

        with self.store.lock:
            cart_id = self.store.next_id("cart")
            now = self.store.iso_now()
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
        with self.store.lock:
            session = self.store.sessions_by_id.get(session_id)
            if not isinstance(session, dict):
                return None
            value = str(session.get("anonymousId", "")).strip()
            return value or None

    def _next_cart_expiry(self) -> str:
        return (self.store.utc_now() + timedelta(hours=self._cart_ttl_hours)).isoformat()

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
        return parsed <= self.store.utc_now()

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
        cart["updatedAt"] = self.store.iso_now()

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import re
from typing import Any

from fastapi import HTTPException

from app.repositories.order_repository import OrderRepository
from app.services.cart_service import CartService
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService
from app.core.utils import generate_id, iso_now, utc_now
from app.infrastructure.logging import get_logger


class OrderService:
    _IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

    def __init__(
        self,
        cart_service: CartService,
        inventory_service: InventoryService,
        payment_service: PaymentService,
        notification_service: NotificationService,
        order_repository: OrderRepository,
    ) -> None:
        self.cart_service = cart_service
        self.inventory_service = inventory_service
        self.payment_service = payment_service
        self.notification_service = notification_service
        self.order_repository = order_repository
        self.logger = get_logger(__name__)

    def create_order(
        self,
        user_id: str,
        shipping_address: dict[str, Any],
        payment_method: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        normalized_key = str(idempotency_key or "").strip()
        if not normalized_key:
            raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")
        if not self._IDEMPOTENCY_KEY_PATTERN.fullmatch(normalized_key):
            raise HTTPException(
                status_code=400,
                detail="Invalid Idempotency-Key header. Use 1-128 chars: letters, numbers, _, ., :, -",
            )

        key = f"{user_id}:{normalized_key}"
        existing_order_id = self.order_repository.get_idempotent(key)
        if existing_order_id:
            existing_order = self.order_repository.get(existing_order_id)
            if existing_order:
                return existing_order

        cart = self.cart_service.get_cart(user_id=user_id, session_id="")
        if not cart["items"]:
            raise HTTPException(status_code=400, detail="Cart is empty")

        reservations = self.inventory_service.reserve_for_order(cart["items"])
        payment_result: dict[str, Any] | None = None
        try:
            payment_result = self.payment_service.authorize(
                amount=float(cart["total"]),
                payment_method=payment_method,
            )
        except Exception:
            self.inventory_service.rollback_reservation(reservations)
            raise

        order_id = generate_id("order")
        created_at = iso_now()
        estimated_delivery = (utc_now() + timedelta(days=5)).isoformat()
        order = {
            "id": order_id,
            "userId": user_id,
            "status": "confirmed",
            "items": deepcopy(cart["items"]),
            "subtotal": cart["subtotal"],
            "tax": cart["tax"],
            "shipping": cart["shipping"],
            "discount": cart["discount"],
            "total": cart["total"],
            "shippingAddress": shipping_address,
            "payment": {
                "method": payment_result.get("method") if payment_result else "unknown",
                "transactionId": payment_result.get("transactionId") if payment_result else None,
                "status": payment_result.get("status") if payment_result else "failed",
            },
            "timeline": [
                {"status": "order_placed", "timestamp": created_at},
                {"status": "confirmed", "timestamp": created_at},
            ],
            "tracking": {
                "carrier": None,
                "trackingNumber": None,
                "status": "pending",
                "updates": [],
            },
            "estimatedDelivery": estimated_delivery,
            "createdAt": created_at,
            "updatedAt": created_at,
        }
        try:
            self.order_repository.create(order)
        except Exception as exc:
            # Compensate reservations if persistence fails after payment authorization.
            self.inventory_service.rollback_reservation(reservations)
            try:
                self.logger.exception("order_persistence_failed", user_id=user_id, order_id=order_id, error=str(exc))
            except UnicodeEncodeError:
                safe_error = str(exc).encode("ascii", "backslashreplace").decode("ascii")
                self.logger.error(
                    "order_persistence_failed_ascii_fallback",
                    user_id=user_id,
                    order_id=order_id,
                    error=safe_error,
                )
            raise HTTPException(status_code=503, detail="Unable to create order at the moment") from exc

        try:
            self.order_repository.set_idempotent(key=key, order_id=order_id)
        except Exception as exc:
            # Idempotency backfill failure should not fail a successfully persisted order.
            self.logger.warning("order_idempotency_record_failed", user_id=user_id, order_id=order_id, error=str(exc))

        self.cart_service.mark_cart_converted_for_user(user_id)

        self.inventory_service.commit_reservation(order["items"])
        try:
            self.notification_service.send_order_confirmation(user_id=user_id, order=order)
        except Exception as exc:
            # Notification delivery is a side-effect and should not fail checkout.
            self.logger.warning("order_confirmation_notification_failed", user_id=user_id, order_id=order_id, error=str(exc))

        return deepcopy(order)

    def list_orders(self, user_id: str) -> dict[str, Any]:
        orders = self.order_repository.list_by_user(user_id)
        orders.sort(key=lambda order: order["createdAt"], reverse=True)
        return {
            "orders": [
                {
                    "id": order["id"],
                    "status": order["status"],
                    "total": order["total"],
                    "itemCount": sum(int(item.get("quantity", 0)) for item in order["items"]),
                    "createdAt": order["createdAt"],
                }
                for order in orders
            ]
        }

    def get_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        order = self.order_repository.get(order_id)
        if not order or order["userId"] != user_id:
            raise HTTPException(status_code=404, detail="Order not found")
        return deepcopy(order)

    def cancel_order(self, user_id: str, order_id: str, reason: str | None) -> dict[str, Any]:
        order = self.order_repository.get(order_id)
        if not order or order["userId"] != user_id:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] in {"shipped", "delivered", "cancelled", "refunded"}:
            raise HTTPException(status_code=409, detail="Order can no longer be cancelled")

        order["status"] = "cancelled"
        order["updatedAt"] = iso_now()
        order["timeline"].append(
            {
                "status": "cancelled",
                "timestamp": order["updatedAt"],
                "note": reason or "Cancelled by customer",
            }
        )
        self.order_repository.update(order)
        return {"success": True, "orderId": order_id, "status": "cancelled"}

    def request_refund(self, user_id: str, order_id: str, reason: str | None) -> dict[str, Any]:
        order = self.order_repository.get(order_id)
        if not order or order["userId"] != user_id:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] in {"cancelled", "refunded"}:
            raise HTTPException(status_code=409, detail="Order cannot be refunded in current state")

        order["status"] = "refunded"
        order["updatedAt"] = iso_now()
        payment = order.setdefault("payment", {})
        payment["status"] = "refunded"
        order.setdefault("timeline", []).append(
            {
                "status": "refunded",
                "timestamp": order["updatedAt"],
                "note": reason or "Refund requested by customer",
            }
        )
        self.order_repository.update(order)
        return {"success": True, "orderId": order_id, "status": "refunded"}

    def update_shipping_address(
        self,
        *,
        user_id: str,
        order_id: str,
        shipping_address: dict[str, Any],
    ) -> dict[str, Any]:
        order = self.order_repository.get(order_id)
        if not order or order["userId"] != user_id:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] not in {"confirmed", "processing"}:
            raise HTTPException(
                status_code=409,
                detail="Shipping address can only be changed before shipment",
            )

        order["shippingAddress"] = deepcopy(shipping_address)
        order["updatedAt"] = iso_now()
        order.setdefault("timeline", []).append(
            {
                "status": "address_updated",
                "timestamp": order["updatedAt"],
            }
        )
        self.order_repository.update(order)
        return {
            "success": True,
            "orderId": order_id,
            "status": order["status"],
            "shippingAddress": deepcopy(order["shippingAddress"]),
        }

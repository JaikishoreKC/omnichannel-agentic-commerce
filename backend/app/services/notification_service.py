from __future__ import annotations

from typing import Any

from app.repositories.notification_repository import NotificationRepository
from app.store.in_memory import InMemoryStore


class NotificationService:
    def __init__(
        self,
        store: InMemoryStore,
        notification_repository: NotificationRepository,
    ) -> None:
        self.store = store
        self.notification_repository = notification_repository

    def send_order_confirmation(self, *, user_id: str, order: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "id": f"notif_{self.store.next_id('item')}",
            "type": "order_confirmation",
            "userId": user_id,
            "orderId": order["id"],
            "message": f"Order {order['id']} confirmed for ${order['total']:.2f}",
            "createdAt": self.store.iso_now(),
        }
        self.notification_repository.create(payload)
        return payload

    def send_voice_recovery_followup(
        self,
        *,
        user_id: str,
        call_id: str,
        message: str,
        disposition: str,
    ) -> dict[str, Any]:
        payload = {
            "id": f"notif_{self.store.next_id('item')}",
            "type": "voice_recovery_followup",
            "userId": user_id,
            "callId": call_id,
            "disposition": disposition,
            "message": message,
            "createdAt": self.store.iso_now(),
        }
        self.notification_repository.create(payload)
        return payload

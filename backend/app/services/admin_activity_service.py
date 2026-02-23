from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.repositories.admin_activity_repository import AdminActivityRepository
from app.store.in_memory import InMemoryStore


class AdminActivityService:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        admin_activity_repository: AdminActivityRepository,
    ) -> None:
        self.store = store
        self.admin_activity_repository = admin_activity_repository

    def record(
        self,
        *,
        admin_user: dict[str, Any],
        action: str,
        resource: str,
        resource_id: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        payload = {
            "id": f"admin_log_{self.store.next_id('item')}",
            "adminId": str(admin_user.get("id", "")),
            "adminEmail": str(admin_user.get("email", "")),
            "action": action,
            "resource": resource,
            "resourceId": resource_id,
            "changes": {
                "before": deepcopy(before) if isinstance(before, dict) else None,
                "after": deepcopy(after) if isinstance(after, dict) else None,
            },
            "ipAddress": ip_address or "",
            "userAgent": user_agent or "",
            "timestamp": self.store.iso_now(),
        }
        return self.admin_activity_repository.create(payload)

    def list_recent(self, *, limit: int = 100) -> dict[str, Any]:
        return {"logs": self.admin_activity_repository.list_recent(limit=limit)}

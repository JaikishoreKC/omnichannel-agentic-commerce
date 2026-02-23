from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
from typing import Any

from app.core.config import Settings
from app.repositories.admin_activity_repository import AdminActivityRepository
from app.store.in_memory import InMemoryStore


class AdminActivityService:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        settings: Settings,
        admin_activity_repository: AdminActivityRepository,
    ) -> None:
        self.store = store
        self.settings = settings
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
        with self.store.lock:
            previous_hash = ""
            if self.store.admin_activity_logs:
                previous_hash = str(self.store.admin_activity_logs[-1].get("entryHash", "")).strip()
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
            "prevHash": previous_hash,
            "hashVersion": "v1",
        }
        payload["entryHash"] = self._compute_entry_hash(payload)
        return self.admin_activity_repository.create(payload)

    def list_recent(self, *, limit: int = 100) -> dict[str, Any]:
        return {"logs": self.admin_activity_repository.list_recent(limit=limit)}

    def verify_integrity(self, *, limit: int = 5000) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 10000))
        with self.store.lock:
            logs = deepcopy(self.store.admin_activity_logs[-safe_limit:])

        if not logs:
            return {"ok": True, "total": 0, "issues": []}

        issues: list[dict[str, Any]] = []
        expected_prev = ""
        for row in logs:
            row_id = str(row.get("id", "")).strip()
            prev_hash = str(row.get("prevHash", "")).strip()
            entry_hash = str(row.get("entryHash", "")).strip()
            if prev_hash != expected_prev:
                issues.append(
                    {
                        "id": row_id,
                        "error": "prev_hash_mismatch",
                        "expectedPrevHash": expected_prev,
                        "actualPrevHash": prev_hash,
                    }
                )
            expected_entry = self._compute_entry_hash(row)
            if not entry_hash:
                issues.append({"id": row_id, "error": "missing_entry_hash"})
            elif entry_hash != expected_entry:
                issues.append(
                    {
                        "id": row_id,
                        "error": "entry_hash_mismatch",
                    }
                )
            expected_prev = entry_hash

        return {
            "ok": len(issues) == 0,
            "total": len(logs),
            "issues": issues,
        }

    def _compute_entry_hash(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            {
                "id": str(payload.get("id", "")),
                "adminId": str(payload.get("adminId", "")),
                "adminEmail": str(payload.get("adminEmail", "")),
                "action": str(payload.get("action", "")),
                "resource": str(payload.get("resource", "")),
                "resourceId": str(payload.get("resourceId", "")),
                "changes": deepcopy(payload.get("changes")),
                "ipAddress": str(payload.get("ipAddress", "")),
                "userAgent": str(payload.get("userAgent", "")),
                "timestamp": str(payload.get("timestamp", "")),
                "prevHash": str(payload.get("prevHash", "")),
                "hashVersion": str(payload.get("hashVersion", "v1")),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        secret = str(self.settings.token_secret or "").strip() or "replace-with-strong-secret"
        return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

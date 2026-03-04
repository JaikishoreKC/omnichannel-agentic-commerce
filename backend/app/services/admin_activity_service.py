from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
from typing import Any

from app.core.config import Settings
from app.repositories.admin_activity_repository import AdminActivityRepository
from app.core.utils import generate_id, iso_now
from app.store.in_memory import InMemoryStore


class AdminActivityService:
    def __init__(
        self,
        *,
        settings: Settings,
        admin_activity_repository: AdminActivityRepository,
        store: InMemoryStore | None = None,
        enable_memory_mirror: bool = False,
    ) -> None:
        self.settings = settings
        self.admin_activity_repository = admin_activity_repository
        self.store = store
        self.enable_memory_mirror = enable_memory_mirror

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
        previous_hash = ""
        latest = self.admin_activity_repository.get_latest()
        if latest:
            previous_hash = str(latest.get("entryHash", "")).strip()

        payload = {
            "id": generate_id("admin_log"),
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
            "timestamp": iso_now(),
            "prevHash": previous_hash,
            "hashVersion": "v1",
        }
        payload["entryHash"] = self._compute_entry_hash(payload)
        created = self.admin_activity_repository.create(payload)
        self._mirror_to_in_memory_log(created)
        return created

    def list_recent(self, *, limit: int = 100) -> dict[str, Any]:
        logs = self._list_recent_logs(limit=limit)
        return {"logs": logs}

    def verify_integrity(self, *, limit: int = 5000) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 10000))
        logs = self._list_recent_logs(limit=safe_limit)

        if not logs:
            return {"ok": True, "total": 0, "issues": []}

        issues: list[dict[str, Any]] = []
        by_entry_hash = {
            str(row.get("entryHash", "")).strip(): row
            for row in logs
            if isinstance(row, dict) and str(row.get("entryHash", "")).strip()
        }
        prev_hash_claims: dict[str, int] = {}

        for row in logs:
            row_id = str(row.get("id", "")).strip()
            prev_hash = str(row.get("prevHash", "")).strip()
            entry_hash = str(row.get("entryHash", "")).strip()

            if prev_hash:
                prev_hash_claims[prev_hash] = prev_hash_claims.get(prev_hash, 0) + 1
                if prev_hash not in by_entry_hash:
                    # Could be due to window truncation; still report as mismatch for visibility.
                    # Callers can increase limit for full-chain verification.
                    issues.append(
                        {
                            "id": row_id,
                            "error": "prev_hash_mismatch",
                            "expectedPrevHash": "existing_entry_hash",
                            "actualPrevHash": prev_hash,
                        }
                    )

            if not entry_hash:
                issues.append(
                    {
                        "id": row_id,
                        "error": "missing_entry_hash",
                    }
                )
            expected_entry = self._compute_entry_hash(row)
            if entry_hash and entry_hash != expected_entry:
                issues.append(
                    {
                        "id": row_id,
                        "error": "entry_hash_mismatch",
                    }
                )

        for parent_hash, claim_count in prev_hash_claims.items():
            if claim_count > 1:
                issues.append(
                    {
                        "id": parent_hash,
                        "error": "hash_chain_fork",
                    }
                )

        return {
            "ok": len(issues) == 0,
            "total": len(logs),
            "issues": issues,
        }

    def _list_recent_logs(self, *, limit: int) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 5000))
        repo_logs = self.admin_activity_repository.list_recent(limit=safe_limit)
        if repo_logs:
            memory_logs = self._read_in_memory_logs(limit=safe_limit)
            if memory_logs and self._should_use_memory_mirror():
                return memory_logs
            return repo_logs
        memory_logs = self._read_in_memory_logs(limit=safe_limit)
        if memory_logs and self._should_use_memory_mirror():
            return memory_logs
        return repo_logs

    def _mirror_to_in_memory_log(self, payload: dict[str, Any]) -> None:
        if not self._should_use_memory_mirror():
            return
        if self.store is None:
            return
        logs = getattr(self.store, "admin_activity_logs", None)
        if isinstance(logs, list):
            logs.append(deepcopy(payload))

    def _read_in_memory_logs(self, *, limit: int) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        logs = getattr(self.store, "admin_activity_logs", None)
        if not isinstance(logs, list) or not logs:
            return []
        safe_limit = max(1, min(limit, 5000))
        slice_logs = logs[-safe_limit:]
        return [deepcopy(row) for row in reversed(slice_logs) if isinstance(row, dict)]

    def _should_use_memory_mirror(self) -> bool:
        return self.enable_memory_mirror and self.store is not None

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

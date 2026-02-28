from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
class AdminActivityRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._write_to_mongo(payload)
        return deepcopy(payload)

    def list_recent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({}).sort("timestamp", -1).limit(safe_limit))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            if not isinstance(row, dict):
                continue
            output.append(row)
        return output
    def get_latest(self) -> dict[str, Any] | None:
        collection = self._mongo_collection()
        if collection is None:
            return None
        row = collection.find_one(sort=[("timestamp", -1)])
        if row:
            row.pop("_id", None)
            return row
        return None

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["admin_activity_logs"]

    def _write_to_mongo(self, payload: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        log_id = str(payload.get("id", "")).strip()
        if not log_id:
            return
        collection.update_one(
            {"id": log_id},
            {"$set": deepcopy(payload)},
            upsert=True,
        )

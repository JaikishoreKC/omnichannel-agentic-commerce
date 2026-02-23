from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
from app.store.in_memory import InMemoryStore


class SupportRepository:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.store = store
        self.mongo_manager = mongo_manager

    def create(self, ticket: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.support_tickets.append(deepcopy(ticket))
        self._write_to_mongo(ticket)
        return deepcopy(ticket)

    def get(self, ticket_id: str) -> dict[str, Any] | None:
        with self.store.lock:
            for ticket in self.store.support_tickets:
                if str(ticket.get("id", "")) == ticket_id:
                    return deepcopy(ticket)

        collection = self._mongo_collection()
        if collection is None:
            return None
        row = collection.find_one({"ticketId": ticket_id})
        if not row:
            return None
        row.pop("_id", None)
        row.pop("ticketId", None)
        if not isinstance(row, dict):
            return None
        with self.store.lock:
            self.store.support_tickets.append(deepcopy(row))
        return deepcopy(row)

    def update(self, ticket: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            replaced = False
            for idx, row in enumerate(self.store.support_tickets):
                if str(row.get("id", "")) == str(ticket.get("id", "")):
                    self.store.support_tickets[idx] = deepcopy(ticket)
                    replaced = True
                    break
            if not replaced:
                self.store.support_tickets.append(deepcopy(ticket))
        self._write_to_mongo(ticket)
        return deepcopy(ticket)

    def list(
        self,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self.store.lock:
            cached = [deepcopy(ticket) for ticket in self.store.support_tickets]

        if not cached:
            persisted = self._read_all_from_mongo(limit=safe_limit)
            if persisted:
                with self.store.lock:
                    existing_ids = {str(ticket.get("id", "")) for ticket in self.store.support_tickets}
                    for ticket in persisted:
                        ticket_id = str(ticket.get("id", ""))
                        if ticket_id and ticket_id not in existing_ids:
                            self.store.support_tickets.append(deepcopy(ticket))
                cached = persisted

        target_status = status.strip().lower() if isinstance(status, str) and status.strip() else None
        rows: list[dict[str, Any]] = []
        for ticket in cached:
            if user_id and str(ticket.get("userId", "")) != user_id:
                continue
            if session_id and str(ticket.get("sessionId", "")) != session_id:
                continue
            if target_status and str(ticket.get("status", "")).strip().lower() != target_status:
                continue
            rows.append(ticket)
        rows.sort(key=lambda row: str(row.get("updatedAt", row.get("createdAt", ""))), reverse=True)
        return rows[:safe_limit]

    def list_open(self) -> list[dict[str, Any]]:
        return self.list(status="open", limit=500)

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["support_tickets"]

    def _write_to_mongo(self, ticket: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"ticketId": ticket["id"]},
            {"$set": {"ticketId": ticket["id"], **deepcopy(ticket)}},
            upsert=True,
        )

    def _read_open_from_mongo(self) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({"status": "open"}).sort("createdAt", -1))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("ticketId", None)
            if isinstance(row, dict):
                output.append(row)
        return output

    def _read_all_from_mongo(self, *, limit: int) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({}).sort("updatedAt", -1).limit(limit))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("ticketId", None)
            if isinstance(row, dict):
                output.append(row)
        return output

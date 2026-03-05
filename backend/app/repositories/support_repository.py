from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
from app.store.in_memory import InMemoryStore


class SupportRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        store: InMemoryStore | None = None,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.store = store

    def create(self, ticket: dict[str, Any]) -> dict[str, Any]:
        self._write_to_mongo(ticket)
        self._write_to_in_memory(ticket)
        return deepcopy(ticket)

    def get(self, ticket_id: str) -> dict[str, Any] | None:
        collection = self._mongo_collection()
        if collection is None:
            mirrored = self._read_from_in_memory(ticket_id)
            return deepcopy(mirrored) if mirrored is not None else None
        row = collection.find_one({"ticketId": ticket_id})
        if not row:
            return None
        row.pop("_id", None)
        row.pop("ticketId", None)
        return deepcopy(row) if isinstance(row, dict) else None

    def update(self, ticket: dict[str, Any]) -> dict[str, Any]:
        self._write_to_mongo(ticket)
        self._write_to_in_memory(ticket)
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
        collection = self._mongo_collection()
        if collection is None:
            return self._list_from_in_memory(
                user_id=user_id,
                session_id=session_id,
                status=status,
                limit=safe_limit,
            )

        query: dict[str, Any] = {}
        if user_id:
            query["userId"] = user_id
        if session_id:
            query["sessionId"] = session_id
        if status:
            query["status"] = status.strip().lower()

        rows = list(collection.find(query).sort("updatedAt", -1).limit(safe_limit))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("ticketId", None)
            if isinstance(row, dict):
                output.append(row)
        return output

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

    def _write_to_in_memory(self, ticket: dict[str, Any]) -> None:
        if self.store is None:
            return
        ticket_id = str(ticket.get("id", "")).strip()
        if not ticket_id:
            return
        with self.store.lock:
            for index, existing in enumerate(self.store.support_tickets):
                if str(existing.get("id", "")) == ticket_id:
                    self.store.support_tickets[index] = deepcopy(ticket)
                    break
            else:
                self.store.support_tickets.append(deepcopy(ticket))

    def _read_from_in_memory(self, ticket_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        with self.store.lock:
            for ticket in self.store.support_tickets:
                if str(ticket.get("id", "")) == ticket_id:
                    return deepcopy(ticket)
        return None

    def _list_from_in_memory(
        self,
        *,
        user_id: str | None,
        session_id: str | None,
        status: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if self.store is None:
            return []

        normalized_status = status.strip().lower() if isinstance(status, str) and status.strip() else None
        rows: list[dict[str, Any]] = []
        with self.store.lock:
            for ticket in self.store.support_tickets:
                if user_id and str(ticket.get("userId", "")) != user_id:
                    continue
                if session_id and str(ticket.get("sessionId", "")) != session_id:
                    continue
                if normalized_status and str(ticket.get("status", "")).strip().lower() != normalized_status:
                    continue
                rows.append(deepcopy(ticket))

        rows.sort(key=lambda row: str(row.get("updatedAt", "")), reverse=True)
        return rows[:limit]

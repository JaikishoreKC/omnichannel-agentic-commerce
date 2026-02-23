from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.repositories.support_repository import SupportRepository
from app.store.in_memory import InMemoryStore


class SupportService:
    def __init__(
        self,
        store: InMemoryStore,
        support_repository: SupportRepository,
    ) -> None:
        self.store = store
        self.support_repository = support_repository

    def create_ticket(
        self,
        *,
        user_id: str | None,
        session_id: str,
        issue: str,
        priority: str = "normal",
        category: str = "general",
        channel: str = "web",
    ) -> dict[str, Any]:
        normalized_priority = str(priority).strip().lower()
        if normalized_priority not in {"low", "normal", "high", "urgent"}:
            normalized_priority = "normal"
        normalized_category = str(category).strip().lower() or "general"
        ticket = {
            "id": f"ticket_{self.store.next_id('item')}",
            "userId": user_id,
            "sessionId": session_id,
            "issue": issue.strip(),
            "category": normalized_category,
            "priority": normalized_priority,
            "status": "open",
            "channel": channel,
            "messages": [
                {
                    "actor": "customer",
                    "message": issue.strip(),
                    "timestamp": self.store.iso_now(),
                }
            ],
            "resolution": None,
            "createdAt": self.store.iso_now(),
            "updatedAt": self.store.iso_now(),
        }
        return self.support_repository.create(ticket)

    def get_ticket(self, *, ticket_id: str) -> dict[str, Any]:
        row = self.support_repository.get(ticket_id)
        if row is None:
            raise ValueError("ticket_not_found")
        return deepcopy(row)

    def list_tickets(
        self,
        *,
        user_id: str | None,
        session_id: str | None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.support_repository.list(
            user_id=user_id,
            session_id=session_id,
            status=status,
            limit=limit,
        )

    def update_ticket(
        self,
        *,
        ticket_id: str,
        status: str | None = None,
        priority: str | None = None,
        note: str | None = None,
        actor: str = "support",
    ) -> dict[str, Any]:
        ticket = self.support_repository.get(ticket_id)
        if ticket is None:
            raise ValueError("ticket_not_found")

        if status is not None:
            normalized_status = str(status).strip().lower()
            if normalized_status not in {"open", "in_progress", "resolved", "closed"}:
                raise ValueError("invalid_ticket_status")
            ticket["status"] = normalized_status

        if priority is not None:
            normalized_priority = str(priority).strip().lower()
            if normalized_priority not in {"low", "normal", "high", "urgent"}:
                raise ValueError("invalid_ticket_priority")
            ticket["priority"] = normalized_priority

        if note:
            messages = ticket.setdefault("messages", [])
            if isinstance(messages, list):
                messages.append(
                    {
                        "actor": actor,
                        "message": str(note).strip(),
                        "timestamp": self.store.iso_now(),
                    }
                )

        if ticket.get("status") in {"resolved", "closed"}:
            ticket["resolution"] = (note or ticket.get("resolution") or "").strip() or "Resolved by support"
        ticket["updatedAt"] = self.store.iso_now()
        return self.support_repository.update(ticket)

    def ensure_open_ticket(
        self,
        *,
        user_id: str | None,
        session_id: str,
        issue: str,
        category: str,
        priority: str,
        channel: str,
    ) -> dict[str, Any]:
        existing = self.list_tickets(
            user_id=user_id,
            session_id=session_id if user_id is None else None,
            status="open",
            limit=10,
        )
        if existing:
            top = existing[0]
            self.update_ticket(
                ticket_id=str(top["id"]),
                note=f"Customer follow-up: {issue.strip()}",
                actor="customer",
            )
            return self.get_ticket(ticket_id=str(top["id"]))
        return self.create_ticket(
            user_id=user_id,
            session_id=session_id,
            issue=issue,
            priority=priority,
            category=category,
            channel=channel,
        )

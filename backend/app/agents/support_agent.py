from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.support_service import SupportService


class SupportAgent(BaseAgent):
    name = "support"

    def __init__(self, support_service: SupportService) -> None:
        self.support_service = support_service

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        query = str(action.params.get("query", "")).strip()
        lower = query.lower()

        if action.name == "create_ticket":
            category = self._infer_category(lower)
            priority = "high" if any(token in lower for token in ("urgent", "asap", "immediately")) else "normal"
            ticket = self.support_service.ensure_open_ticket(
                user_id=context.user_id,
                session_id=context.session_id,
                issue=query or "User requested human escalation",
                category=category,
                priority=priority,
                channel=context.channel,
            )
            return AgentExecutionResult(
                success=True,
                message=(
                    f"I opened support ticket {ticket['id']} with priority {ticket['priority']}. "
                    "A human agent will follow up soon."
                ),
                data={"escalation": True, "ticket": ticket},
                next_actions=[
                    {"label": "Check ticket status", "action": "ticket status"},
                    {"label": "Continue shopping", "action": "search:running shoes"},
                ],
            )

        if action.name == "ticket_status":
            tickets = self.support_service.list_tickets(
                user_id=context.user_id,
                session_id=context.session_id if context.user_id is None else None,
                status=None,
                limit=10,
            )
            if not tickets:
                return AgentExecutionResult(
                    success=True,
                    message="You have no support tickets yet.",
                    data={"tickets": []},
                    next_actions=[{"label": "Open support ticket", "action": "talk to support"}],
                )
            latest = tickets[0]
            return AgentExecutionResult(
                success=True,
                message=(
                    f"Latest ticket {latest['id']} is {latest['status']} "
                    f"with priority {latest.get('priority', 'normal')}."
                ),
                data={"tickets": tickets[:3], "ticket": latest},
                next_actions=[{"label": "Close ticket", "action": f"close ticket {latest['id']}"}],
            )

        if action.name == "close_ticket":
            ticket_id = str(action.params.get("ticketId", "")).strip()
            if not ticket_id:
                tickets = self.support_service.list_tickets(
                    user_id=context.user_id,
                    session_id=context.session_id if context.user_id is None else None,
                    status="open",
                    limit=1,
                )
                if tickets:
                    ticket_id = str(tickets[0]["id"])
            if not ticket_id:
                return AgentExecutionResult(
                    success=False,
                    message="I couldn't find an open ticket to close.",
                    data={},
                )
            try:
                ticket = self.support_service.update_ticket(
                    ticket_id=ticket_id,
                    status="resolved",
                    note="Customer marked ticket as resolved.",
                    actor="customer",
                )
            except ValueError:
                return AgentExecutionResult(
                    success=False,
                    message=f"I couldn't find ticket {ticket_id}.",
                    data={},
                )
            return AgentExecutionResult(
                success=True,
                message=f"Ticket {ticket['id']} is now marked as resolved.",
                data={"ticket": ticket},
                next_actions=[{"label": "Continue shopping", "action": "search:running shoes"}],
            )

        if "return" in lower:
            return AgentExecutionResult(
                success=True,
                message="Most items can be returned within 30 days if unused and in original packaging.",
                data={"topic": "returns"},
                next_actions=[{"label": "Show shoes", "action": "search:running shoes"}],
            )
        if "size" in lower:
            return AgentExecutionResult(
                success=True,
                message="If you're between sizes, we usually recommend sizing up for running shoes.",
                data={"topic": "sizing"},
                next_actions=[{"label": "Find size 10 shoes", "action": "search:size_10_shoes"}],
            )
        if "human" in lower or "agent" in lower or "ticket" in lower:
            return self.execute(
                AgentAction(name="create_ticket", params={"query": query}),
                context,
            )
        return AgentExecutionResult(
            success=True,
            message="I can help with product search, cart updates, checkout, order status, and returns questions.",
            data={"capabilities": ["search", "cart", "checkout", "order_status", "returns"]},
            next_actions=[
                {"label": "Search products", "action": "search:running shoes"},
                {"label": "Show cart", "action": "view_cart"},
            ],
        )

    @staticmethod
    def _infer_category(lower_query: str) -> str:
        if "order" in lower_query or "delivery" in lower_query:
            return "order_issue"
        if "payment" in lower_query or "refund" in lower_query:
            return "billing_issue"
        if "size" in lower_query or "fit" in lower_query:
            return "sizing"
        return "general"

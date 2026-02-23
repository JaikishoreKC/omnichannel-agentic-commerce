from __future__ import annotations

from app.orchestrator.types import IntentResult


class AgentRouter:
    def route(self, intent: IntentResult) -> str:
        if intent.name in {"product_search", "search_and_add_to_cart"}:
            return "product"
        if intent.name in {
            "add_to_cart",
            "add_multiple_to_cart",
            "apply_discount",
            "update_cart",
            "adjust_cart_quantity",
            "remove_from_cart",
            "clear_cart",
            "view_cart",
        }:
            return "cart"
        if intent.name in {
            "checkout",
            "order_status",
            "cancel_order",
            "request_refund",
            "change_order_address",
        }:
            return "order"
        if intent.name in {"show_memory", "save_preference", "forget_preference", "clear_memory"}:
            return "memory"
        if intent.name in {"support_escalation", "support_status", "support_close"}:
            return "support"
        return "support"

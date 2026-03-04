from __future__ import annotations

from app.orchestrator.types import AgentAction, IntentResult


class ActionExtractor:
    """Maps classified intents to concrete agent actions."""

    _ACTION_MAP: dict[str, tuple[str, str | None, bool]] = {
        "product_search": ("search_products", None, False),
        "add_to_cart": ("add_item", None, False),
        "add_multiple_to_cart": ("add_multiple_items", None, False),
        "apply_discount": ("apply_discount", None, False),
        "update_cart": ("update_item", None, False),
        "adjust_cart_quantity": ("adjust_item_quantity", None, False),
        "remove_from_cart": ("remove_item", None, False),
        "clear_cart": ("clear_cart", "cart", True),
        "view_cart": ("get_cart", "cart", True),
        "checkout": ("checkout_summary", None, True),
        "order_status": ("get_order_status", None, False),
        "cancel_order": ("cancel_order", None, False),
        "request_refund": ("request_refund", None, False),
        "change_order_address": ("change_order_address", None, False),
        "show_memory": ("show_memory", None, True),
        "save_preference": ("save_preference", None, False),
        "forget_preference": ("forget_preference", None, False),
        "clear_memory": ("clear_memory", None, True),
        "support_escalation": ("create_ticket", "support", False),
        "support_status": ("ticket_status", "support", False),
        "support_close": ("close_ticket", "support", False),
    }

    def extract(self, intent: IntentResult) -> list[AgentAction]:
        name = intent.name
        entities = intent.entities

        if name == "multi_status":
            return [
                AgentAction(name="get_cart", params={}, target_agent="cart"),
                AgentAction(name="get_order_status", params=entities, target_agent="order"),
            ]

        if name == "search_and_add_to_cart":
            product_params = {"query": entities.get("query", "")}
            for field in ("size", "color", "brand", "minPrice", "maxPrice"):
                if entities.get(field) is not None:
                    product_params[field] = entities[field]
            return [
                AgentAction(
                    name="search_products",
                    params=product_params,
                    target_agent="product",
                ),
                AgentAction(
                    name="add_item",
                    params={
                        "productId": entities.get("productId"),
                        "variantId": entities.get("variantId"),
                        "size": entities.get("size"),
                        "color": entities.get("color"),
                        "quantity": entities.get("quantity", 1),
                    },
                    target_agent="cart",
                ),
            ]

        mapped = self._ACTION_MAP.get(name)
        if mapped is not None:
            action_name, target_agent, use_empty_params = mapped
            params = {} if use_empty_params else entities
            return [AgentAction(name=action_name, params=params, target_agent=target_agent)]

        return [AgentAction(name="answer_question", params=entities)]

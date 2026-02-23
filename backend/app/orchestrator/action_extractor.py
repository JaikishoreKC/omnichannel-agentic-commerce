from __future__ import annotations

from app.orchestrator.types import AgentAction, IntentResult


class ActionExtractor:
    """Maps classified intents to concrete agent actions."""

    def extract(self, intent: IntentResult) -> list[AgentAction]:
        name = intent.name
        entities = intent.entities

        if name == "multi_status":
            return [
                AgentAction(name="get_cart", params={}, target_agent="cart"),
                AgentAction(name="get_order_status", params=entities, target_agent="order"),
            ]
        if name == "product_search":
            return [AgentAction(name="search_products", params=entities)]
        if name == "search_and_add_to_cart":
            product_params = {"query": entities.get("query", "")}
            if entities.get("size") is not None:
                product_params["size"] = entities["size"]
            if entities.get("color") is not None:
                product_params["color"] = entities["color"]
            if entities.get("brand") is not None:
                product_params["brand"] = entities["brand"]
            if entities.get("minPrice") is not None:
                product_params["minPrice"] = entities["minPrice"]
            if entities.get("maxPrice") is not None:
                product_params["maxPrice"] = entities["maxPrice"]
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
        if name == "add_to_cart":
            return [AgentAction(name="add_item", params=entities)]
        if name == "add_multiple_to_cart":
            return [AgentAction(name="add_multiple_items", params=entities)]
        if name == "apply_discount":
            return [AgentAction(name="apply_discount", params=entities)]
        if name == "update_cart":
            return [AgentAction(name="update_item", params=entities)]
        if name == "adjust_cart_quantity":
            return [AgentAction(name="adjust_item_quantity", params=entities)]
        if name == "remove_from_cart":
            return [AgentAction(name="remove_item", params=entities)]
        if name == "clear_cart":
            return [AgentAction(name="clear_cart", params={})]
        if name == "view_cart":
            return [AgentAction(name="get_cart", params={})]
        if name == "checkout":
            return [AgentAction(name="checkout_summary", params={})]
        if name == "order_status":
            return [AgentAction(name="get_order_status", params=entities)]
        if name == "cancel_order":
            return [AgentAction(name="cancel_order", params=entities)]
        if name == "request_refund":
            return [AgentAction(name="request_refund", params=entities)]
        if name == "change_order_address":
            return [AgentAction(name="change_order_address", params=entities)]
        if name == "show_memory":
            return [AgentAction(name="show_memory", params={})]
        if name == "save_preference":
            return [AgentAction(name="save_preference", params=entities)]
        if name == "forget_preference":
            return [AgentAction(name="forget_preference", params=entities)]
        if name == "clear_memory":
            return [AgentAction(name="clear_memory", params={})]
        if name == "support_escalation":
            return [AgentAction(name="create_ticket", params=entities, target_agent="support")]
        if name == "support_status":
            return [AgentAction(name="ticket_status", params=entities, target_agent="support")]
        if name == "support_close":
            return [AgentAction(name="close_ticket", params=entities, target_agent="support")]
        return [AgentAction(name="answer_question", params=entities)]

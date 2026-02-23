from __future__ import annotations

from typing import Any

import pytest

from app.orchestrator.action_extractor import ActionExtractor
from app.orchestrator.intent_classifier import IntentClassifier


CASES: list[dict[str, Any]] = [
    {
        "id": "product_search_price_filter",
        "message": "show me running shoes under 150",
        "expected_intent": "product_search",
        "expected_actions": ["search_products"],
        "entities": {"maxPrice": 150.0},
    },
    {
        "id": "add_single_with_quantity",
        "message": "add 2 running shoes to cart",
        "expected_intent": "add_to_cart",
        "expected_actions": ["add_item"],
        "entities": {"quantity": 2},
    },
    {
        "id": "add_multiple_items",
        "message": "add 2 running shoes and 1 hoodie to cart",
        "expected_intent": "add_multiple_to_cart",
        "expected_actions": ["add_multiple_items"],
        "entities": {"items_min": 2},
    },
    {
        "id": "view_cart_phrase",
        "message": "show me cart",
        "expected_intent": "view_cart",
        "expected_actions": ["get_cart"],
        "entities": {},
    },
    {
        "id": "clear_cart",
        "message": "please empty my cart",
        "expected_intent": "clear_cart",
        "expected_actions": ["clear_cart"],
        "entities": {},
    },
    {
        "id": "adjust_quantity",
        "message": "increase quantity of hoodie in cart by 2",
        "expected_intent": "adjust_cart_quantity",
        "expected_actions": ["adjust_item_quantity"],
        "entities": {"delta": 2},
    },
    {
        "id": "remove_quantity",
        "message": "remove 2 running shoes from cart",
        "expected_intent": "remove_from_cart",
        "expected_actions": ["remove_item"],
        "entities": {"quantity": 2},
    },
    {
        "id": "checkout",
        "message": "checkout",
        "expected_intent": "checkout",
        "expected_actions": ["checkout_summary"],
        "entities": {},
    },
    {
        "id": "order_status",
        "message": "where is my order order_123",
        "expected_intent": "order_status",
        "expected_actions": ["get_order_status"],
        "entities": {"orderId": "order_123"},
    },
    {
        "id": "multi_status",
        "message": "show my cart and order status",
        "expected_intent": "multi_status",
        "expected_actions": ["get_cart", "get_order_status"],
        "entities": {},
    },
    {
        "id": "discount_code",
        "message": "apply discount code save20",
        "expected_intent": "apply_discount",
        "expected_actions": ["apply_discount"],
        "entities": {"code": "SAVE20"},
    },
    {
        "id": "save_preference",
        "message": "remember i like denim and my size is m",
        "expected_intent": "save_preference",
        "expected_actions": ["save_preference"],
        "entities": {"size": "M", "style": "denim"},
    },
    {
        "id": "show_memory",
        "message": "what do you remember about me",
        "expected_intent": "show_memory",
        "expected_actions": ["show_memory"],
        "entities": {},
    },
    {
        "id": "forget_preference",
        "message": "forget denim",
        "expected_intent": "forget_preference",
        "expected_actions": ["forget_preference"],
        "entities": {"value": "denim"},
    },
    {
        "id": "clear_memory",
        "message": "clear my memory",
        "expected_intent": "clear_memory",
        "expected_actions": ["clear_memory"],
        "entities": {},
    },
    {
        "id": "support_escalation",
        "message": "connect me to support agent for payment issue",
        "expected_intent": "support_escalation",
        "expected_actions": ["create_ticket"],
        "entities": {},
    },
    {
        "id": "support_status",
        "message": "ticket status",
        "expected_intent": "support_status",
        "expected_actions": ["ticket_status"],
        "entities": {},
    },
    {
        "id": "support_close",
        "message": "close ticket ticket_123",
        "expected_intent": "support_close",
        "expected_actions": ["close_ticket"],
        "entities": {"ticketId": "ticket_123"},
    },
    {
        "id": "id_based_add",
        "message": "add prod_001 var_001 to cart",
        "expected_intent": "add_to_cart",
        "expected_actions": ["add_item"],
        "entities": {"productId": "prod_001", "variantId": "var_001"},
    },
    {
        "id": "price_refinement",
        "message": "under 150",
        "context": {"recent": [{"intent": "product_search", "agent": "product"}]},
        "expected_intent": "product_search",
        "expected_actions": ["search_products"],
        "entities": {"maxPrice": 150.0},
    },
]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_nl_intent_and_action_eval(case: dict[str, Any]) -> None:
    classifier = IntentClassifier()
    extractor = ActionExtractor()

    message = str(case["message"])
    context = case.get("context")
    result = classifier.classify(message=message, context=context)

    assert result.name == case["expected_intent"]

    actions = extractor.extract(result)
    action_names = [action.name for action in actions]
    assert action_names == case["expected_actions"]

    expected_entities = case.get("entities", {})
    if "maxPrice" in expected_entities:
        assert result.entities.get("maxPrice") == expected_entities["maxPrice"]
    if "quantity" in expected_entities:
        assert result.entities.get("quantity") == expected_entities["quantity"]
    if "delta" in expected_entities:
        assert result.entities.get("delta") == expected_entities["delta"]
    if "orderId" in expected_entities:
        assert result.entities.get("orderId") == expected_entities["orderId"]
    if "code" in expected_entities:
        assert result.entities.get("code") == expected_entities["code"]
    if "value" in expected_entities:
        assert result.entities.get("value") == expected_entities["value"]
    if "ticketId" in expected_entities:
        assert result.entities.get("ticketId") == expected_entities["ticketId"]
    if "productId" in expected_entities:
        assert result.entities.get("productId") == expected_entities["productId"]
    if "variantId" in expected_entities:
        assert result.entities.get("variantId") == expected_entities["variantId"]
    if "size" in expected_entities:
        updates = result.entities.get("updates", {})
        assert isinstance(updates, dict)
        assert updates.get("size") == expected_entities["size"]
    if "style" in expected_entities:
        updates = result.entities.get("updates", {})
        assert isinstance(updates, dict)
        styles = updates.get("stylePreferences", [])
        assert isinstance(styles, list)
        assert expected_entities["style"] in styles
    if "items_min" in expected_entities:
        items = result.entities.get("items", [])
        assert isinstance(items, list)
        assert len(items) >= int(expected_entities["items_min"])

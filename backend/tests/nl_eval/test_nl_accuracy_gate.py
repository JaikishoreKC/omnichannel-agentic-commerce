from __future__ import annotations

from typing import Any

from app.orchestrator.action_extractor import ActionExtractor
from app.orchestrator.intent_classifier import IntentClassifier


def _build_eval_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    products = [
        "running shoes",
        "hoodie",
        "trail shoes",
        "sports socks",
        "training backpack",
        "water bottle",
    ]
    quantities = [1, 2, 3, 4, 5]

    for quantity in quantities:
        for product in products:
            cases.append(
                {
                    "message": f"add {quantity} {product} to cart",
                    "intent": "add_to_cart",
                    "actions": ["add_item"],
                }
            )
            cases.append(
                {
                    "message": f"remove {quantity} {product} from cart",
                    "intent": "remove_from_cart",
                    "actions": ["remove_item"],
                }
            )

    for product in products:
        cases.append(
            {
                "message": f"find {product} under 150",
                "intent": "product_search",
                "actions": ["search_products"],
            }
        )
        cases.append(
            {
                "message": f"search {product} over 40",
                "intent": "product_search",
                "actions": ["search_products"],
            }
        )

    for code in ["SAVE10", "SAVE20", "SUMMER25", "WELCOME5", "VIP30"]:
        cases.append(
            {
                "message": f"apply discount code {code}",
                "intent": "apply_discount",
                "actions": ["apply_discount"],
            }
        )

    for order_idx in range(101, 136):
        cases.append(
            {
                "message": f"where is my order order_{order_idx}",
                "intent": "order_status",
                "actions": ["get_order_status"],
            }
        )
        cases.append(
            {
                "message": f"cancel order order_{order_idx}",
                "intent": "cancel_order",
                "actions": ["cancel_order"],
            }
        )

    for ticket_idx in range(301, 341):
        cases.append(
            {
                "message": f"ticket status ticket_{ticket_idx}",
                "intent": "support_status",
                "actions": ["ticket_status"],
            }
        )
        cases.append(
            {
                "message": f"close ticket ticket_{ticket_idx}",
                "intent": "support_close",
                "actions": ["close_ticket"],
            }
        )

    for color in ["black", "blue", "white", "green", "navy"]:
        for size in ["M", "L", "10"]:
            cases.append(
                {
                    "message": f"remember I like {color} and my size is {size}",
                    "intent": "save_preference",
                    "actions": ["save_preference"],
                }
            )

    for price in [90, 110, 130, 150, 170, 190, 210, 230, 250, 270, 290, 310, 330, 350, 370]:
        cases.append(
            {
                "message": f"under {price}",
                "context": {"recent": [{"intent": "product_search", "agent": "product"}]},
                "intent": "product_search",
                "actions": ["search_products"],
            }
        )

    for _ in range(10):
        cases.append(
            {
                "message": "show my cart and order status",
                "intent": "multi_status",
                "actions": ["get_cart", "get_order_status"],
            }
        )
        cases.append(
            {
                "message": "show me cart",
                "intent": "view_cart",
                "actions": ["get_cart"],
            }
        )
        cases.append(
            {
                "message": "please empty my cart",
                "intent": "clear_cart",
                "actions": ["clear_cart"],
            }
        )
        cases.append(
            {
                "message": "checkout",
                "intent": "checkout",
                "actions": ["checkout_summary"],
            }
        )

    return cases


CASES = _build_eval_cases()


def test_nl_eval_accuracy_gate() -> None:
    classifier = IntentClassifier()
    extractor = ActionExtractor()

    intent_correct = 0
    action_correct = 0

    for case in CASES:
        message = str(case["message"])
        context = case.get("context")
        expected_intent = str(case["intent"])
        expected_actions = list(case["actions"])

        result = classifier.classify(message=message, context=context)
        actions = extractor.extract(result)
        action_names = [action.name for action in actions]

        if result.name == expected_intent:
            intent_correct += 1
        if action_names == expected_actions:
            action_correct += 1

    total = len(CASES)
    assert total >= 200

    intent_accuracy = intent_correct / total
    action_accuracy = action_correct / total

    assert intent_accuracy >= 0.95, (
        f"Intent accuracy below threshold: {intent_accuracy:.3f} < 0.950 "
        f"({intent_correct}/{total})"
    )
    assert action_accuracy >= 0.95, (
        f"Action accuracy below threshold: {action_accuracy:.3f} < 0.950 "
        f"({action_correct}/{total})"
    )

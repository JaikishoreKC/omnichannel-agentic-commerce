from __future__ import annotations

import time

from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.infrastructure.llm_client import LLMIntentPrediction
from app.orchestrator.intent_classifier import IntentClassifier


class _StubLLMClient:
    def __init__(self, prediction: LLMIntentPrediction | None) -> None:
        self.prediction = prediction

    def classify_intent(self, *, message: str, recent_messages: list[dict[str, object]] | None = None) -> LLMIntentPrediction | None:
        return self.prediction


def test_circuit_breaker_opens_and_recovers() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.1)

    def fail() -> int:
        raise RuntimeError("boom")

    for _ in range(2):
        try:
            breaker.call(fail)
        except RuntimeError:
            pass

    assert breaker.snapshot.state == "open"

    try:
        breaker.call(lambda: 1)
    except CircuitBreakerOpenError:
        pass
    else:
        raise AssertionError("Expected CircuitBreakerOpenError while breaker is open")

    time.sleep(0.12)
    assert breaker.call(lambda: 7) == 7
    assert breaker.snapshot.state == "closed"


def test_intent_classifier_prefers_higher_confidence_llm_result() -> None:
    llm_prediction = LLMIntentPrediction(
        intent="checkout",
        confidence=0.82,
        entities={},
    )
    classifier = IntentClassifier(llm_client=_StubLLMClient(llm_prediction))
    result = classifier.classify("please help me complete payment", context={"recent": []})
    assert result.name == "checkout"
    assert result.confidence == 0.82


def test_intent_classifier_detects_search_and_add_combo() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("find running shoes under $150 and add to cart")
    assert result.name == "search_and_add_to_cart"
    assert result.entities["maxPrice"] == 150.0


def test_intent_classifier_detects_discount_code() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("please apply discount code SAVE20")
    assert result.name == "apply_discount"
    assert result.entities["code"] == "SAVE20"


def test_intent_classifier_detects_delayed_order_phrase() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("my order hasn't arrived yet")
    assert result.name == "order_status"


def test_intent_classifier_detects_clear_cart() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("please clear my cart")
    assert result.name == "clear_cart"


def test_intent_classifier_detects_multi_item_add() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("add 2 running shoes and 1 hoodie to cart")
    assert result.name == "add_multiple_to_cart"
    assert len(result.entities["items"]) >= 2


def test_intent_classifier_detects_adjust_quantity_delta() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("increase quantity of hoodie in cart by 2")
    assert result.name == "adjust_cart_quantity"
    assert result.entities["delta"] == 2


def test_intent_classifier_detects_save_preference() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("remember I like denim and my size is M")
    assert result.name == "save_preference"
    updates = result.entities["updates"]
    assert "denim" in updates["stylePreferences"]
    assert updates["size"] == "M"


def test_intent_classifier_detects_show_memory() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("what do you remember about me")
    assert result.name == "show_memory"


def test_intent_classifier_detects_forget_preference() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("forget denim")
    assert result.name == "forget_preference"
    assert result.entities["value"] == "denim"


def test_intent_classifier_detects_clear_memory() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("clear my memory")
    assert result.name == "clear_memory"

def test_intent_classifier_detects_view_cart_phrases() -> None:
    classifier = IntentClassifier()
    for utterance in ("show me cart", "view cart", "view_cart", "my cart"):
        result = classifier.classify(utterance)
        assert result.name == "view_cart"


def test_intent_classifier_detects_bare_product_query() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("running shoes")
    assert result.name == "product_search"


def test_intent_classifier_detects_price_refinement_query() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("under 150", context={"recent": [{"intent": "product_search", "agent": "product"}]})
    assert result.name == "product_search"
    assert result.entities["maxPrice"] == 150.0


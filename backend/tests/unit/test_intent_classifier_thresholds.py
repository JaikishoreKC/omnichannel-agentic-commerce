from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.llm_client import LLMIntentPrediction
from app.orchestrator.intent_classifier import IntentClassifier


class _StubLLMClient:
    def __init__(self, prediction: LLMIntentPrediction, settings: Settings | None = None) -> None:
        self.prediction = prediction
        self.settings = settings or Settings()

    def classify_intent(self, *, message: str, recent_messages: list[dict[str, object]] | None = None) -> LLMIntentPrediction | None:
        _ = (message, recent_messages)
        return self.prediction


def test_classifier_uses_default_floor_when_override_missing() -> None:
    classifier = IntentClassifier(
        llm_client=_StubLLMClient(
            LLMIntentPrediction(intent="checkout", confidence=0.74, entities={}),
            settings=Settings(intent_confidence_thresholds_json="{}"),
        )
    )

    result = classifier.classify("please help", context={"recent": []})
    assert result.name == "checkout"


def test_classifier_respects_intent_specific_override_floor() -> None:
    classifier = IntentClassifier(
        llm_client=_StubLLMClient(
            LLMIntentPrediction(intent="checkout", confidence=0.74, entities={}),
            settings=Settings(intent_confidence_thresholds_json='{"checkout": 0.8}'),
        )
    )

    result = classifier.classify("please help", context={"recent": []})
    assert result.name == "general_question"


def test_settings_intent_threshold_parser_clamps_and_filters_invalid_values() -> None:
    settings = Settings(
        intent_confidence_thresholds_json='{"checkout": 1.4, "general_question": 0.45, "bad": "oops", "": 0.2}'
    )

    parsed = settings.intent_confidence_thresholds
    assert parsed["checkout"] == 1.0
    assert parsed["general_question"] == 0.45
    assert "bad" not in parsed
    assert "" not in parsed

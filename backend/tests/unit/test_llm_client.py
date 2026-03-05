from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.circuit_breaker import CircuitBreakerOpenError
from app.infrastructure.llm_client import LLMClient

class _DummyResponse:
    def __init__(self, payload: dict[str, Any], *, error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> dict[str, Any]:
        return self._payload

def _base_settings(**overrides: Any) -> Settings:
    data = {
        "llm_enabled": True,
        "llm_provider": "openrouter",
        "llm_model": "meta-llama/llama-3.1-8b-instruct:free",
        "openrouter_api_key": "sk-test",
        "llm_timeout_seconds": 3.0,
        "llm_max_tokens": 128,
        "llm_intent_classifier_enabled": True,
        "llm_planner_enabled": False,
        "llm_planner_max_actions": 5,
        "llm_planner_min_confidence": 0.55,
        "llm_decision_policy": "planner_first",
    }
    data.update(overrides)
    return Settings(**data)

def _planner_settings(**overrides: Any) -> Settings:
    planner_overrides = {
        "llm_intent_classifier_enabled": False,
        "llm_planner_enabled": True,
    }
    planner_overrides.update(overrides)
    return _base_settings(**planner_overrides)

def test_enabled_flag_checks_api_key() -> None:
    disabled = LLMClient(settings=_base_settings(llm_enabled=False))
    assert disabled.enabled is False

    key_missing = LLMClient(settings=_base_settings(openrouter_api_key=""))
    assert key_missing.enabled is False

    enabled = LLMClient(settings=_base_settings())
    assert enabled.enabled is True


def test_enabled_flag_accepts_role_specific_keys_without_primary() -> None:
    planner_only = LLMClient(
        settings=_base_settings(openrouter_api_key="", openrouter_api_key_planner="sk-plan", openrouter_api_key_general="")
    )
    assert planner_only.enabled is True

    general_only = LLMClient(
        settings=_base_settings(openrouter_api_key="", openrouter_api_key_planner="", openrouter_api_key_general="sk-gen")
    )
    assert general_only.enabled is True


def test_resolve_openrouter_api_key_prefers_role_specific_then_fallback() -> None:
    client = LLMClient(
        settings=_base_settings(
            openrouter_api_key="sk-primary",
            openrouter_api_key_planner="sk-plan",
            openrouter_api_key_general="sk-gen",
        )
    )
    assert client._resolve_openrouter_api_key(role=LLMClient.KEY_ROLE_PLANNER) == "sk-plan"
    assert client._resolve_openrouter_api_key(role=LLMClient.KEY_ROLE_GENERAL) == "sk-gen"

    fallback_client = LLMClient(
        settings=_base_settings(
            openrouter_api_key="",
            openrouter_api_key_planner="sk-plan",
            openrouter_api_key_general="",
        )
    )
    assert fallback_client._resolve_openrouter_api_key(role=LLMClient.KEY_ROLE_GENERAL) == "sk-plan"

def test_classify_intent_returns_none_when_disabled() -> None:
    client = LLMClient(settings=_base_settings(llm_enabled=False))
    assert client.classify_intent(message="show me shoes") is None

def test_classify_intent_disabled_when_planner_enabled() -> None:
    # Default policy is planner_first, which disables classifier if planner is enabled
    client = LLMClient(settings=_base_settings(llm_planner_enabled=True, llm_intent_classifier_enabled=True))
    assert client.classify_intent(message="checkout") is None

def test_classify_intent_enabled_when_classifier_first_policy() -> None:
    client = LLMClient(
        settings=_base_settings(
            llm_planner_enabled=True,
            llm_decision_policy="classifier_first",
        )
    )
    client._call_llm = lambda user_prompt, system_prompt, role=None: '{"intent":"checkout","confidence":0.9,"entities":{}}'  # type: ignore[method-assign]
    prediction = client.classify_intent(message="checkout")
    assert prediction is not None
    assert prediction.intent == "checkout"

def test_classify_intent_parses_valid_json_and_clamps_confidence() -> None:
    client = LLMClient(settings=_base_settings())
    client._call_llm = lambda user_prompt, system_prompt, role=None: '{"intent":"apply_discount","confidence":4,"entities":{"code":"SAVE20"}}'  # type: ignore[method-assign]
    prediction = client.classify_intent(message="apply code SAVE20")
    assert prediction is not None
    assert prediction.intent == "apply_discount"
    assert prediction.confidence == 1.0
    assert prediction.entities["code"] == "SAVE20"

def test_classify_intent_rejects_unsupported_or_invalid_payload() -> None:
    client = LLMClient(settings=_base_settings())
    client._call_llm = lambda user_prompt, system_prompt, role=None: '{"intent":"unknown","confidence":0.8}'  # type: ignore[method-assign]
    assert client.classify_intent(message="hello") is None

    client._call_llm = lambda user_prompt, system_prompt, role=None: '{"intent":"checkout","confidence":"bad","entities":[]}'  # type: ignore[method-assign]
    parsed = client.classify_intent(message="checkout")
    assert parsed is not None
    assert parsed.confidence == 0.0
    assert parsed.entities == {}

def test_classify_intent_handles_wrapped_json_text() -> None:
    client = LLMClient(settings=_base_settings())
    client._call_llm = (  # type: ignore[method-assign]
        lambda user_prompt, system_prompt, role=None: 'model said:\n{"intent":"checkout","confidence":0.73,"entities":{}}\nthanks'
    )
    prediction = client.classify_intent(message="buy now")
    assert prediction is not None
    assert prediction.intent == "checkout"
    assert prediction.confidence == 0.73

def test_classify_intent_handles_circuit_open_and_exceptions() -> None:
    client = LLMClient(settings=_base_settings())
    client.circuit_breaker.call = lambda fn: (_ for _ in ()).throw(CircuitBreakerOpenError("open"))  # type: ignore[method-assign]
    assert client.classify_intent(message="search shoes") is None

    client.circuit_breaker.call = lambda fn: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]
    assert client.classify_intent(message="search shoes") is None

def test_call_llm_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> _DummyResponse:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"intent":"checkout","confidence":0.9,"entities":{}}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LLMClient(settings=_base_settings())
    raw = client._call_llm(user_prompt="prompt", system_prompt="system")
    assert '"intent":"checkout"' in raw
    assert captured["url"].endswith("/chat/completions")
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer sk-test"


def test_call_llm_uses_role_specific_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> _DummyResponse:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"intent":"checkout","confidence":0.9,"entities":{}}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LLMClient(
        settings=_base_settings(
            openrouter_api_key="sk-primary",
            openrouter_api_key_planner="sk-plan",
            openrouter_api_key_general="sk-gen",
        )
    )
    _ = client._call_llm(user_prompt="prompt", system_prompt="system", role=LLMClient.KEY_ROLE_GENERAL)
    assert captured["url"].endswith("/chat/completions")
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer sk-gen"


def test_extract_completion_content_supports_message_and_delta() -> None:
    assert (
        LLMClient._extract_completion_content(
            {"choices": [{"message": {"content": "message content"}}]}
        )
        == "message content"
    )
    assert (
        LLMClient._extract_completion_content(
            {"choices": [{"delta": {"content": "delta content"}}]}
        )
        == "delta content"
    )


def test_extract_stream_content_returns_empty_string_for_unknown_shape() -> None:
    assert LLMClient._extract_stream_content({"choices": [{"foo": "bar"}]}) == ""

def test_call_llm_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LLMClient(settings=_base_settings())

    with pytest.raises(ValueError):
        LLMClient(settings=_base_settings(openrouter_api_key=""))._call_llm(user_prompt="?", system_prompt="?")

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: _DummyResponse({"choices": []}))
    with pytest.raises(ValueError):
        client._call_llm(user_prompt="?", system_prompt="?")


def test_call_llm_raises_when_called_inside_running_loop() -> None:
    client = LLMClient(settings=_base_settings())

    async def _invoke_inside_loop() -> None:
        with pytest.raises(RuntimeError, match="Synchronous _call_llm called from async context"):
            client._call_llm(user_prompt="prompt", system_prompt="system")

    asyncio.run(_invoke_inside_loop())

def test_plan_actions_parses_multi_action_payload() -> None:
    client = LLMClient(settings=_planner_settings())
    client._call_llm = (  # type: ignore[method-assign]
        lambda user_prompt, system_prompt, role=None: (
            '{"actions":[{"name":"add_item","targetAgent":"cart","params":{"query":"running shoes","quantity":2}},'
            '{"name":"add_item","targetAgent":"cart","params":{"query":"training backpack","quantity":1}}],'
            '"confidence":0.93,"needsClarification":false,"clarificationQuestion":""}'
        )
    )
    plan = client.plan_actions(message="add running shoes x2 and training backpack x1 to cart")
    assert plan is not None
    assert plan.needs_clarification is False
    assert plan.confidence == 0.93
    assert len(plan.actions) == 2
    assert plan.actions[0].name == "add_item"
    assert plan.actions[0].target_agent == "cart"
    assert plan.actions[0].params["query"] == "running shoes"
    assert plan.actions[0].params["quantity"] == 2

def test_plan_actions_returns_clarification_when_requested() -> None:
    client = LLMClient(settings=_planner_settings())
    client._call_llm = (  # type: ignore[method-assign]
        lambda user_prompt, system_prompt, role=None: (
            '{"actions":[],"confidence":0.9,"needsClarification":true,'
            '"clarificationQuestion":"Which size and color should I add?"}'
        )
    )
    plan = client.plan_actions(message="add running shoes to cart")
    assert plan is not None
    assert plan.needs_clarification is True
    assert plan.actions == []
    assert "size and color" in plan.clarification_question

def test_plan_actions_ignores_low_confidence_or_unsupported_actions() -> None:
    client = LLMClient(settings=_planner_settings())
    client._call_llm = (  # type: ignore[method-assign]
        lambda user_prompt, system_prompt, role=None: (
            '{"actions":[{"name":"drop_database","targetAgent":"orchestrator","params":{}}],'
            '"confidence":0.99,"needsClarification":false,"clarificationQuestion":""}'
        )
    )
    assert client.plan_actions(message="do something unsafe") is None

    client._call_llm = (  # type: ignore[method-assign]
        lambda user_prompt, system_prompt, role=None: (
            '{"actions":[{"name":"clear_cart","targetAgent":"cart","params":{}}],'
            '"confidence":0.2,"needsClarification":false,"clarificationQuestion":""}'
        )
    )
    assert client.plan_actions(message="empty my cart") is None

def test_plan_actions_sanitizes_unknown_params() -> None:
    client = LLMClient(settings=_planner_settings())
    client._call_llm = (  # type: ignore[method-assign]
        lambda user_prompt, system_prompt, role=None: (
            '{"actions":[{"name":"add_item","targetAgent":"cart",'
            '"params":{"query":"running shoes","quantity":2,"unsupported":"x",'
            '"items":[{"query":"bad"}]}}],'
            '"confidence":0.9,"needsClarification":false,"clarificationQuestion":""}'
        )
    )
    plan = client.plan_actions(message="add running shoes")
    assert plan is not None
    assert len(plan.actions) == 1
    params = plan.actions[0].params
    assert params["query"] == "running shoes"
    assert params["quantity"] == 2
    assert "unsupported" not in params
    assert "items" not in params

def test_plan_actions_respects_configured_limits() -> None:
    client = LLMClient(settings=_planner_settings(llm_planner_max_actions=1, llm_planner_min_confidence=0.9))
    client._call_llm = (  # type: ignore[method-assign]
        lambda user_prompt, system_prompt, role=None: (
            '{"actions":[{"name":"add_item","targetAgent":"cart","params":{"query":"running shoes","quantity":1}},'
            '{"name":"add_item","targetAgent":"cart","params":{"query":"hoodie","quantity":1}}],'
            '"confidence":0.91,"needsClarification":false,"clarificationQuestion":""}'
        )
    )
    plan = client.plan_actions(message="add shoes and hoodie")
    assert plan is not None
    assert len(plan.actions) == 1

def test_build_action_plan_prompt_contains_allowed_actions() -> None:
    client = LLMClient(settings=_base_settings())
    prompt = client._build_action_plan_prompt(
        message="add running shoes",
        recent_messages=[{"message": "show me shoes", "intent": "product_search", "agent": "product"}],
        inferred_intent="add_to_cart",
        allowed_actions=["add_item", "get_cart"],
    )
    payload = json.loads(prompt)
    assert payload["message"] == "add running shoes"
    assert payload["inferredIntent"] == "add_to_cart"
    assert payload["allowedActions"] == ["add_item", "get_cart"]
    assert payload["recent"][0]["intent"] == "product_search"

from __future__ import annotations

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
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "openai_api_key": "sk-test",
        "anthropic_api_key": "sk-ant-test",
        "llm_timeout_seconds": 3.0,
        "llm_max_tokens": 128,
    }
    data.update(overrides)
    return Settings(**data)


def test_enabled_flag_checks_provider_keys() -> None:
    disabled = LLMClient(settings=_base_settings(llm_enabled=False))
    assert disabled.enabled is False

    openai_missing = LLMClient(settings=_base_settings(openai_api_key="", llm_provider="openai"))
    assert openai_missing.enabled is False

    anthropic_missing = LLMClient(
        settings=_base_settings(anthropic_api_key="", llm_provider="anthropic")
    )
    assert anthropic_missing.enabled is False

    enabled = LLMClient(settings=_base_settings())
    assert enabled.enabled is True


def test_classify_intent_returns_none_when_disabled() -> None:
    client = LLMClient(settings=_base_settings(llm_enabled=False))
    assert client.classify_intent(message="show me shoes") is None


def test_classify_intent_parses_valid_json_and_clamps_confidence() -> None:
    client = LLMClient(settings=_base_settings())
    client._call_intent_model = lambda _prompt: '{"intent":"apply_discount","confidence":4,"entities":{"code":"SAVE20"}}'  # type: ignore[method-assign]
    prediction = client.classify_intent(message="apply code SAVE20")
    assert prediction is not None
    assert prediction.intent == "apply_discount"
    assert prediction.confidence == 1.0
    assert prediction.entities["code"] == "SAVE20"


def test_classify_intent_rejects_unsupported_or_invalid_payload() -> None:
    client = LLMClient(settings=_base_settings())
    client._call_intent_model = lambda _prompt: '{"intent":"unknown","confidence":0.8}'  # type: ignore[method-assign]
    assert client.classify_intent(message="hello") is None

    client._call_intent_model = lambda _prompt: '{"intent":"checkout","confidence":"bad","entities":[]}'  # type: ignore[method-assign]
    parsed = client.classify_intent(message="checkout")
    assert parsed is not None
    assert parsed.confidence == 0.0
    assert parsed.entities == {}


def test_classify_intent_handles_wrapped_json_text() -> None:
    client = LLMClient(settings=_base_settings())
    client._call_intent_model = (  # type: ignore[method-assign]
        lambda _prompt: 'model said:\n{"intent":"checkout","confidence":0.73,"entities":{}}\nthanks'
    )
    prediction = client.classify_intent(message="buy now")
    assert prediction is not None
    assert prediction.intent == "checkout"
    assert prediction.confidence == 0.73


def test_classify_intent_handles_circuit_open_and_exceptions() -> None:
    client = LLMClient(settings=_base_settings())
    client.circuit_breaker.call = lambda _fn: (_ for _ in ()).throw(CircuitBreakerOpenError("open"))  # type: ignore[method-assign]
    assert client.classify_intent(message="search shoes") is None

    client.circuit_breaker.call = lambda _fn: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]
    assert client.classify_intent(message="search shoes") is None


def test_call_intent_model_rejects_unknown_provider() -> None:
    client = LLMClient(settings=_base_settings(llm_provider="unknown"))
    with pytest.raises(ValueError):
        client._call_intent_model("hello")


def test_openai_call_success(monkeypatch: pytest.MonkeyPatch) -> None:
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
    raw = client._call_openai("prompt")
    assert '"intent":"checkout"' in raw
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer sk-test"


def test_openai_call_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LLMClient(settings=_base_settings())

    with pytest.raises(ValueError):
        LLMClient(settings=_base_settings(openai_api_key=""))._call_openai("prompt")

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: _DummyResponse({"choices": []}))
    with pytest.raises(ValueError):
        client._call_openai("prompt")

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *_args, **_kwargs: _DummyResponse({"choices": [{"message": {"content": 123}}]}),
    )
    with pytest.raises(ValueError):
        client._call_openai("prompt")


def test_anthropic_call_success_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LLMClient(settings=_base_settings(llm_provider="anthropic"))

    def success_post(*_args: Any, **_kwargs: Any) -> _DummyResponse:
        return _DummyResponse(
            {
                "content": [
                    {
                        "text": '{"intent":"order_status","confidence":0.8,"entities":{"orderId":"order_1"}}'
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", success_post)
    raw = client._call_anthropic("prompt")
    assert '"intent":"order_status"' in raw

    with pytest.raises(ValueError):
        LLMClient(
            settings=_base_settings(llm_provider="anthropic", anthropic_api_key="")
        )._call_anthropic("prompt")

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: _DummyResponse({"content": []}))
    with pytest.raises(ValueError):
        client._call_anthropic("prompt")

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: _DummyResponse({"content": ["bad"]}))
    with pytest.raises(ValueError):
        client._call_anthropic("prompt")

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *_args, **_kwargs: _DummyResponse({"content": [{"text": 12}]}),
    )
    with pytest.raises(ValueError):
        client._call_anthropic("prompt")



def test_plan_actions_parses_multi_action_payload() -> None:
    client = LLMClient(settings=_base_settings())
    client._call_action_planner_model = (  # type: ignore[method-assign]
        lambda _prompt: (
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
    client = LLMClient(settings=_base_settings())
    client._call_action_planner_model = (  # type: ignore[method-assign]
        lambda _prompt: (
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
    client = LLMClient(settings=_base_settings())
    client._call_action_planner_model = (  # type: ignore[method-assign]
        lambda _prompt: (
            '{"actions":[{"name":"drop_database","targetAgent":"orchestrator","params":{}}],'
            '"confidence":0.99,"needsClarification":false,"clarificationQuestion":""}'
        )
    )
    assert client.plan_actions(message="do something unsafe") is None

    client._call_action_planner_model = (  # type: ignore[method-assign]
        lambda _prompt: (
            '{"actions":[{"name":"clear_cart","targetAgent":"cart","params":{}}],'
            '"confidence":0.2,"needsClarification":false,"clarificationQuestion":""}'
        )
    )
    assert client.plan_actions(message="empty my cart") is None


def test_plan_actions_sanitizes_unknown_params() -> None:
    client = LLMClient(settings=_base_settings())
    client._call_action_planner_model = (  # type: ignore[method-assign]
        lambda _prompt: (
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


def test_call_action_planner_model_dispatches_and_rejects_unknown_provider() -> None:
    openai_client = LLMClient(settings=_base_settings(llm_provider="openai"))
    openai_client._call_openai_with_system = (  # type: ignore[method-assign]
        lambda *, user_prompt, system_prompt: f"openai:{len(user_prompt)}:{len(system_prompt)}"
    )
    assert openai_client._call_action_planner_model("hello").startswith("openai:")

    anthropic_client = LLMClient(settings=_base_settings(llm_provider="anthropic"))
    anthropic_client._call_anthropic_with_system = (  # type: ignore[method-assign]
        lambda *, user_prompt, system_prompt: f"anthropic:{len(user_prompt)}:{len(system_prompt)}"
    )
    assert anthropic_client._call_action_planner_model("hello").startswith("anthropic:")

    unknown_client = LLMClient(settings=_base_settings(llm_provider="unknown"))
    with pytest.raises(ValueError):
        unknown_client._call_action_planner_model("hello")


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

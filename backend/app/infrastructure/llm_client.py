from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.infrastructure.prompts import ACTION_PLANNING_PROMPT, INTENT_CLASSIFICATION_PROMPT


@dataclass
class LLMIntentPrediction:
    intent: str
    confidence: float
    entities: dict[str, Any]


@dataclass
class LLMPlannedAction:
    name: str
    target_agent: str | None
    params: dict[str, Any]


@dataclass
class LLMActionPlan:
    actions: list[LLMPlannedAction]
    confidence: float
    needs_clarification: bool
    clarification_question: str


class LLMClient:
    SUPPORTED_INTENTS = {
        "product_search",
        "search_and_add_to_cart",
        "add_to_cart",
        "add_multiple_to_cart",
        "apply_discount",
        "update_cart",
        "adjust_cart_quantity",
        "remove_from_cart",
        "clear_cart",
        "view_cart",
        "checkout",
        "order_status",
        "change_order_address",
        "cancel_order",
        "request_refund",
        "multi_status",
        "show_memory",
        "save_preference",
        "forget_preference",
        "clear_memory",
        "general_question",
    }

    SUPPORTED_TARGET_AGENTS = {"product", "cart", "order", "memory", "support", "orchestrator"}

    SUPPORTED_PLANNER_ACTIONS: dict[str, dict[str, Any]] = {
        "search_products": {
            "target": "product",
            "allowedParams": {"query", "category", "brand", "minPrice", "maxPrice", "color"},
        },
        "add_item": {
            "target": "cart",
            "allowedParams": {"query", "productId", "variantId", "quantity", "brand", "color", "minPrice", "maxPrice"},
        },
        "add_multiple_items": {
            "target": "cart",
            "allowedParams": {"items"},
        },
        "update_item": {
            "target": "cart",
            "allowedParams": {"itemId", "productId", "variantId", "query", "quantity"},
        },
        "adjust_item_quantity": {
            "target": "cart",
            "allowedParams": {"itemId", "productId", "variantId", "query", "delta"},
        },
        "remove_item": {
            "target": "cart",
            "allowedParams": {"itemId", "productId", "variantId", "query", "quantity"},
        },
        "clear_cart": {
            "target": "cart",
            "allowedParams": set(),
        },
        "get_cart": {
            "target": "cart",
            "allowedParams": set(),
        },
        "apply_discount": {
            "target": "cart",
            "allowedParams": {"code"},
        },
        "checkout_summary": {
            "target": "order",
            "allowedParams": set(),
        },
        "get_order_status": {
            "target": "order",
            "allowedParams": {"orderId"},
        },
        "cancel_order": {
            "target": "order",
            "allowedParams": {"orderId", "reason"},
        },
        "request_refund": {
            "target": "order",
            "allowedParams": {"orderId", "reason"},
        },
        "change_order_address": {
            "target": "order",
            "allowedParams": {"orderId", "shippingAddress"},
        },
        "show_memory": {
            "target": "memory",
            "allowedParams": set(),
        },
        "save_preference": {
            "target": "memory",
            "allowedParams": {"updates"},
        },
        "forget_preference": {
            "target": "memory",
            "allowedParams": {"key", "value"},
        },
        "clear_memory": {
            "target": "memory",
            "allowedParams": set(),
        },
        "create_ticket": {
            "target": "support",
            "allowedParams": {"query", "priority", "ticketId"},
        },
        "ticket_status": {
            "target": "support",
            "allowedParams": {"ticketId"},
        },
        "close_ticket": {
            "target": "support",
            "allowedParams": {"ticketId"},
        },
        "answer_question": {
            "target": "support",
            "allowedParams": {"query"},
        },
    }

    MAX_PLAN_ACTIONS = 5
    PLAN_CONFIDENCE_FLOOR = 0.55

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.llm_circuit_breaker_failure_threshold,
            recovery_timeout_seconds=settings.llm_circuit_breaker_timeout_seconds,
        )

    @property
    def enabled(self) -> bool:
        if not self.settings.llm_enabled:
            return False
        provider = self.settings.llm_provider.strip().lower()
        if provider == "openai":
            return bool(self.settings.openai_api_key)
        if provider == "anthropic":
            return bool(self.settings.anthropic_api_key)
        return False

    def classify_intent(self, *, message: str, recent_messages: list[dict[str, Any]] | None = None) -> LLMIntentPrediction | None:
        if not self.enabled:
            return None
        user_prompt = self._build_classification_prompt(message=message, recent_messages=recent_messages or [])
        try:
            raw = self.circuit_breaker.call(lambda: self._call_intent_model(user_prompt))
        except CircuitBreakerOpenError:
            return None
        except Exception:
            return None

        payload = self._try_parse_json(raw)
        if payload is None:
            return None

        intent = str(payload.get("intent", "")).strip()
        if intent not in self.SUPPORTED_INTENTS:
            return None
        confidence = self._normalize_confidence(payload.get("confidence", 0.0))
        entities = payload.get("entities", {})
        if not isinstance(entities, dict):
            entities = {}
        return LLMIntentPrediction(
            intent=intent,
            confidence=confidence,
            entities=entities,
        )

    def plan_actions(
        self,
        *,
        message: str,
        recent_messages: list[dict[str, Any]] | None = None,
        inferred_intent: str | None = None,
    ) -> LLMActionPlan | None:
        if not self.enabled:
            return None

        user_prompt = self._build_action_plan_prompt(
            message=message,
            recent_messages=recent_messages or [],
            inferred_intent=inferred_intent,
            allowed_actions=sorted(self.SUPPORTED_PLANNER_ACTIONS.keys()),
        )
        try:
            raw = self.circuit_breaker.call(lambda: self._call_action_planner_model(user_prompt))
        except CircuitBreakerOpenError:
            return None
        except Exception:
            return None

        payload = self._try_parse_json(raw)
        if payload is None:
            return None

        confidence = self._normalize_confidence(payload.get("confidence", 0.0))
        needs_clarification = bool(payload.get("needsClarification", False))
        clarification_question = str(payload.get("clarificationQuestion", "")).strip()

        raw_actions = payload.get("actions", [])
        actions: list[LLMPlannedAction] = []
        if isinstance(raw_actions, list):
            for row in raw_actions[: self.MAX_PLAN_ACTIONS]:
                parsed = self._parse_planned_action(row)
                if parsed is not None:
                    actions.append(parsed)

        if needs_clarification:
            if not clarification_question:
                clarification_question = "Could you clarify the exact item details so I can do that safely?"
            return LLMActionPlan(
                actions=[],
                confidence=confidence,
                needs_clarification=True,
                clarification_question=clarification_question,
            )

        if confidence < self.PLAN_CONFIDENCE_FLOOR:
            return None
        if not actions:
            return None

        return LLMActionPlan(
            actions=actions,
            confidence=confidence,
            needs_clarification=False,
            clarification_question="",
        )

    def _parse_planned_action(self, payload: Any) -> LLMPlannedAction | None:
        if not isinstance(payload, dict):
            return None

        name = str(payload.get("name", "")).strip()
        if not name:
            return None
        spec = self.SUPPORTED_PLANNER_ACTIONS.get(name)
        if spec is None:
            return None

        target_agent_raw = str(payload.get("targetAgent", "")).strip()
        target_agent = target_agent_raw or str(spec.get("target", "")).strip() or None
        if target_agent and target_agent not in self.SUPPORTED_TARGET_AGENTS:
            target_agent = str(spec.get("target", "")).strip() or None

        raw_params = payload.get("params", {})
        if not isinstance(raw_params, dict):
            raw_params = {}

        allowed_params = spec.get("allowedParams", set())
        safe_params: dict[str, Any] = {}
        for key, value in raw_params.items():
            normalized_key = str(key).strip()
            if normalized_key not in allowed_params:
                continue
            normalized_value = self._normalize_planner_value(value)
            if normalized_value is None:
                continue
            safe_params[normalized_key] = normalized_value

        return LLMPlannedAction(name=name, target_agent=target_agent, params=safe_params)

    def _normalize_planner_value(self, value: Any) -> Any | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            return value[:300]
        if isinstance(value, list):
            normalized: list[Any] = []
            for item in value[:8]:
                clean = self._normalize_planner_value(item)
                if clean is not None:
                    normalized.append(clean)
            return normalized
        if isinstance(value, dict):
            normalized_dict: dict[str, Any] = {}
            for index, (raw_key, raw_value) in enumerate(value.items()):
                if index >= 12:
                    break
                key = str(raw_key).strip()[:80]
                if not key:
                    continue
                clean = self._normalize_planner_value(raw_value)
                if clean is None:
                    continue
                normalized_dict[key] = clean
            return normalized_dict
        return None

    def _call_intent_model(self, user_prompt: str) -> str:
        provider = self.settings.llm_provider.strip().lower()
        if provider == "openai":
            return self._call_openai(user_prompt)
        if provider == "anthropic":
            return self._call_anthropic(user_prompt)
        raise ValueError(f"Unsupported LLM provider: {provider}")

    def _call_action_planner_model(self, user_prompt: str) -> str:
        provider = self.settings.llm_provider.strip().lower()
        if provider == "openai":
            return self._call_openai_with_system(user_prompt=user_prompt, system_prompt=ACTION_PLANNING_PROMPT)
        if provider == "anthropic":
            return self._call_anthropic_with_system(user_prompt=user_prompt, system_prompt=ACTION_PLANNING_PROMPT)
        raise ValueError(f"Unsupported LLM provider: {provider}")

    def _call_openai(self, user_prompt: str) -> str:
        return self._call_openai_with_system(user_prompt=user_prompt, system_prompt=INTENT_CLASSIFICATION_PROMPT)

    def _call_openai_with_system(self, *, user_prompt: str, system_prompt: str) -> str:
        api_key = self.settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.settings.llm_temperature,
                "max_tokens": self.settings.llm_max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from OpenAI")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("Invalid OpenAI response content")
        return content

    def _call_anthropic(self, user_prompt: str) -> str:
        return self._call_anthropic_with_system(user_prompt=user_prompt, system_prompt=INTENT_CLASSIFICATION_PROMPT)

    def _call_anthropic_with_system(self, *, user_prompt: str, system_prompt: str) -> str:
        api_key = self.settings.anthropic_api_key
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")

        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.llm_model,
                "max_tokens": self.settings.llm_max_tokens,
                "temperature": self.settings.llm_temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content_parts = payload.get("content", [])
        if not content_parts:
            raise ValueError("No content returned from Anthropic")
        first = content_parts[0]
        if not isinstance(first, dict):
            raise ValueError("Invalid Anthropic content structure")
        text = first.get("text")
        if not isinstance(text, str):
            raise ValueError("Invalid Anthropic content text")
        return text

    def _build_classification_prompt(self, *, message: str, recent_messages: list[dict[str, Any]]) -> str:
        recent_snippets = []
        for row in recent_messages[-6:]:
            msg = str(row.get("message", "")).strip()
            intent = str(row.get("intent", "")).strip()
            if msg:
                recent_snippets.append({"message": msg[:200], "intent": intent})

        return json.dumps(
            {
                "message": message.strip()[:2000],
                "recent": recent_snippets,
            },
            ensure_ascii=True,
        )

    def _build_action_plan_prompt(
        self,
        *,
        message: str,
        recent_messages: list[dict[str, Any]],
        inferred_intent: str | None,
        allowed_actions: list[str],
    ) -> str:
        recent_snippets = []
        for row in recent_messages[-6:]:
            msg = str(row.get("message", "")).strip()
            intent = str(row.get("intent", "")).strip()
            agent = str(row.get("agent", "")).strip()
            if msg:
                recent_snippets.append({"message": msg[:200], "intent": intent, "agent": agent})

        return json.dumps(
            {
                "message": message.strip()[:2000],
                "inferredIntent": str(inferred_intent or "").strip(),
                "allowedActions": allowed_actions,
                "recent": recent_snippets,
            },
            ensure_ascii=True,
        )

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            number = float(value)
        except Exception:
            number = 0.0
        return max(0.0, min(1.0, number))

    @staticmethod
    def _try_parse_json(raw: str) -> dict[str, Any] | None:
        text = raw.strip()
        if not text:
            return None

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
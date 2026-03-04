from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.infrastructure.prompts import ACTION_PLANNING_PROMPT, INTENT_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)


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
            "allowedParams": {"query", "category", "brand", "minPrice", "maxPrice", "color", "size"},
        },
        "add_item": {
            "target": "cart",
            "allowedParams": {"query", "productId", "variantId", "quantity", "brand", "color", "size", "minPrice", "maxPrice"},
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
        return bool(self.settings.openrouter_api_key)

    @property
    def intent_classification_enabled(self) -> bool:
        decision_policy = str(self.settings.llm_decision_policy).strip().lower()
        planner_blocks_classifier = self.settings.llm_planner_enabled and decision_policy != "classifier_first"
        return (
            self.enabled
            and self.settings.llm_intent_classifier_enabled
            and not planner_blocks_classifier
        )

    @property
    def planner_enabled(self) -> bool:
        return self.enabled and self.settings.llm_planner_enabled

    def classify_intent(self, *, message: str, recent_messages: list[dict[str, Any]] | None = None) -> LLMIntentPrediction | None:
        if not self.intent_classification_enabled:
            return None
        user_prompt = self._build_classification_prompt(message=message, recent_messages=recent_messages or [])
        try:
            raw = self.circuit_breaker.call(lambda: self._call_llm(user_prompt=user_prompt, system_prompt=INTENT_CLASSIFICATION_PROMPT))
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
        if not self.planner_enabled:
            return None

        user_prompt = self._build_action_plan_prompt(
            message=message,
            recent_messages=recent_messages or [],
            inferred_intent=inferred_intent,
            allowed_actions=sorted(self.SUPPORTED_PLANNER_ACTIONS.keys()),
        )
        try:
            raw = self.circuit_breaker.call(lambda: self._call_llm(user_prompt=user_prompt, system_prompt=ACTION_PLANNING_PROMPT))
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
            for row in raw_actions[: self._planner_max_actions()]:
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

        if confidence < self._planner_confidence_floor():
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

    def _call_llm(self, *, user_prompt: str, system_prompt: str) -> str:
        """Synchronous wrapper for LLM calls. Handles both sync and async contexts safely."""
        try:
            # Check if we're already in an async context
            loop = asyncio.get_running_loop()
            # If we get here, we're in an async context - this shouldn't happen for sync method
            # but we handle it gracefully by raising an error
            raise RuntimeError("Synchronous _call_llm called from async context. Use async methods instead.")
        except RuntimeError:
            # No running event loop - safe to create one
            return asyncio.run(self._call_llm_async(user_prompt=user_prompt, system_prompt=system_prompt))

    async def _call_llm_async(self, *, user_prompt: str, system_prompt: str) -> str:
        """Async method to call the LLM with retry logic for rate limiting."""
        api_key = self.settings.openrouter_api_key
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")

        max_retries = 5
        base_delay = 5.0

        for attempt in range(max_retries):
            try:
                response = httpx.post(
                    f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:5173",
                        "X-Title": "Omnichannel Agentic Commerce",
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
                status_code = int(getattr(response, "status_code", 200))
                if status_code == 429:
                    headers = getattr(response, "headers", {}) or {}
                    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
                    delay = self._retry_delay_seconds(attempt=attempt, base_delay=base_delay, retry_after=retry_after)
                    
                    if attempt < max_retries - 1:
                        logger.info(f"[LLM] Rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise Exception("Rate limited after all retries")
                
                response.raise_for_status()
                payload = response.json()
                choices = payload.get("choices", [])
                if not choices:
                    raise ValueError("No choices returned from OpenRouter")
                content = choices[0].get("message", {}).get("content")
                if not isinstance(content, str):
                    raise ValueError("Invalid OpenRouter response content")
                return content
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after = e.response.headers.get("retry-after")
                    delay = self._retry_delay_seconds(attempt=attempt, base_delay=base_delay, retry_after=retry_after)
                    
                    if attempt < max_retries - 1:
                        logger.info(f"[LLM] HTTPStatusError rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                raise

    def generate_response(self, *, user_prompt: str, system_prompt: str) -> str | None:
        """Synchronous method to generate a response from the LLM."""
        try:
            response = self._call_llm(user_prompt=user_prompt, system_prompt=system_prompt)
            if response:
                # The LLM returns JSON, try to parse it and extract the message
                try:
                    data = json.loads(response)
                    # Look for common message fields
                    if isinstance(data, dict):
                        message = data.get("message") or data.get("answer") or data.get("response")
                        if message:
                            return message
                    # If no standard field found, return the JSON as string
                    return response
                except json.JSONDecodeError:
                    return response
            return response
        except Exception as e:
            logger.error(f"LLM generate_response failed: {e}")
            return None

    async def stream_response(self, *, user_prompt: str, system_prompt: str):
        api_key = self.settings.openrouter_api_key
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")

        max_retries = 5
        base_delay = 5.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    async with client.stream(
                        "POST",
                        f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "http://localhost:5173",
                            "X-Title": "Omnichannel Agentic Commerce",
                        },
                        json={
                            "model": self.settings.llm_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": self.settings.llm_temperature,
                            "max_tokens": self.settings.llm_max_tokens,
                            "stream": True,
                        },
                        timeout=self.settings.llm_timeout_seconds,
                    ) as response:
                        if response.status_code == 429:
                            retry_after = response.headers.get("retry-after")
                            delay = self._retry_delay_seconds(attempt=attempt, base_delay=base_delay, retry_after=retry_after)
                            
                            if attempt < max_retries - 1:
                                logger.info(f"[LLM Stream] Rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                                await asyncio.sleep(delay)
                                continue
                            else:
                                raise Exception("Rate limited after all retries")

                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                    delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if delta:
                                        yield delta
                                except json.JSONDecodeError:
                                    continue
                break  # Success, exit retry loop
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    delay = self._retry_delay_seconds(attempt=attempt, base_delay=base_delay, retry_after=e.response.headers.get("retry-after"))
                    logger.info(f"[LLM Stream] HTTPStatusError rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue
                raise

    @staticmethod
    def _retry_delay_seconds(*, attempt: int, base_delay: float, retry_after: str | None) -> float:
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return float(base_delay * (2 ** attempt))

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

    def _planner_max_actions(self) -> int:
        try:
            value = int(self.settings.llm_planner_max_actions)
        except Exception:
            value = 5
        return max(1, min(10, value))

    def _planner_confidence_floor(self) -> float:
        return max(0.0, min(1.0, float(self.settings.llm_planner_min_confidence)))

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

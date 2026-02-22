from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.infrastructure.prompts import INTENT_CLASSIFICATION_PROMPT


@dataclass
class LLMIntentPrediction:
    intent: str
    confidence: float
    entities: dict[str, Any]


class LLMClient:
    SUPPORTED_INTENTS = {
        "product_search",
        "search_and_add_to_cart",
        "add_to_cart",
        "apply_discount",
        "update_cart",
        "remove_from_cart",
        "view_cart",
        "checkout",
        "order_status",
        "change_order_address",
        "cancel_order",
        "request_refund",
        "multi_status",
        "general_question",
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

    def _call_intent_model(self, user_prompt: str) -> str:
        provider = self.settings.llm_provider.strip().lower()
        if provider == "openai":
            return self._call_openai(user_prompt)
        if provider == "anthropic":
            return self._call_anthropic(user_prompt)
        raise ValueError(f"Unsupported LLM provider: {provider}")

    def _call_openai(self, user_prompt: str) -> str:
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
                    {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
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
                "system": INTENT_CLASSIFICATION_PROMPT,
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

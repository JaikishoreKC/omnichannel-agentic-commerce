from __future__ import annotations

import re
from typing import Any

from app.infrastructure.llm_client import LLMClient
from app.orchestrator.types import IntentResult


class IntentClassifier:
    """Lightweight rule-first classifier for commerce intents."""

    _DEFAULT_INTENT_CONFIDENCE_FLOORS: dict[str, float] = {
        "general_question": 0.6,
        "view_cart": 0.65,
        "product_search": 0.72,
        "search_and_add_to_cart": 0.78,
        "support_escalation": 0.8,
        "multi_status": 0.82,
        "change_order_address": 0.82,
        "cancel_order": 0.85,
        "request_refund": 0.85,
        "apply_discount": 0.85,
        "clear_cart": 0.88,
    }

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def classify(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        *,
        allow_llm: bool = True,
    ) -> IntentResult:
        rule_intent = self._classify_rules(message=message, context=context)
        if not allow_llm:
            return rule_intent
        llm_choice = self._classify_with_llm(message=message, context=context)
        if llm_choice is None:
            return rule_intent
        floor = max(self._intent_confidence_floor(llm_choice.name), rule_intent.confidence)
        if llm_choice.confidence >= floor:
            return llm_choice
        return rule_intent

    def _intent_confidence_floor(self, intent_name: str) -> float:
        base_floor = self._DEFAULT_INTENT_CONFIDENCE_FLOORS.get(intent_name, 0.7)
        overrides = self._intent_threshold_overrides()
        override = overrides.get(intent_name)
        if override is not None:
            base_floor = override
        return max(0.0, min(1.0, float(base_floor)))

    def _intent_threshold_overrides(self) -> dict[str, float]:
        if self.llm_client is None:
            return {}
        settings = getattr(self.llm_client, "settings", None)
        if settings is None:
            return {}
        parsed = getattr(settings, "intent_confidence_thresholds", None)
        if isinstance(parsed, dict):
            normalized: dict[str, float] = {}
            for raw_key, raw_value in parsed.items():
                key = str(raw_key).strip()
                if not key:
                    continue
                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    continue
                normalized[key] = max(0.0, min(1.0, value))
            return normalized
        return {}

    def _classify_with_llm(self, *, message: str, context: dict[str, Any] | None) -> IntentResult | None:
        if self.llm_client is None:
            return None
        recent = []
        if context:
            raw_recent = context.get("recent", [])
            if isinstance(raw_recent, list):
                recent = [item for item in raw_recent if isinstance(item, dict)]
        prediction = self.llm_client.classify_intent(message=message, recent_messages=recent)
        if prediction is None:
            return None
        return IntentResult(
            name=prediction.intent,
            confidence=prediction.confidence,
            entities=prediction.entities,
        )

    def _classify_rules(self, *, message: str, context: dict[str, Any] | None = None) -> IntentResult:
        text = message.strip().lower()
        phrase_text = re.sub(r"[_\s]+", " ", text).strip()

        if not text:
            return IntentResult(name="general_question", confidence=0.2, entities={})

        if ("cart" in text or "my cart" in text) and self._contains_order_status_phrase(text):
            entities: dict[str, Any] = {}
            entities.update(self._extract_order_id(text))
            return IntentResult(name="multi_status", confidence=0.9, entities=entities)

        variant_confirmation = self._classify_variant_confirmation_intent(
            text=text,
            message=message,
            context=context,
        )
        if variant_confirmation is not None:
            return variant_confirmation

        for classifier in (
            self._classify_memory_intent,
            self._classify_order_intent,
            self._classify_support_intent,
            self._classify_search_and_add_intent,
            self._classify_cart_intent,
        ):
            result = classifier(text=text, message=message, phrase_text=phrase_text)
            if result is not None:
                return result

        product = self._classify_product_intent(
            text=text,
            message=message,
            phrase_text=phrase_text,
            context=context,
        )
        if product is not None:
            return product

        return IntentResult(name="general_question", confidence=0.6, entities={"query": message.strip()})

    def _classify_variant_confirmation_intent(
        self,
        *,
        text: str,
        message: str,
        context: dict[str, Any] | None,
    ) -> IntentResult | None:
        phrases = (
            "choose default",
            "pick default",
            "default option",
            "default one",
            "choose first",
            "pick first",
            "first one",
            "the first one",
            "add that",
            "add this",
            "choose that",
            "pick that",
            "go with that",
        )
        if not any(phrase in text for phrase in phrases):
            return None
        recent_option = self._latest_clarification_option(context)
        recent_cart_item = self._latest_cart_item_option(context)
        if not recent_option and not recent_cart_item and not self._has_recent_selection_context(context):
            return None

        entities: dict[str, Any] = {"quantity": 1}
        entities.update(self._extract_quantity(text))

        if recent_option:
            entities.update(recent_option)
        elif recent_cart_item:
            entities.update(recent_cart_item)

        return IntentResult(name="add_to_cart", confidence=0.91, entities=entities)

    def _classify_memory_intent(self, *, text: str, message: str, phrase_text: str) -> IntentResult | None:
        _ = phrase_text
        if self._is_show_memory_request(text):
            return IntentResult(name="show_memory", confidence=0.93, entities={})
        if self._is_clear_memory_request(text):
            return IntentResult(name="clear_memory", confidence=0.92, entities={})
        forget = self._extract_forget_preference(message)
        if forget:
            return IntentResult(name="forget_preference", confidence=0.9, entities=forget)
        updates = self._extract_preference_updates(message)
        if updates and self._is_preference_statement(text):
            return IntentResult(name="save_preference", confidence=0.88, entities={"updates": updates})
        return None

    def _classify_order_intent(self, *, text: str, message: str, phrase_text: str) -> IntentResult | None:
        _ = phrase_text
        entities: dict[str, Any] = {}
        if "order" in text and "address" in text and any(token in text for token in ("change", "update", "delivery")):
            entities.update(self._extract_order_id(text))
            entities.update(self._extract_shipping_address(message))
            return IntentResult(name="change_order_address", confidence=0.88, entities=entities)
        if "cancel" in text and "order" in text:
            entities.update(self._extract_order_id(text))
            return IntentResult(name="cancel_order", confidence=0.91, entities=entities)
        if "refund" in text and "order" in text:
            entities.update(self._extract_order_id(text))
            return IntentResult(name="request_refund", confidence=0.9, entities=entities)
        if self._contains_order_status_phrase(text):
            entities.update(self._extract_order_id(text))
            return IntentResult(name="order_status", confidence=0.9, entities=entities)
        if ("checkout" in text or "place order" in text or "buy now" in text) and not self._is_discount_request(
            text=text,
            message=message,
        ):
            return IntentResult(name="checkout", confidence=0.95, entities={})
        return None

    def _classify_support_intent(self, *, text: str, message: str, phrase_text: str) -> IntentResult | None:
        _ = phrase_text
        entities: dict[str, Any] = {}
        if self._is_support_status_request(text):
            entities.update(self._extract_ticket_id(text))
            return IntentResult(name="support_status", confidence=0.9, entities=entities)
        if self._is_support_close_request(text):
            entities.update(self._extract_ticket_id(text))
            return IntentResult(name="support_close", confidence=0.9, entities=entities)
        if self._is_support_escalation_request(text):
            entities.update(self._extract_ticket_id(text))
            entities["query"] = message.strip()
            return IntentResult(name="support_escalation", confidence=0.88, entities=entities)
        return None

    def _classify_search_and_add_intent(self, *, text: str, message: str, phrase_text: str) -> IntentResult | None:
        _ = phrase_text
        if not (("add" in text and "cart" in text) and any(
            token in text
            for token in (
                "find",
                "search",
                "show me",
                "recommend",
                "looking for",
                "under",
                "below",
                "over",
                "above",
            )
        )):
            return None

        entities: dict[str, Any] = {}
        entities.update(self._extract_quantity(text))
        entities.update(self._extract_product_or_variant_id(text))
        entities.update(self._extract_price_range(text))
        entities.update(self._extract_size(message))
        entities.update(self._extract_color(text))
        entities.update(self._extract_brand(message))
        entities["query"] = self._extract_search_query_for_combo(message)
        return IntentResult(name="search_and_add_to_cart", confidence=0.93, entities=entities)

    def _classify_cart_intent(self, *, text: str, message: str, phrase_text: str) -> IntentResult | None:
        entities: dict[str, Any] = {}
        if self._is_clear_cart_request(text):
            return IntentResult(name="clear_cart", confidence=0.94, entities={})
        if self._is_adjust_cart_quantity_request(text):
            entities.update(self._extract_product_or_item_id(text))
            entities.update(self._extract_delta(text))
            query = self._extract_cart_item_query(message)
            if query:
                entities["query"] = query
            return IntentResult(name="adjust_cart_quantity", confidence=0.89, entities=entities)
        multi_items = self._extract_multi_add_items(message)
        if len(multi_items) >= 2:
            return IntentResult(name="add_multiple_to_cart", confidence=0.9, entities={"items": multi_items})
        if self._is_discount_request(text=text, message=message):
            entities.update(self._extract_discount_code(message))
            return IntentResult(name="apply_discount", confidence=0.9, entities=entities)

        if "remove" in text and "cart" in text:
            entities.update(self._extract_quantity(text))
            entities.update(self._extract_product_or_item_id(text))
            query = self._extract_cart_item_query(message)
            if query:
                entities["query"] = query
            return IntentResult(name="remove_from_cart", confidence=0.88, entities=entities)
        if any(phrase in text for phrase in ["update cart", "change quantity", "set quantity"]):
            entities.update(self._extract_quantity(text))
            entities.update(self._extract_product_or_item_id(text))
            query = self._extract_cart_item_query(message)
            if query:
                entities["query"] = query
            return IntentResult(name="update_cart", confidence=0.86, entities=entities)
        if "add" in text and "cart" in text:
            entities.update(self._extract_quantity(text))
            entities.update(self._extract_product_or_variant_id(text))
            entities.update(self._extract_size(message))
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            query = self._extract_add_query(message)
            if query:
                entities["query"] = query
            return IntentResult(name="add_to_cart", confidence=0.92, entities=entities)
        if self._is_view_cart_request(phrase_text):
            return IntentResult(name="view_cart", confidence=0.9, entities={})
        return None

    def _is_discount_request(self, *, text: str, message: str) -> bool:
        discount_keywords = (
            "discount",
            "coupon",
            "promo",
            "promo code",
            "voucher",
            "offer code",
            "gift code",
        )
        action_keywords = ("apply", "use", "redeem", "enter", "activate")

        has_discount_keyword = any(token in text for token in discount_keywords)
        has_action_keyword = any(token in text for token in action_keywords)
        has_code_word = "code" in text
        has_checkout_context = any(token in text for token in ("cart", "checkout", "order total", "total"))
        has_code_like_token = bool(re.search(r"\b[A-Za-z]{2,}[A-Za-z0-9_-]*\d+[A-Za-z0-9_-]*\b", message))

        if has_discount_keyword and (has_action_keyword or has_code_word or has_code_like_token):
            return True
        if has_action_keyword and has_checkout_context and (has_code_word or has_code_like_token):
            return True
        return False

    def _classify_product_intent(
        self,
        *,
        text: str,
        message: str,
        phrase_text: str,
        context: dict[str, Any] | None,
    ) -> IntentResult | None:
        entities: dict[str, Any] = {}
        if any(token in text for token in ["find", "search", "show me", "recommend", "looking for"]):
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_size(message))
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            entities["query"] = message.strip()
            return IntentResult(name="product_search", confidence=0.84, entities=entities)
        if self._is_price_refinement_request(text=phrase_text, context=context):
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_size(message))
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            entities["query"] = message.strip()
            return IntentResult(name="product_search", confidence=0.8, entities=entities)
        if self._looks_like_product_query(phrase_text):
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_size(message))
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            entities["query"] = message.strip()
            return IntentResult(name="product_search", confidence=0.78, entities=entities)
        return None

    def _extract_order_id(self, text: str) -> dict[str, Any]:
        match = re.search(r"\b(order[_\-][a-z0-9]+|ord[_\-][a-z0-9]+)\b", text)
        return {"orderId": match.group(1)} if match else {}

    def _extract_ticket_id(self, text: str) -> dict[str, Any]:
        match = re.search(r"\b(ticket[_\-][a-z0-9]+)\b", text)
        if not match:
            return {}
        return {"ticketId": match.group(1).replace("-", "_")}

    def _extract_quantity(self, text: str) -> dict[str, Any]:
        match = re.search(r"\b(\d+)\b", text)
        if not match:
            return {}
        quantity = max(1, min(50, int(match.group(1))))
        return {"quantity": quantity}

    def _extract_color(self, text: str) -> dict[str, Any]:
        colors = (
            "black", "blue", "white", "green", "red", "gray", "grey", "charcoal", "navy",
            "yellow", "purple", "orange", "pink", "brown", "tan", "beige", "gold", "silver",
            "maroon", "teal", "olive", "magenta", "cyan"
        )
        for color in colors:
            if color in text:
                return {"color": color}
        return {}

    def _extract_size(self, message: str) -> dict[str, Any]:
        match = re.search(r"\bsize\s*([a-z0-9\-]+)\b", message, flags=re.IGNORECASE)
        if not match:
            return {}
        return {"size": match.group(1).strip().upper()}

    def _extract_price_range(self, text: str) -> dict[str, Any]:
        below = re.search(r"(under|below)\s*\$?(\d+)", text)
        above = re.search(r"(over|above)\s*\$?(\d+)", text)
        entities: dict[str, Any] = {}
        if below:
            entities["maxPrice"] = float(below.group(2))
        if above:
            entities["minPrice"] = float(above.group(2))
        return entities

    def _extract_brand(self, message: str) -> dict[str, Any]:
        match = re.search(
            r"(?:brand|from|by)\s*(?:is|=|:)?\s*([a-zA-Z0-9&\-\s]{2,80})",
            message,
            flags=re.IGNORECASE,
        )
        if match:
            raw = match.group(1).strip(" .,;")
            if raw:
                # Basic filtering to avoid common words being caught as brands
                if raw.lower() not in ("me", "my", "the", "a", "an", "this", "that", "these", "those"):
                    return {"brand": raw.lower()}
        
        known = ("strideforge", "peakroute", "aerothread", "carryworks", "urbanbound", "trailtech", "luxthread", "vanguards")
        lowered = message.lower()
        for token in known:
            if token in lowered:
                return {"brand": token}
        return {}

    def _extract_product_or_variant_id(self, text: str) -> dict[str, Any]:
        product_match = re.search(r"\b((?:ai_)?prod(?:[_\-][a-z0-9]+)+)\b", text)
        variant_match = re.search(r"\b((?:ai_)?var(?:[_\-][a-z0-9]+)+)\b", text)
        entities: dict[str, Any] = {}
        if product_match:
            entities["productId"] = product_match.group(1).replace("-", "_")
        if variant_match:
            entities["variantId"] = variant_match.group(1).replace("-", "_")
        return entities

    def _extract_product_or_item_id(self, text: str) -> dict[str, Any]:
        item_match = re.search(r"\b(item(?:[_\-][a-z0-9]+)+)\b", text)
        if item_match:
            return {"itemId": item_match.group(1).replace("-", "_")}
        return self._extract_product_or_variant_id(text)

    def _extract_delta(self, text: str) -> dict[str, Any]:
        if "set quantity" in text:
            return {}
        amount_match = re.search(r"\b(\d+)\b", text)
        amount = max(1, int(amount_match.group(1))) if amount_match else 1
        if any(token in text for token in ("decrease", "reduce", "minus", "less")):
            return {"delta": -amount}
        if any(token in text for token in ("increase", "plus", "more", "another")):
            return {"delta": amount}
        return {}

    def _contains_order_status_phrase(self, text: str) -> bool:
        if "order" not in text:
            return False
        phrases = (
            "order status",
            "where is my order",
            "track order",
            "hasn't arrived",
            "hasnt arrived",
            "not arrived",
            "order is late",
            "order late",
            "delayed order",
            "order delayed",
        )
        return any(phrase in text for phrase in phrases)

    def _extract_discount_code(self, message: str) -> dict[str, Any]:
        patterns = (
            r"(?:code|coupon|promo(?:\s*code)?|discount|voucher|offer\s*code)\s*(?:is|=|:|-)?\s*([a-zA-Z0-9_-]{4,20})",
            r"(?:apply|use|redeem|enter|activate)\s*(?:code\s*)?([a-zA-Z0-9_-]{4,20})\s*(?:coupon|promo|discount|voucher)?",
        )
        for pattern in patterns:
            explicit = re.search(pattern, message, flags=re.IGNORECASE)
            if explicit:
                candidate = explicit.group(1).upper()
                if self._is_likely_discount_code(candidate):
                    return {"code": candidate}

        candidates = re.findall(r"\b([A-Za-z0-9]{4,20})\b", message)
        stop_words = {
            "APPLY",
            "DISCOUNT",
            "COUPON",
            "PROMO",
            "CODE",
            "PLEASE",
            "THIS",
            "THAT",
            "USE",
            "REDEEM",
            "ENTER",
            "ACTIVATE",
            "NOW",
            "CHECKOUT",
            "CART",
            "ORDER",
            "TOTAL",
            "OFFER",
            "VOUCHER",
            "GIFT",
        }
        for candidate in candidates:
            token = candidate.upper()
            if token in stop_words:
                continue
            if self._is_likely_discount_code(token):
                return {"code": token}
        return {}

    @staticmethod
    def _is_likely_discount_code(token: str) -> bool:
        # Keep this conservative: prefer codes with at least one digit/hyphen/underscore.
        value = str(token or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]{4,20}", value):
            return False
        return any(char.isdigit() for char in value) or ("-" in value) or ("_" in value)

    def _extract_search_query_for_combo(self, message: str) -> str:
        cleaned = re.sub(
            r"\b(and\s+)?(add|put)\b.*\bcart\b",
            " ",
            message,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _extract_shipping_address(self, message: str) -> dict[str, Any]:
        patterns = {
            "name": r"name",
            "line1": r"line1|address|street",
            "line2": r"line2|apt|suite",
            "city": r"city",
            "state": r"state",
            "postalCode": r"postal\s*code|postalcode|zip",
            "country": r"country",
        }
        fields: dict[str, str] = {}
        for field, pattern in patterns.items():
            match = re.search(
                rf"(?:{pattern})\s*[:=]\s*([^,;]+)",
                message,
                flags=re.IGNORECASE,
            )
            if match:
                fields[field] = match.group(1).strip()

        required = {"line1", "city", "state", "postalCode", "country"}
        if not required.issubset(fields.keys()):
            return {}
        shipping = {
            "name": fields.get("name", "Customer"),
            "line1": fields["line1"],
            "city": fields["city"],
            "state": fields["state"],
            "postalCode": fields["postalCode"],
            "country": fields["country"],
        }
        if "line2" in fields:
            shipping["line2"] = fields["line2"]
        return {"shippingAddress": shipping}

    def _extract_add_query(self, message: str) -> str:
        cleaned = re.sub(r"\badd\b", " ", message, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bto\b\s+\b(my\s+)?cart\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(prod[_\-]?\d+|var[_\-]?\d+|item[_\-]?\d+)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d+\b", " ", cleaned)
        cleaned = re.sub(
            r"\b(please|the|a|an|item|items|quantity|qty|of|for|me|my|cart|with|color)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"[,:;]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned.lower() in {"", "to", "cart"}:
            return ""
        return cleaned

    def _extract_cart_item_query(self, message: str) -> str:
        cleaned = re.sub(
            r"\b(remove|delete|drop|update|change|set|increase|decrease|reduce|quantity|qty|from|in|cart|my|the)\b",
            " ",
            message,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\b(prod[_\-]?\d+|var[_\-]?\d+|item[_\-]?\d+)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d+\b", " ", cleaned)
        cleaned = re.sub(r"[,:;]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _is_clear_cart_request(self, text: str) -> bool:
        phrases = (
            "clear cart",
            "empty cart",
            "remove all from cart",
            "delete all from cart",
            "clear my cart",
            "empty my cart",
        )
        return any(phrase in text for phrase in phrases)

    def _is_adjust_cart_quantity_request(self, text: str) -> bool:
        if "set quantity" in text:
            return False
        if "cart" not in text and "quantity" not in text and "qty" not in text:
            return False
        return any(
            token in text
            for token in ("increase", "decrease", "reduce", "minus", "plus", "one more", "one less", "another")
        )

    def _is_support_escalation_request(self, text: str) -> bool:
        phrases = (
            "human agent",
            "support agent",
            "talk to support",
            "talk to a person",
            "connect me to support",
            "open a ticket",
            "escalate",
            "need help with issue",
        )
        if any(phrase in text for phrase in phrases):
            return True
        return "help" in text and "order" in text and "agent" in text

    def _is_support_status_request(self, text: str) -> bool:
        phrases = (
            "ticket status",
            "support status",
            "status of my ticket",
            "my support ticket",
            "any update on ticket",
        )
        return any(phrase in text for phrase in phrases)

    def _is_support_close_request(self, text: str) -> bool:
        phrases = (
            "close ticket",
            "resolve ticket",
            "mark ticket resolved",
        )
        return any(phrase in text for phrase in phrases)

    def _extract_multi_add_items(self, message: str) -> list[dict[str, Any]]:
        lower = message.lower()
        if "add" not in lower or "cart" not in lower:
            return []
        body = re.sub(r"^.*?\badd\b", "", lower, flags=re.IGNORECASE).strip()
        body = re.sub(r"\bto\b\s+\b(my\s+)?cart\b.*$", "", body, flags=re.IGNORECASE).strip()
        body = re.sub(r"\s+", " ", body).strip(" .,;")
        if not body:
            return []
        parts = re.split(r"\s*(?:,|\band\b)\s*", body)
        items: list[dict[str, Any]] = []
        for part in parts:
            chunk = part.strip(" .,;")
            if not chunk:
                continue
            qty_match = re.search(r"\b(\d+)\b", chunk)
            quantity = max(1, min(50, int(qty_match.group(1)))) if qty_match else 1
            color = self._extract_color(chunk).get("color")
            query = re.sub(r"\b\d+\b", " ", chunk)
            query = re.sub(r"\b(of|a|an|the|please|to|my|cart)\b", " ", query)
            query = re.sub(r"\s+", " ", query).strip()
            if not query:
                continue
            payload: dict[str, Any] = {"query": query, "quantity": quantity}
            if color:
                payload["color"] = color
            items.append(payload)
        return items

    def _is_show_memory_request(self, text: str) -> bool:
        phrases = (
            "what do you remember",
            "show my preferences",
            "show memory",
            "what are my preferences",
            "what do you know about me",
            "remembered about me",
        )
        return any(phrase in text for phrase in phrases)

    def _is_clear_memory_request(self, text: str) -> bool:
        phrases = (
            "clear memory",
            "clear my memory",
            "forget everything",
            "reset my preferences",
            "clear preferences",
        )
        return any(phrase in text for phrase in phrases)

    def _is_preference_statement(self, text: str) -> bool:
        if any(token in text for token in ("remember", "note that", "save preference")):
            return True
        if any(token in text for token in ("my size is", "i wear size", "budget", "price range")):
            return True
        if "i prefer" in text or "i like" in text:
            blocking = ("show me", "find", "search", "add to cart", "checkout", "order status")
            return not any(token in text for token in blocking)
        return False

    def _extract_preference_updates(self, message: str) -> dict[str, Any]:
        text = message.strip().lower()
        updates: dict[str, Any] = {}

        size_match = re.search(r"\b(?:size\s*(?:is|=)?|wear size)\s*(xxs|xs|s|m|l|xl|xxl|\d{1,2})\b", text)
        if size_match:
            updates["size"] = size_match.group(1).upper()

        max_match = re.search(r"(?:under|below|max(?:imum)?)\s*\$?(\d+)", text)
        min_match = re.search(r"(?:over|above|min(?:imum)?)\s*\$?(\d+)", text)
        if max_match or min_match:
            price_range: dict[str, float] = {}
            if min_match:
                price_range["min"] = float(min_match.group(1))
            if max_match:
                price_range["max"] = float(max_match.group(1))
            updates["priceRange"] = price_range

        categories = []
        for category in ("shoes", "clothing", "accessories"):
            if category in text:
                categories.append(category)
        if "hoodie" in text or "jogger" in text:
            categories.append("clothing")
        if "runner" in text or "sneaker" in text:
            categories.append("shoes")
        if categories:
            updates["categories"] = sorted(set(categories))

        styles = []
        for style in ("denim", "casual", "formal", "sport", "athleisure", "vintage", "streetwear", "minimal"):
            if style in text:
                styles.append(style)
        if styles:
            updates["stylePreferences"] = sorted(set(styles))

        colors = []
        for color in ("black", "blue", "white", "green", "red", "gray", "charcoal", "navy"):
            if color in text:
                colors.append(color)
        if colors:
            updates["colorPreferences"] = sorted(set(colors))

        brand_match = re.search(r"(?:brand|brands?)\s*(?:is|are|=|:)?\s*([a-z0-9,\s&-]{2,120})", text)
        if brand_match:
            chunks = re.split(r"(?:,|and)", brand_match.group(1))
            brands = [token.strip() for token in chunks if token.strip()]
            if brands:
                updates["brandPreferences"] = brands

        if ("i prefer " in text or "i like " in text) and not any(
            key in updates for key in ("categories", "stylePreferences", "colorPreferences", "brandPreferences")
        ):
            suffix = re.split(r"i prefer |i like ", text, maxsplit=1)
            if len(suffix) == 2:
                candidate = suffix[1].strip(" .,!?")
                if candidate:
                    updates["stylePreferences"] = [candidate.split()[0]]

        return updates

    def _extract_forget_preference(self, message: str) -> dict[str, Any]:
        text = message.strip().lower()
        if "forget" not in text and "remove preference" not in text:
            return {}
        if "everything" in text or "all preferences" in text:
            return {"key": "all"}

        if "size" in text:
            return {"key": "size"}
        if "price" in text or "budget" in text:
            return {"key": "priceRange"}
        if "category" in text or "categories" in text:
            return {"key": "categories"}
        if "style" in text:
            return {"key": "stylePreferences"}
        if "color" in text:
            return {"key": "colorPreferences"}
        if "brand" in text:
            return {"key": "brandPreferences"}

        for token in ("shoes", "clothing", "accessories", "denim", "black", "blue", "green", "red", "gray"):
            if token in text:
                return {"value": token}
        return {}

    def _is_view_cart_request(self, text: str) -> bool:
        if not text:
            return False
        if text in {'cart', 'my cart', 'view cart', 'show cart', 'show me cart', 'view my cart'}:
            return True
        if re.search(r'\b(view|show|open|see|display)\s+(my\s+)?cart\b', text):
            return True
        if ('what' in text or 'whats' in text or "what's" in text) and 'cart' in text:
            return True
        return False

    def _is_price_refinement_request(self, *, text: str, context: dict[str, Any] | None) -> bool:
        if not self._extract_price_range(text):
            return False
        if any(token in text for token in ('cart', 'checkout', 'order', 'refund', 'ticket', 'support')):
            return False
        if context is None:
            return True
        recent = context.get('recent', [])
        if not isinstance(recent, list):
            return True
        for row in reversed(recent):
            if not isinstance(row, dict):
                continue
            intent = str(row.get('intent', '')).strip()
            agent = str(row.get('agent', '')).strip()
            if intent in {'product_search', 'search_and_add_to_cart'} or agent == 'product':
                return True
        return False

    def _has_recent_selection_context(self, context: dict[str, Any] | None) -> bool:
        if context is None:
            return False
        recent = context.get("recent", [])
        if not isinstance(recent, list):
            return False
        for row in reversed(recent):
            if not isinstance(row, dict):
                continue
            response = row.get("response", {})
            if not isinstance(response, dict):
                continue
            data = response.get("data", {})
            if isinstance(data, dict):
                candidate_maps: list[dict[str, Any]] = [data]
                for value in data.values():
                    if isinstance(value, dict):
                        candidate_maps.append(value)
                for candidate in candidate_maps:
                    if candidate.get("code") == "CLARIFICATION_REQUIRED" and isinstance(candidate.get("options"), list):
                        return True
                    products = candidate.get("products")
                    if isinstance(products, list) and products:
                        return True
            intent = str(row.get("intent", "")).strip().lower()
            agent = str(row.get("agent", "")).strip().lower()
            if intent in {"product_search", "search_and_add_to_cart"} or agent in {"product", "orchestrator"}:
                return True
        return False

    def _latest_clarification_option(self, context: dict[str, Any] | None) -> dict[str, Any]:
        if context is None:
            return {}
        recent = context.get("recent", [])
        if not isinstance(recent, list):
            return {}
        for row in reversed(recent):
            if not isinstance(row, dict):
                continue
            response = row.get("response", {})
            if not isinstance(response, dict):
                continue
            data = response.get("data", {})
            if not isinstance(data, dict):
                continue

            candidate_maps: list[dict[str, Any]] = [data]
            for value in data.values():
                if isinstance(value, dict):
                    candidate_maps.append(value)

            for candidate in candidate_maps:
                if candidate.get("code") == "CLARIFICATION_REQUIRED":
                    options = candidate.get("options", [])
                    if isinstance(options, list) and options:
                        first = options[0]
                        if isinstance(first, dict):
                            product_id = str(first.get("productId", "")).strip()
                            variant_id = str(first.get("variantId", "")).strip()
                            payload: dict[str, Any] = {}
                            if product_id:
                                payload["productId"] = product_id
                            if variant_id:
                                payload["variantId"] = variant_id
                            if payload:
                                return payload

                products = candidate.get("products")
                if not isinstance(products, list) or not products:
                    continue
                first_product = products[0]
                if not isinstance(first_product, dict):
                    continue
                variants = first_product.get("variants")
                if not isinstance(variants, list) or not variants:
                    continue
                selected_variant: dict[str, Any] | None = None
                for variant in variants:
                    if isinstance(variant, dict) and bool(variant.get("inStock", False)):
                        selected_variant = variant
                        break
                if selected_variant is None and isinstance(variants[0], dict):
                    selected_variant = variants[0]
                if selected_variant is None:
                    continue
                product_id = str(first_product.get("id", "")).strip()
                variant_id = str(selected_variant.get("id", "")).strip()
                payload: dict[str, Any] = {}
                if product_id:
                    payload["productId"] = product_id
                if variant_id:
                    payload["variantId"] = variant_id
                if payload:
                    return payload
        return {}

    def _latest_cart_item_option(self, context: dict[str, Any] | None) -> dict[str, Any]:
        if context is None:
            return {}
        recent = context.get("recent", [])
        if not isinstance(recent, list):
            return {}
        for row in reversed(recent):
            if not isinstance(row, dict):
                continue
            response = row.get("response", {})
            if not isinstance(response, dict):
                continue
            data = response.get("data", {})
            if not isinstance(data, dict):
                continue

            pending: list[dict[str, Any]] = [data]
            while pending:
                candidate = pending.pop()
                items = candidate.get("items", [])
                if isinstance(items, list) and items:
                    last_item = items[-1]
                    if isinstance(last_item, dict):
                        product_id = str(last_item.get("productId", "")).strip()
                        variant_id = str(last_item.get("variantId", "")).strip()
                        payload: dict[str, Any] = {}
                        if product_id:
                            payload["productId"] = product_id
                        if variant_id:
                            payload["variantId"] = variant_id
                        if payload:
                            return payload
                for value in candidate.values():
                    if isinstance(value, dict):
                        pending.append(value)
        return {}

    def _looks_like_product_query(self, text: str) -> bool:
        if not text:
            return False
        if any(
            token in text
            for token in (
                'support',
                'ticket',
                'order',
                'refund',
                'cancel',
                'checkout',
                'memory',
                'preference',
                'cart',
            )
        ):
            return False
        product_tokens = (
            'shoe', 'shoes', 'sneaker', 'sneakers', 'runner', 'running', 'trail', 'hoodie',
            'jogger', 'joggers', 'sock', 'socks', 'backpack', 'bag', 'clothing', 'accessories',
            'denim', 'athleisure', 'tee', 'tshirt', 'shirt', 'pants', 'trousers', 'shorts',
            'jacket', 'coat', 'vest', 'hat', 'cap', 'beanie', 'gloves', 'watch', 'belt',
            'wallet', 'purse', 'handbag', 'tote'
        )
        return any(token in text for token in product_tokens)



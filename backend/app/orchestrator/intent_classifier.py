from __future__ import annotations

import re
from typing import Any

from app.infrastructure.llm_client import LLMClient
from app.orchestrator.types import IntentResult


class IntentClassifier:
    """Lightweight rule-first classifier for commerce intents."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def classify(self, message: str, context: dict[str, Any] | None = None) -> IntentResult:
        rule_intent = self._classify_rules(message=message, context=context)
        llm_choice = self._classify_with_llm(message=message, context=context)
        if llm_choice is None:
            return rule_intent
        if llm_choice.confidence >= max(0.7, rule_intent.confidence):
            return llm_choice
        return rule_intent

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
        entities: dict[str, Any] = {}

        if not text:
            return IntentResult(name="general_question", confidence=0.2, entities={})

        if ("cart" in text or "my cart" in text) and self._contains_order_status_phrase(text):
            entities.update(self._extract_order_id(text))
            return IntentResult(name="multi_status", confidence=0.9, entities=entities)

        # Memory intents.
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

        # Order intents.
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
        if "checkout" in text or "place order" in text or "buy now" in text:
            return IntentResult(name="checkout", confidence=0.95, entities={})

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

        if ("add" in text and "cart" in text) and any(
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
        ):
            entities.update(self._extract_quantity(text))
            entities.update(self._extract_product_or_variant_id(text))
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            entities["query"] = self._extract_search_query_for_combo(message)
            return IntentResult(name="search_and_add_to_cart", confidence=0.93, entities=entities)

        # Cart intents.
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
        if any(token in text for token in ("discount", "coupon", "promo")) and any(
            token in text for token in ("apply", "use", "code")
        ):
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
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            query = self._extract_add_query(message)
            if query:
                entities["query"] = query
            return IntentResult(name="add_to_cart", confidence=0.92, entities=entities)
        if self._is_view_cart_request(phrase_text):
            return IntentResult(name="view_cart", confidence=0.9, entities={})

        # Product intents.
        if any(token in text for token in ["find", "search", "show me", "recommend", "looking for"]):
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            entities["query"] = message.strip()
            return IntentResult(name="product_search", confidence=0.84, entities=entities)
        if self._is_price_refinement_request(text=phrase_text, context=context):
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            entities["query"] = message.strip()
            return IntentResult(name="product_search", confidence=0.8, entities=entities)
        if self._looks_like_product_query(phrase_text):
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_color(text))
            entities.update(self._extract_brand(message))
            entities["query"] = message.strip()
            return IntentResult(name="product_search", confidence=0.78, entities=entities)

        return IntentResult(name="general_question", confidence=0.6, entities={"query": message.strip()})

    def _extract_order_id(self, text: str) -> dict[str, Any]:
        match = re.search(r"(order[_\-]?\d+|ord[_\-]?\d+)", text)
        return {"orderId": match.group(1)} if match else {}

    def _extract_ticket_id(self, text: str) -> dict[str, Any]:
        match = re.search(r"(ticket[_\-]?(?:item[_\-]?)?\d+)", text)
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
        for color in ("black", "blue", "white", "green", "red", "gray", "charcoal", "navy"):
            if color in text:
                return {"color": color}
        return {}

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
            r"(?:brand|from)\s*(?:is|=|:)?\s*([a-zA-Z0-9&\-\s]{2,80})",
            message,
            flags=re.IGNORECASE,
        )
        if match:
            raw = match.group(1).strip(" .,;")
            if raw:
                return {"brand": raw}
        known = ("strideforge", "peakroute", "aerothread", "carryworks")
        lowered = message.lower()
        for token in known:
            if token in lowered:
                return {"brand": token}
        return {}

    def _extract_product_or_variant_id(self, text: str) -> dict[str, Any]:
        product_match = re.search(r"(prod[_\-]?\d+)", text)
        variant_match = re.search(r"(var[_\-]?\d+)", text)
        entities: dict[str, Any] = {}
        if product_match:
            entities["productId"] = product_match.group(1).replace("-", "_")
        if variant_match:
            entities["variantId"] = variant_match.group(1).replace("-", "_")
        return entities

    def _extract_product_or_item_id(self, text: str) -> dict[str, Any]:
        item_match = re.search(r"(item[_\-]?\d+)", text)
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
        explicit = re.search(
            r"(?:code|coupon|promo)\s*(?:is|=|:)?\s*([a-zA-Z0-9_-]{4,20})",
            message,
            flags=re.IGNORECASE,
        )
        if explicit:
            return {"code": explicit.group(1).upper()}

        candidates = re.findall(r"\b([A-Za-z0-9]{4,20})\b", message)
        stop_words = {"APPLY", "DISCOUNT", "COUPON", "PROMO", "CODE", "PLEASE", "THIS", "THAT"}
        for candidate in candidates:
            token = candidate.upper()
            if token not in stop_words and any(char.isdigit() for char in token):
                return {"code": token}
        return {}

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
        return True

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
            'shoe',
            'shoes',
            'sneaker',
            'sneakers',
            'runner',
            'running',
            'trail',
            'hoodie',
            'jogger',
            'joggers',
            'sock',
            'socks',
            'backpack',
            'bag',
            'clothing',
            'accessories',
            'denim',
            'athleisure',
        )
        return any(token in text for token in product_tokens)



from __future__ import annotations

import re
from typing import Any

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.product_service import ProductService


class ProductAgent(BaseAgent):
    name = "product"

    def __init__(self, product_service: ProductService) -> None:
        self.product_service = product_service

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        params = action.params
        raw_query = str(params.get("query", "")).strip()
        query = self._normalize_query(raw_query)
        if self._should_browse_without_query(raw_query=raw_query, normalized_query=query):
            query = ""
        inferred_category = self._infer_category(query)
        inferred_brand = self._infer_brand(query=query)
        preferred_category, preference_reason = self._preferred_category(context=context, query=query)
        preferred_brand, brand_reason = self._preferred_brand(context=context, query=query)
        category = inferred_category or preferred_category
        brand = inferred_brand or preferred_brand
        results = self.product_service.list_products(
            query=query or None,
            category=category,
            brand=brand,
            min_price=params.get("minPrice"),
            max_price=params.get("maxPrice"),
            page=1,
            limit=8,
        )

        preferred_color = self._preferred_color(context=context)
        if "color" in params or preferred_color:
            color = str(params.get("color") or preferred_color).lower()
            filtered_products: list[dict[str, Any]] = []
            for product in results["products"]:
                if any(v["color"].lower() == color for v in product["variants"]):
                    filtered_products.append(product)
            results["products"] = filtered_products
            results["pagination"]["total"] = len(filtered_products)
            results["pagination"]["pages"] = 1

        products = self._sort_with_affinity(results["products"], context=context)
        results["products"] = products
        reasons: list[str] = []
        if preference_reason:
            reasons.append(preference_reason)
        if brand_reason:
            reasons.append(brand_reason)
        reason_snippet = ""
        if reasons:
            reason_snippet = " Based on your saved preference for " + " and ".join(reasons) + "."
        if not products:
            return AgentExecutionResult(
                success=True,
                message=f"I couldn't find matching products.{reason_snippet} Want to broaden filters?",
                data={"products": [], "pagination": results["pagination"]},
                next_actions=[
                    {"label": "Show all products", "action": "search:all"},
                    {"label": "Set max price $150", "action": "search:under_150"},
                ],
            )

        top = products[0]
        top_variant = top["variants"][0]["id"] if top.get("variants") else ""
        next_actions = [{"label": "Show my cart", "action": "view_cart"}]
        if top_variant:
            next_actions.insert(
                0,
                {
                    "label": f"Add {top['name']}",
                    "action": f"add_to_cart:{top['id']}:{top_variant}",
                },
            )
        return AgentExecutionResult(
            success=True,
            message=(
                f"I found {len(products)} options. Top result: {top['name']} (${top['price']:.2f})."
                f"{reason_snippet}"
            ),
            data={"products": products, "pagination": results["pagination"]},
            next_actions=next_actions,
        )

    def _infer_category(self, query: str) -> str | None:
        lower = query.lower()
        if "shoe" in lower or "runner" in lower:
            return "shoes"
        if "hoodie" in lower or "jogger" in lower:
            return "clothing"
        if "sock" in lower or "backpack" in lower:
            return "accessories"
        return None

    def _infer_brand(self, *, query: str) -> str | None:
        lower = query.lower()
        if not lower:
            return None
        known = {
            "strideforge": "StrideForge",
            "peakroute": "PeakRoute",
            "aerothread": "AeroThread",
            "carryworks": "CarryWorks",
        }
        for token, canonical in known.items():
            if token in lower:
                return canonical
        return None

    def _normalize_query(self, query: str) -> str:
        lowered = query.lower()
        lowered = re.sub(
            r"\b(show me|find|search|looking for|i need|i want|please|recommend|suggest)\b",
            " ",
            lowered,
        )
        lowered = re.sub(r"\b(under|below|over|above)\s*\$?\d+\b", " ", lowered)
        lowered = re.sub(r"\b(something|anything|options)\b", " ", lowered)
        lowered = re.sub(r"\b(products?|items?)\b", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _should_browse_without_query(self, *, raw_query: str, normalized_query: str) -> bool:
        lower = raw_query.lower()
        if any(token in lower for token in ("recommend", "suggest", "anything", "something")):
            return True
        return normalized_query in {"", "me", "for me"}

    def _preferred_category(self, *, context: AgentContext, query: str) -> tuple[str | None, str]:
        preferences = context.preferences or {}
        preferred_categories = preferences.get("categories") if isinstance(preferences, dict) else None
        if isinstance(preferred_categories, list) and preferred_categories:
            category = str(preferred_categories[0]).strip().lower() or None
            return category, f"category {category}" if category else ""

        styles = preferences.get("stylePreferences") if isinstance(preferences, dict) else None
        if not query and isinstance(styles, list) and styles:
            if any("denim" == str(style).strip().lower() for style in styles):
                return "clothing", "style denim"

        memory = context.memory or {}
        affinities = memory.get("productAffinities") if isinstance(memory, dict) else None
        category_scores = affinities.get("categories", {}) if isinstance(affinities, dict) else {}
        if isinstance(category_scores, dict) and category_scores:
            category = str(max(category_scores.items(), key=lambda item: int(item[1]))[0]).lower()
            return category, f"your past interest in {category}"
        return None, ""

    def _preferred_color(self, *, context: AgentContext) -> str | None:
        preferences = context.preferences or {}
        colors = preferences.get("colorPreferences") if isinstance(preferences, dict) else None
        if isinstance(colors, list) and colors:
            candidate = str(colors[0]).strip().lower()
            return candidate or None
        return None

    def _preferred_brand(self, *, context: AgentContext, query: str) -> tuple[str | None, str]:
        preferences = context.preferences or {}
        brands = preferences.get("brandPreferences") if isinstance(preferences, dict) else None
        if isinstance(brands, list) and brands and not query:
            candidate = str(brands[0]).strip()
            if candidate:
                return candidate, f"brand {candidate}"

        memory = context.memory or {}
        affinities = memory.get("productAffinities") if isinstance(memory, dict) else None
        brand_scores = affinities.get("brands", {}) if isinstance(affinities, dict) else {}
        if isinstance(brand_scores, dict) and brand_scores:
            top_brand = max(brand_scores.items(), key=lambda item: int(item[1]))[0]
            candidate = str(top_brand).strip()
            if candidate:
                return candidate, f"your past interest in {candidate}"
        return None, ""

    def _sort_with_affinity(
        self, products: list[dict[str, Any]], *, context: AgentContext
    ) -> list[dict[str, Any]]:
        memory = context.memory or {}
        affinities = memory.get("productAffinities") if isinstance(memory, dict) else None
        if not isinstance(affinities, dict):
            return products

        product_scores = affinities.get("products", {})
        category_scores = affinities.get("categories", {})
        brand_scores = affinities.get("brands", {})
        if not isinstance(product_scores, dict) or not isinstance(category_scores, dict):
            return products

        def rank(item: dict[str, Any]) -> tuple[int, int, int, float]:
            product_id = str(item.get("id", ""))
            category = str(item.get("category", "")).strip().lower()
            brand = str(item.get("brand", "")).strip().lower()
            direct = int(product_scores.get(product_id, 0))
            by_category = int(category_scores.get(category, 0))
            by_brand = int(brand_scores.get(brand, 0)) if isinstance(brand_scores, dict) else 0
            rating = float(item.get("rating", 0.0))
            return (direct, by_category, by_brand, rating)

        return sorted(products, key=rank, reverse=True)

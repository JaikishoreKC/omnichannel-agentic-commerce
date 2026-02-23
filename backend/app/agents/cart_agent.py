from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.cart_service import CartService
from app.services.product_service import ProductService


@dataclass
class _AddResolution:
    product_id: str | None = None
    variant_id: str | None = None
    clarification: str = ""
    options: list[dict[str, Any]] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return bool(self.product_id and self.variant_id)


class CartAgent(BaseAgent):
    name = "cart"

    def __init__(self, cart_service: CartService, product_service: ProductService) -> None:
        self.cart_service = cart_service
        self.product_service = product_service

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = context.user_id
        session_id = context.session_id
        params = action.params

        if action.name == "get_cart":
            cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            return AgentExecutionResult(
                success=True,
                message=f"Your cart has {cart['itemCount']} item(s), total ${cart['total']:.2f}.",
                data={"cart": cart},
                next_actions=self._cart_next_actions(cart),
            )

        if action.name == "add_item":
            resolution = self._resolve_variant_for_add(params=params, context=context)
            if resolution.clarification:
                suggestion_actions = [
                    {
                        "label": f"Add {option['name']}",
                        "action": f"add_to_cart:{option['productId']}:{option['variantId']}",
                    }
                    for option in resolution.options[:3]
                ]
                return AgentExecutionResult(
                    success=False,
                    message=resolution.clarification,
                    data={"code": "CLARIFICATION_REQUIRED", "options": resolution.options},
                    next_actions=suggestion_actions,
                )
            if not resolution.resolved:
                return AgentExecutionResult(
                    success=False,
                    message="Tell me what to add, for example: add 2 running shoes to cart.",
                    data={},
                )

            product_id = str(resolution.product_id)
            variant_id = str(resolution.variant_id)
            quantity = self._safe_quantity(params.get("quantity", 1))
            cart = self.cart_service.add_item(
                user_id=user_id,
                session_id=session_id,
                product_id=product_id,
                variant_id=variant_id,
                quantity=quantity,
            )
            return AgentExecutionResult(
                success=True,
                message=(
                    f"Added item to cart: {self._product_name(product_id)} x{quantity}. "
                    f"New total is ${cart['total']:.2f}."
                ),
                data={"cart": cart},
                next_actions=self._cart_next_actions(cart),
            )

        if action.name == "add_multiple_items":
            raw_items = params.get("items", [])
            if not isinstance(raw_items, list) or not raw_items:
                return AgentExecutionResult(
                    success=False,
                    message="Tell me multiple items like: add 2 running shoes and 1 hoodie to cart.",
                    data={},
                )

            added: list[str] = []
            unresolved: list[str] = []
            clarifications: list[str] = []
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue
                resolution = self._resolve_variant_for_add(params=raw_item, context=context)
                if resolution.clarification:
                    unresolved.append(str(raw_item.get("query", "item")).strip())
                    clarifications.append(resolution.clarification)
                    continue
                if not resolution.resolved:
                    unresolved.append(str(raw_item.get("query", "item")).strip())
                    continue
                product_id = str(resolution.product_id)
                variant_id = str(resolution.variant_id)
                quantity = self._safe_quantity(raw_item.get("quantity", 1))
                self.cart_service.add_item(
                    user_id=user_id,
                    session_id=session_id,
                    product_id=product_id,
                    variant_id=variant_id,
                    quantity=quantity,
                )
                added.append(f"{self._product_name(product_id)} x{quantity}")

            cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            if not added:
                fallback = "I couldn't match those items. Try product names like running shoes or hoodie."
                return AgentExecutionResult(
                    success=False,
                    message=clarifications[0] if clarifications else fallback,
                    data={"cart": cart, "unresolved": unresolved, "clarifications": clarifications},
                )

            message = f"Added {', '.join(added)}."
            unresolved_clean = [name for name in unresolved if name]
            if unresolved_clean:
                message += f" I couldn't match: {', '.join(unresolved_clean)}."
            message += f" Cart total is ${cart['total']:.2f}."
            return AgentExecutionResult(
                success=True,
                message=message,
                data={"cart": cart, "unresolved": unresolved_clean},
                next_actions=self._cart_next_actions(cart),
            )

        if action.name == "clear_cart":
            cart = self.cart_service.clear_cart(user_id=user_id, session_id=session_id)
            return AgentExecutionResult(
                success=True,
                message="Cleared your cart.",
                data={"cart": cart},
                next_actions=self._cart_next_actions(cart),
            )

        if action.name == "adjust_item_quantity":
            cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            target = self._find_cart_item(cart=cart, params=params)
            if target is None:
                return AgentExecutionResult(
                    success=False,
                    message="I couldn't identify which cart item to adjust.",
                    data={"cart": cart},
                )

            delta = int(params.get("delta", 0))
            if delta == 0:
                delta = 1
            current_quantity = int(target.get("quantity", 1))
            next_quantity = current_quantity + delta
            if next_quantity <= 0:
                self.cart_service.remove_item(
                    user_id=user_id,
                    session_id=session_id,
                    item_id=str(target["itemId"]),
                )
                updated = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
                return AgentExecutionResult(
                    success=True,
                    message=f"Removed {target['name']} from cart.",
                    data={"cart": updated},
                    next_actions=self._cart_next_actions(updated),
                )

            updated = self.cart_service.update_item(
                user_id=user_id,
                session_id=session_id,
                item_id=str(target["itemId"]),
                quantity=next_quantity,
            )
            return AgentExecutionResult(
                success=True,
                message=(
                    f"Updated {target['name']} quantity from {current_quantity} to {next_quantity}. "
                    f"Total is now ${updated['total']:.2f}."
                ),
                data={"cart": updated},
                next_actions=self._cart_next_actions(updated),
            )

        if action.name == "update_item":
            cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            target = self._find_cart_item(cart=cart, params=params)
            if target is None:
                return AgentExecutionResult(
                    success=False,
                    message="Your cart is empty. Add an item first.",
                    data={"cart": cart},
                )

            quantity = self._safe_quantity(params.get("quantity", 1))
            updated = self.cart_service.update_item(
                user_id=user_id,
                session_id=session_id,
                item_id=str(target["itemId"]),
                quantity=quantity,
            )
            return AgentExecutionResult(
                success=True,
                message=f"Updated {target['name']} quantity to {quantity}. Total is now ${updated['total']:.2f}.",
                data={"cart": updated},
                next_actions=self._cart_next_actions(updated),
            )

        if action.name == "remove_item":
            cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            target = self._find_cart_item(cart=cart, params=params)
            if target is None:
                return AgentExecutionResult(
                    success=False,
                    message="Your cart is empty.",
                    data={"cart": cart},
                )

            remove_quantity = int(params.get("quantity", 0))
            current_quantity = int(target.get("quantity", 1))
            if remove_quantity > 0 and current_quantity > remove_quantity:
                updated = self.cart_service.update_item(
                    user_id=user_id,
                    session_id=session_id,
                    item_id=str(target["itemId"]),
                    quantity=current_quantity - remove_quantity,
                )
                return AgentExecutionResult(
                    success=True,
                    message=(
                        f"Removed {remove_quantity} of {target['name']}. "
                        f"Remaining quantity is {current_quantity - remove_quantity}."
                    ),
                    data={"cart": updated},
                    next_actions=self._cart_next_actions(updated),
                )

            self.cart_service.remove_item(user_id=user_id, session_id=session_id, item_id=str(target["itemId"]))
            updated = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            return AgentExecutionResult(
                success=True,
                message=f"Removed {target['name']} from cart. Cart total is ${updated['total']:.2f}.",
                data={"cart": updated},
                next_actions=self._cart_next_actions(updated),
            )

        if action.name == "apply_discount":
            code = str(params.get("code", "")).strip().upper()
            if not code:
                return AgentExecutionResult(
                    success=False,
                    message="Tell me the discount code to apply, for example: apply code SAVE20.",
                    data={},
                )
            cart = self.cart_service.apply_discount(
                user_id=user_id,
                session_id=session_id,
                discount_code=code,
            )
            discount_amount = float(cart.get("discount", 0.0))
            return AgentExecutionResult(
                success=True,
                message=f"Applied {code}. You saved ${discount_amount:.2f}.",
                data={"cart": cart},
                next_actions=self._cart_next_actions(cart),
            )

        raise HTTPException(status_code=400, detail=f"Unsupported cart action: {action.name}")

    def _safe_quantity(self, value: Any) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = 1
        return max(1, min(50, parsed))

    def _resolve_variant_for_add(
        self,
        *,
        params: dict[str, Any],
        context: AgentContext,
    ) -> _AddResolution:
        product_id = str(params.get("productId", "")).strip()
        variant_id = str(params.get("variantId", "")).strip()
        query = str(params.get("query", "")).strip()
        color = str(params.get("color", "")).strip().lower()
        size = str(params.get("size", "")).strip().lower()

        if product_id and variant_id:
            return _AddResolution(product_id=product_id, variant_id=variant_id)

        if product_id and not variant_id:
            try:
                product = self.product_service.get_product(product_id)
            except HTTPException:
                product = None
            if isinstance(product, dict):
                variants = self._matching_in_stock_variants(product=product, color=color, size=size)
                if len(variants) == 1:
                    return _AddResolution(product_id=product_id, variant_id=str(variants[0]["id"]))
                if len(variants) > 1:
                    options = [
                        self._resolution_option(product=product, variant=variant)
                        for variant in variants[:3]
                    ]
                    return _AddResolution(
                        clarification=(
                            f"I found multiple variants for {str(product.get('name', 'that product'))}. "
                            "Please specify size and/or color."
                        ),
                        options=options,
                    )

        if query:
            resolution = self._resolve_variant_from_query(
                query=query,
                color=color,
                size=size,
                brand=str(params.get("brand", "")).strip(),
                min_price=params.get("minPrice"),
                max_price=params.get("maxPrice"),
            )
            if resolution.resolved or resolution.clarification:
                return resolution

        inferred = self._infer_from_recent(context.recent_messages)
        inferred_product = str(inferred.get("productId", "")).strip()
        inferred_variant = str(inferred.get("variantId", "")).strip()
        if inferred_product and inferred_variant:
            return _AddResolution(product_id=inferred_product, variant_id=inferred_variant)
        return _AddResolution()

    def _resolve_variant_from_query(
        self,
        *,
        query: str,
        color: str,
        size: str,
        brand: str,
        min_price: Any,
        max_price: Any,
    ) -> _AddResolution:
        results = self.product_service.list_products(
            query=query,
            category=None,
            brand=brand or None,
            min_price=float(min_price) if isinstance(min_price, (int, float)) else None,
            max_price=float(max_price) if isinstance(max_price, (int, float)) else None,
            page=1,
            limit=8,
        )
        products = results.get("products", [])
        if not isinstance(products, list):
            return _AddResolution()

        candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        ambiguous_variant_options: list[dict[str, Any]] = []
        for product in products:
            if not isinstance(product, dict):
                continue
            variants = self._matching_in_stock_variants(product=product, color=color, size=size)
            if not variants:
                continue
            if len(variants) == 1:
                candidates.append((product, variants[0]))
                continue
            if not size and not color:
                candidates.append((product, variants[0]))
                continue
            ambiguous_variant_options.extend(
                [self._resolution_option(product=product, variant=variant) for variant in variants[:3]]
            )

        if not candidates and ambiguous_variant_options:
            option_names = ", ".join(option["name"] for option in ambiguous_variant_options[:3])
            clarification = (
                f"I found multiple size/color variants for '{query}': {option_names}. "
                "Please specify size and/or color."
            )
            return _AddResolution(
                clarification=clarification,
                options=ambiguous_variant_options[:3],
            )

        if not candidates:
            return _AddResolution()

        query_lower = query.strip().lower()
        query_tokens = [token for token in query_lower.split() if token]
        generic_queries = {"shoe", "shoes", "running", "runner", "trail", "clothing", "accessories"}
        strong_matches = [
            pair for pair in candidates if query_lower and query_lower in str(pair[0].get("name", "")).lower()
        ]

        if len(candidates) > 1 and (len(query_tokens) <= 1 or query_lower in generic_queries):
            narrowed = candidates
        else:
            narrowed = strong_matches if strong_matches else candidates

        if len(narrowed) == 1:
            product, variant = narrowed[0]
            return _AddResolution(product_id=str(product["id"]), variant_id=str(variant["id"]))

        options = [self._resolution_option(product=product, variant=variant) for product, variant in narrowed[:3]]
        names = ", ".join(option["name"] for option in options)
        clarification = f"I found multiple matches for '{query}': {names}. Which one should I add?"
        return _AddResolution(clarification=clarification, options=options)

    def _resolution_option(self, *, product: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
        size = str(variant.get("size", "")).strip()
        color = str(variant.get("color", "")).strip()
        suffix = ""
        if size or color:
            suffix = f" ({size or 'n/a'} / {color or 'n/a'})"
        return {
            "productId": str(product.get("id", "")),
            "variantId": str(variant.get("id", "")),
            "name": f"{str(product.get('name', 'item'))}{suffix}",
            "price": float(product.get("price", 0.0)),
            "size": size,
            "color": color,
        }

    def _matching_in_stock_variants(
        self,
        *,
        product: dict[str, Any],
        color: str,
        size: str,
    ) -> list[dict[str, Any]]:
        variants = product.get("variants", [])
        if not isinstance(variants, list):
            return []
        matches: list[dict[str, Any]] = []
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            if color and str(variant.get("color", "")).lower() != color:
                continue
            if size and str(variant.get("size", "")).lower() != size:
                continue
            if bool(variant.get("inStock", False)):
                matches.append(variant)
        return matches

    def _find_cart_item(self, *, cart: dict[str, Any], params: dict[str, Any]) -> dict[str, Any] | None:
        items = cart.get("items", [])
        if not isinstance(items, list):
            return None

        item_id = str(params.get("itemId", "")).strip()
        if item_id:
            return next((item for item in items if str(item.get("itemId", "")) == item_id), None)

        product_id = str(params.get("productId", "")).strip()
        if product_id:
            return next((item for item in items if str(item.get("productId", "")) == product_id), None)

        variant_id = str(params.get("variantId", "")).strip()
        if variant_id:
            return next((item for item in items if str(item.get("variantId", "")) == variant_id), None)

        query = str(params.get("query", "")).strip().lower()
        if query:
            query_tokens = {token for token in query.split() if token}
            best: tuple[int, dict[str, Any]] | None = None
            for item in items:
                name = str(item.get("name", "")).lower()
                name_tokens = set(name.split())
                score = len(query_tokens & name_tokens)
                if query in name:
                    score += 2
                if score <= 0:
                    continue
                if best is None or score > best[0]:
                    best = (score, item)
            if best is not None:
                return best[1]

        return items[0] if items else None

    def _product_name(self, product_id: str) -> str:
        try:
            product = self.product_service.get_product(product_id)
            name = str(product.get("name", "")).strip()
            if name:
                return name
        except HTTPException:
            pass
        return "item"

    def _infer_from_recent(self, recent: list[dict[str, Any]]) -> dict[str, Any]:
        for record in reversed(recent):
            data = record.get("response", {}).get("data", {})
            products = data.get("products", [])
            if products:
                first = products[0]
                variants = first.get("variants", [])
                if variants:
                    return {"productId": first.get("id"), "variantId": variants[0].get("id")}
        return {}

    def _cart_next_actions(self, cart: dict[str, Any]) -> list[dict[str, str]]:
        actions = [{"label": "Continue shopping", "action": "search:more"}]
        if cart["itemCount"] > 0:
            actions.append({"label": "Checkout", "action": "checkout"})
        return actions

from __future__ import annotations

from typing import Any, cast

from app.agents.cart_agent import CartAgent
from app.orchestrator.types import AgentContext


class _StubCartService:
    def get_cart(self, *, user_id: str | None, session_id: str) -> dict[str, Any]:
        _ = (user_id, session_id)
        return {"items": [], "itemCount": 0, "total": 0.0}


class _StubProductService:
    def __init__(self) -> None:
        self._products: dict[str, dict[str, Any]] = {
            "prod_1": {
                "id": "prod_1",
                "name": "AeroThread Audio Pro",
                "price": 225.95,
                "variants": [
                    {"id": "var_blue_m", "size": "M", "color": "Blue", "inStock": True},
                    {"id": "var_black_l", "size": "L", "color": "Black", "inStock": True},
                ],
            }
        }

    def get_product(self, product_id: str) -> dict[str, Any]:
        return {"product": self._products[product_id]}

    def list_products(
        self,
        *,
        query: str,
        category: str | None,
        brand: str | None,
        min_price: float | None,
        max_price: float | None,
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        _ = (query, category, brand, min_price, max_price, page, limit)
        return {"products": [self._products["prod_1"]]}


def _context(*, preferences: dict[str, Any] | None = None, recent: list[dict[str, Any]] | None = None) -> AgentContext:
    return AgentContext(
        session_id="session_1",
        user_id="user_1",
        channel="web",
        session={"id": "session_1"},
        cart={"items": [], "itemCount": 0, "total": 0.0},
        preferences=preferences,
        memory=None,
        recent_messages=recent or [],
    )


def test_infer_from_recent_prefers_clarification_option() -> None:
    agent = CartAgent(
        cart_service=cast(Any, _StubCartService()),
        product_service=cast(Any, _StubProductService()),
    )
    recent = [
        {
            "response": {
                "data": {
                    "code": "CLARIFICATION_REQUIRED",
                    "options": [
                        {"productId": "prod_1", "variantId": "var_blue_m", "name": "Audio Pro (M / Blue)"}
                    ],
                }
            }
        }
    ]

    inferred = agent._infer_from_recent(recent)

    assert inferred == {"productId": "prod_1", "variantId": "var_blue_m"}


def test_resolve_variant_for_add_uses_saved_preferences() -> None:
    agent = CartAgent(
        cart_service=cast(Any, _StubCartService()),
        product_service=cast(Any, _StubProductService()),
    )
    resolution = agent._resolve_variant_for_add(
        params={"query": "AeroThread Audio Pro"},
        context=_context(
            preferences={
                "size": "M",
                "colorPreferences": ["blue"],
            }
        ),
    )

    assert resolution.resolved
    assert resolution.product_id == "prod_1"
    assert resolution.variant_id == "var_blue_m"


def test_resolve_variant_for_add_lists_available_options() -> None:
    agent = CartAgent(
        cart_service=cast(Any, _StubCartService()),
        product_service=cast(Any, _StubProductService()),
    )
    resolution = agent._resolve_variant_for_add(
        params={"productId": "prod_1"},
        context=_context(),
    )

    assert not resolution.resolved
    assert "Available options:" in resolution.clarification
    assert "size" in resolution.clarification.lower()
    assert "color" in resolution.clarification.lower()
    assert len(resolution.options) >= 2


def test_infer_from_recent_handles_malformed_payload_safely() -> None:
    agent = CartAgent(
        cart_service=cast(Any, _StubCartService()),
        product_service=cast(Any, _StubProductService()),
    )
    recent = [
        {"response": {"data": {"products": ["invalid"]}}},
        {"response": {"data": {"products": [{"id": "prod_1", "variants": ["invalid"]}]}}},
        {"response": {"data": None}},
        {"response": None},
        "invalid",
    ]

    inferred = agent._infer_from_recent(cast(Any, recent))

    assert inferred == {}


def test_infer_from_recent_reads_nested_orchestrator_product_payload() -> None:
    agent = CartAgent(
        cart_service=cast(Any, _StubCartService()),
        product_service=cast(Any, _StubProductService()),
    )
    recent = [
        {
            "response": {
                "data": {
                    "product": {
                        "products": [
                            {
                                "id": "prod_1",
                                "variants": [
                                    {"id": "var_black_l", "size": "L", "color": "Black", "inStock": True},
                                    {"id": "var_blue_m", "size": "M", "color": "Blue", "inStock": False},
                                ],
                            }
                        ]
                    }
                }
            }
        }
    ]

    inferred = agent._infer_from_recent(cast(Any, recent))

    assert inferred == {"productId": "prod_1", "variantId": "var_black_l"}


def test_infer_from_recent_uses_last_cart_item_when_available() -> None:
    agent = CartAgent(
        cart_service=cast(Any, _StubCartService()),
        product_service=cast(Any, _StubProductService()),
    )
    recent = [
        {
            "response": {
                "data": {
                    "cart": {
                        "items": [
                            {
                                "productId": "prod_1",
                                "variantId": "var_blue_m",
                                "name": "AeroThread Audio Pro",
                            }
                        ]
                    }
                }
            }
        }
    ]

    inferred = agent._infer_from_recent(cast(Any, recent))

    assert inferred == {"productId": "prod_1", "variantId": "var_blue_m"}


def test_resolve_variant_for_add_uses_recent_item_for_default_query() -> None:
    agent = CartAgent(
        cart_service=cast(Any, _StubCartService()),
        product_service=cast(Any, _StubProductService()),
    )
    recent = [
        {
            "response": {
                "data": {
                    "cart": {
                        "items": [
                            {
                                "productId": "prod_1",
                                "variantId": "var_blue_m",
                            }
                        ]
                    }
                }
            }
        }
    ]

    resolution = agent._resolve_variant_for_add(
        params={"query": "default", "quantity": 2},
        context=_context(recent=recent),
    )

    assert resolution.resolved
    assert resolution.product_id == "prod_1"
    assert resolution.variant_id == "var_blue_m"

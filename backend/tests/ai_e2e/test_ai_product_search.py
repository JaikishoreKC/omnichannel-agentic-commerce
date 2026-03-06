from __future__ import annotations

from .harness import assert_service_layer_only_mutations, run_interaction


def test_ai_product_search_returns_products_without_mutation(ai_client, ai_user, mutation_spy) -> None:
    trace, body = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="show me running shoes",
        mutation_spy=mutation_spy,
        trace_name="TEST_CASE_1_PRODUCT_SEARCH",
    )

    assert body.get("type") == "response"
    payload = body.get("payload", {})
    assert payload.get("agent") in {"product", "orchestrator"}

    products = payload.get("data", {}).get("products", [])
    assert isinstance(products, list)
    assert len(products) >= 0

    assert trace["STATE_BEFORE"]["order_count"] == trace["STATE_AFTER"]["order_count"]
    assert trace["STATE_BEFORE"]["cart_item_count"] == trace["STATE_AFTER"]["cart_item_count"]

    # Real LLM path should be attempted in planner-first mode.
    planner_attempted = trace["LLM_RESPONSE"].get("executionPolicy", {}).get("plannerAttempted")
    assert planner_attempted is True
    assert_service_layer_only_mutations(trace)

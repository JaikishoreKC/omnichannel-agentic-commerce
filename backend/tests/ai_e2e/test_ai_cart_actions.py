from __future__ import annotations

from .harness import assert_service_layer_only_mutations, run_interaction


def test_ai_add_to_cart_and_query_cart(ai_client, ai_user, mutation_spy) -> None:
    _, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="show me running shoes",
        mutation_spy=mutation_spy,
        trace_name="PREP_SEARCH",
    )

    trace_add, body_add = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="add the first running shoe to my cart",
        mutation_spy=mutation_spy,
        trace_name="TEST_CASE_2_ADD_TO_CART",
    )

    assert body_add.get("type") == "response"
    assert trace_add["STATE_AFTER"]["cart_item_count"] >= 1
    assert trace_add["STATE_AFTER"]["order_count"] == trace_add["STATE_BEFORE"]["order_count"]
    assert_service_layer_only_mutations(trace_add)

    trace_cart, body_cart = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="what's in my cart?",
        mutation_spy=mutation_spy,
        trace_name="TEST_CASE_3_CART_QUERY",
    )

    payload = body_cart.get("payload", {})
    message = str(payload.get("message", "")).lower()
    assert payload.get("agent") in {"cart", "orchestrator"}
    assert "cart" in message or "item" in message
    assert trace_cart["STATE_AFTER"]["cart_item_count"] >= 1
    assert trace_cart["STATE_AFTER"]["order_count"] == trace_cart["STATE_BEFORE"]["order_count"]
    assert_service_layer_only_mutations(trace_cart)


def test_ai_session_context_preserved_across_messages(ai_client, ai_user, mutation_spy) -> None:
    _, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="show me running shoes",
        mutation_spy=mutation_spy,
        trace_name="SESSION_CTX_SEARCH",
    )
    _, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="add the first running shoe to my cart",
        mutation_spy=mutation_spy,
        trace_name="SESSION_CTX_ADD",
    )

    trace, body = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="what is in my cart now?",
        mutation_spy=mutation_spy,
        trace_name="TEST_CASE_7_SESSION_CONTEXT",
    )

    payload = body.get("payload", {})
    assert payload.get("agent") in {"cart", "orchestrator"}
    assert trace["STATE_AFTER"]["session_exists"] is True
    assert trace["STATE_AFTER"]["cart_item_count"] >= 1
    assert_service_layer_only_mutations(trace)

from __future__ import annotations

from .harness import assert_service_layer_only_mutations, run_interaction


def test_ai_checkout_flow_creates_order_and_updates_inventory(ai_client, ai_user, mutation_spy) -> None:
    _, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="show me running shoes",
        mutation_spy=mutation_spy,
        trace_name="CHECKOUT_PREP_SEARCH",
    )
    trace_add, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="add the first running shoe to my cart",
        mutation_spy=mutation_spy,
        trace_name="CHECKOUT_PREP_ADD",
    )
    assert trace_add["STATE_AFTER"]["cart_item_count"] >= 1

    before_inv = trace_add["STATE_AFTER"]["inventory"]["ai_var_run_001"]
    assert isinstance(before_inv, dict)

    trace_checkout, body_checkout = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="I want to buy everything in my cart",
        mutation_spy=mutation_spy,
        trace_name="TEST_CASE_4_CHECKOUT_FLOW",
    )

    payload = body_checkout.get("payload", {})
    data = payload.get("data", {})

    assert body_checkout.get("type") == "response"
    assert payload.get("agent") in {"order", "orchestrator"}
    assert trace_checkout["STATE_AFTER"]["order_count"] >= trace_checkout["STATE_BEFORE"]["order_count"] + 1

    after_inv = trace_checkout["STATE_AFTER"]["inventory"]["ai_var_run_001"]
    assert isinstance(after_inv, dict)
    assert int(after_inv.get("totalQuantity", 0)) <= int(before_inv.get("totalQuantity", 0))

    # Active cart should be cleared/converted after successful checkout.
    assert trace_checkout["STATE_AFTER"]["cart_item_count"] == 0
    assert trace_checkout["STATE_AFTER"]["cart_status"] in {"", "active", "converted"}

    # Verify service-layer mutation path and structured execution trace.
    assert trace_checkout["LLM_RESPONSE"].get("executionPolicy", {}).get("plannerAttempted") is True
    assert isinstance(trace_checkout["DATABASE_WRITE"], list)
    assert_service_layer_only_mutations(trace_checkout)

    # If the order payload is present, validate shape.
    if isinstance(data.get("order"), dict):
        status = str(data["order"].get("status", "")).strip().lower()
        assert status in {"", "confirmed", "created", "processing"}

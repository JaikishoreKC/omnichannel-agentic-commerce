from __future__ import annotations

from typing import Any

import pytest

from app.container import container

from .harness import assert_service_layer_only_mutations, run_interaction, snapshot_state


def _write_components(trace: dict[str, Any]) -> set[str]:
    return {str(event.get("component", "")) for event in trace.get("DATABASE_WRITE", [])}


def test_ai_ambiguous_request_does_not_mutate_domain_state(ai_client, ai_user, mutation_spy) -> None:
    trace, body = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="maybe I should buy shoes later",
        mutation_spy=mutation_spy,
        trace_name="TEST_CASE_5_AMBIGUOUS",
    )

    payload = body.get("payload", {})
    message = str(payload.get("message", "")).lower()

    assert trace["STATE_AFTER"]["order_count"] == trace["STATE_BEFORE"]["order_count"]
    assert trace["STATE_AFTER"]["cart_item_count"] == trace["STATE_BEFORE"]["cart_item_count"]
    assert _write_components(trace).isdisjoint({"order_repository", "inventory_repository", "product_repository"})
    assert any(token in message for token in ("clarify", "rephrase", "help", "later", "buy", "found", "options"))
    assert_service_layer_only_mutations(trace)


def test_ai_invalid_action_rejected_without_product_mutation(ai_client, ai_user, mutation_spy) -> None:
    trace, body = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="delete all products",
        mutation_spy=mutation_spy,
        trace_name="TEST_CASE_6_INVALID_ACTION",
    )

    payload = body.get("payload", {})
    message = str(payload.get("message", "")).lower()

    assert trace["STATE_AFTER"]["order_count"] == trace["STATE_BEFORE"]["order_count"]
    assert trace["STATE_AFTER"]["cart_item_count"] == trace["STATE_BEFORE"]["cart_item_count"]
    assert _write_components(trace).isdisjoint({"product_repository", "inventory_repository", "order_repository"})
    assert any(token in message for token in ("can't", "cannot", "not", "help", "sorry"))
    assert_service_layer_only_mutations(trace)


def test_ai_error_scenarios_handle_failures_safely(ai_client, ai_user, mutation_spy, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prime cart for checkout-related failure scenarios.
    _, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="show me running shoes",
        mutation_spy=mutation_spy,
        trace_name="ERROR_PREP_SEARCH",
    )
    _, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="add the first running shoe to my cart",
        mutation_spy=mutation_spy,
        trace_name="ERROR_PREP_ADD",
    )

    before = snapshot_state(user_id=ai_user.user_id, session_id=ai_user.session_id)

    # Scenario A: malformed LLM output should degrade safely.
    original_call_llm = container.llm_client._call_llm
    monkeypatch.setattr(container.llm_client, "_call_llm", lambda **_: "not-json-response")
    trace_malformed, body_malformed = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="show me running shoes",
        mutation_spy=mutation_spy,
        trace_name="ERROR_MALFORMED_LLM",
    )
    assert body_malformed.get("type") == "response"
    assert trace_malformed["STATE_AFTER"]["order_count"] == trace_malformed["STATE_BEFORE"]["order_count"]

    monkeypatch.setattr(container.llm_client, "_call_llm", original_call_llm)

    # Scenario B: payment failure must not create order / must keep inventory coherent.
    def _payment_fail(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("simulated payment failure")

    original_authorize = container.payment_service.authorize
    monkeypatch.setattr(container.payment_service, "authorize", _payment_fail)
    try:
        trace_payment_fail, _ = run_interaction(
            ai_client,
            user_ctx=ai_user,
            message="I want to buy everything in my cart",
            mutation_spy=mutation_spy,
            trace_name="ERROR_PAYMENT_FAILURE",
        )
        assert trace_payment_fail["STATE_AFTER"]["order_count"] == trace_payment_fail["STATE_BEFORE"]["order_count"]
        inv_before = trace_payment_fail["STATE_BEFORE"]["inventory"]["ai_var_run_001"]
        inv_after = trace_payment_fail["STATE_AFTER"]["inventory"]["ai_var_run_001"]
        assert inv_before == inv_after
    except RuntimeError as exc:
        assert "simulated payment failure" in str(exc).lower()

    monkeypatch.setattr(container.payment_service, "authorize", original_authorize)

    # Scenario C: inventory unavailable.
    container.inventory_service.update_variant_inventory(variant_id="ai_var_run_001", available_quantity=0)
    trace_inventory_fail, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="add the first running shoe to my cart",
        mutation_spy=mutation_spy,
        trace_name="ERROR_INVENTORY_UNAVAILABLE",
    )
    assert trace_inventory_fail["STATE_AFTER"]["order_count"] == trace_inventory_fail["STATE_BEFORE"]["order_count"]

    # Scenario D: order repository persistence failure.
    original_create = container.order_repository.create

    def _repo_fail(order: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("simulated db write failure")

    monkeypatch.setattr(container.order_repository, "create", _repo_fail)
    trace_repo_fail, _ = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="I want to buy everything in my cart",
        mutation_spy=mutation_spy,
        trace_name="ERROR_DB_FAILURE",
    )
    assert trace_repo_fail["STATE_AFTER"]["order_count"] == trace_repo_fail["STATE_BEFORE"]["order_count"]

    monkeypatch.setattr(container.order_repository, "create", original_create)

    after = snapshot_state(user_id=ai_user.user_id, session_id=ai_user.session_id)
    assert after["order_count"] >= before["order_count"]
    assert_service_layer_only_mutations(trace_repo_fail)


def test_ai_rejects_invalid_tool_arguments_from_llm(ai_client, ai_user, mutation_spy, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force planner output with invalid add_item args.
    monkeypatch.setattr(
        container.llm_client,
        "_call_llm",
        lambda **_: (
            '{"actions":[{"name":"add_item","targetAgent":"cart","params":'
            '{"productId":"nonexistent_product","variantId":"bad_variant","quantity":-99}}],'
            '"confidence":0.99,"needsClarification":false,"clarificationQuestion":""}'
        ),
    )

    trace, body = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="add shoes to cart",
        mutation_spy=mutation_spy,
        trace_name="INVALID_TOOL_ARGUMENTS",
    )

    # Request should be safely handled, without creating order/product/inventory side-effects.
    assert body.get("type") in {"response", "error", None}
    assert trace["STATE_AFTER"]["order_count"] == trace["STATE_BEFORE"]["order_count"]
    assert _write_components(trace).isdisjoint({"order_repository", "product_repository", "inventory_repository"})
    assert_service_layer_only_mutations(trace)


def test_ai_rejects_hallucinated_tool_without_mutation(ai_client, ai_user, mutation_spy, monkeypatch: pytest.MonkeyPatch) -> None:
    # Planner returns unknown action; orchestrator should drop it and avoid unsafe mutation.
    monkeypatch.setattr(
        container.llm_client,
        "_call_llm",
        lambda **_: (
            '{"actions":[{"name":"delete_all_products","targetAgent":"orchestrator","params":{}}],'
            '"confidence":0.99,"needsClarification":false,"clarificationQuestion":""}'
        ),
    )

    trace, body = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="delete all products now",
        mutation_spy=mutation_spy,
        trace_name="HALLUCINATED_TOOL",
    )

    assert body.get("type") == "response"
    planner_meta = trace.get("LLM_RESPONSE", {}).get("planner", {})
    assert int(planner_meta.get("droppedActionCount", 0)) >= 1 or int(planner_meta.get("actionCount", 0)) == 0
    assert trace["STATE_AFTER"]["order_count"] == trace["STATE_BEFORE"]["order_count"]
    assert _write_components(trace).isdisjoint({"product_repository", "inventory_repository", "order_repository"})
    assert_service_layer_only_mutations(trace)

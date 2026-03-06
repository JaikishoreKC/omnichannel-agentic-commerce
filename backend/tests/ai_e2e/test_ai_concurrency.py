from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import pytest

from .harness import create_test_user_context, make_client, run_interaction


def _conversation(worker_id: int) -> dict[str, object]:
    client = make_client()
    user = create_test_user_context(
        client,
        email=f"ai-e2e-concurrency-{worker_id}-{uuid4().hex[:6]}@example.com",
        password="SecurePass123!",
    )

    # Local no-op mutation spy shape for helper compatibility.
    class _NoopSpy:
        def reset(self) -> None:
            return None

        def write_events(self):
            return []

    spy = _NoopSpy()

    run_interaction(
        client,
        user_ctx=user,
        message="show me running shoes",
        mutation_spy=spy,  # type: ignore[arg-type]
        trace_name=f"CONCURRENCY_{worker_id}_SEARCH",
    )
    run_interaction(
        client,
        user_ctx=user,
        message="add the first running shoe to my cart",
        mutation_spy=spy,  # type: ignore[arg-type]
        trace_name=f"CONCURRENCY_{worker_id}_ADD",
    )
    trace, _ = run_interaction(
        client,
        user_ctx=user,
        message="what's in my cart?",
        mutation_spy=spy,  # type: ignore[arg-type]
        trace_name=f"CONCURRENCY_{worker_id}_QUERY",
    )

    return {
        "worker_id": worker_id,
        "user_id": user.user_id,
        "session_id": user.session_id,
        "cart_item_count": trace["STATE_AFTER"]["cart_item_count"],
        "order_count": trace["STATE_AFTER"]["order_count"],
    }


def test_ai_concurrent_conversations_isolated_sessions() -> None:
    if str(os.getenv("AI_E2E_MODE", "live")).strip().lower() == "replay":
        pytest.skip("Concurrency stress test is skipped in replay mode")

    workers = 12
    results: list[dict[str, object]] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_conversation, idx) for idx in range(workers)]
        for future in as_completed(futures):
            results.append(future.result())

    assert len(results) == workers
    assert len({str(row["user_id"]) for row in results}) == workers
    assert len({str(row["session_id"]) for row in results}) == workers

    for row in results:
        cart_item_count = row["cart_item_count"]
        order_count = row["order_count"]
        assert isinstance(cart_item_count, int)
        assert isinstance(order_count, int)
        assert cart_item_count >= 1
        assert order_count == 0

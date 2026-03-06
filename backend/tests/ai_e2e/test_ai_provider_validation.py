from __future__ import annotations

import pytest

from .harness import get_ai_e2e_mode, run_interaction

pytestmark = [
    pytest.mark.provider_suite,
    pytest.mark.skipif(get_ai_e2e_mode() != "provider", reason="Provider validation tests require AI_E2E_MODE=provider"),
]


def test_provider_mode_records_successful_llm_call(ai_client, ai_user, mutation_spy) -> None:
    trace, body = run_interaction(
        ai_client,
        user_ctx=ai_user,
        message="Can you help me choose a useful birthday gift under $50?",
        mutation_spy=mutation_spy,
        trace_name="TEST_CASE_PROVIDER_PROOF_GENERAL",
    )

    assert body.get("type") == "response"
    provider_proof = trace.get("LLM_PROVIDER_PROOF", {})
    assert provider_proof.get("calls_attempted_delta", 0) >= 1
    assert provider_proof.get("calls_succeeded_delta", 0) >= 1

    calls = provider_proof.get("calls", [])
    assert isinstance(calls, list)
    assert any(call.get("role") in {"general", "planner"} for call in calls)

from __future__ import annotations

from uuid import uuid4

import pytest

from .harness import (
    MUTATION_METHODS,
    MutationSpy,
    configure_replay_llm_settings,
    configure_real_llm_settings,
    create_test_user_context,
    get_ai_e2e_mode,
    get_real_llm_api_keys_from_env,
    install_llm_record_replay,
    make_client,
    restore_llm_settings,
    seed_deterministic_catalog,
)


@pytest.fixture(scope="session")
def require_real_llm_keys() -> tuple[str, str] | None:
    mode = get_ai_e2e_mode()
    if mode == "replay":
        return None
    planner_key, general_key = get_real_llm_api_keys_from_env()
    if not planner_key or not general_key:
        pytest.skip(
            "Real LLM API keys must be set in OPENROUTER_API_KEY_PLANNER and "
            "OPENROUTER_API_KEY_GENERAL; or use AI_E2E_MODE=replay"
        )
    return planner_key, general_key


@pytest.fixture(autouse=True)
def real_llm_mode(require_real_llm_keys: tuple[str, str] | None):
    mode = get_ai_e2e_mode()
    _ = require_real_llm_keys
    if mode == "replay":
        original = configure_replay_llm_settings()
    else:
        original = configure_real_llm_settings()
    restore_llm = install_llm_record_replay()
    try:
        yield
    finally:
        restore_llm()
        restore_llm_settings(original)


@pytest.fixture
def ai_client():
    return make_client()


@pytest.fixture(autouse=True)
def seeded_catalog():
    seed_deterministic_catalog()


@pytest.fixture
def mutation_spy(monkeypatch: pytest.MonkeyPatch) -> MutationSpy:
    spy = MutationSpy()
    for instance, method_name, component in MUTATION_METHODS:
        original = getattr(instance, method_name)
        monkeypatch.setattr(instance, method_name, spy.wrap(component=component, method=method_name, fn=original))
    return spy


@pytest.fixture
def ai_user(ai_client):
    email = f"ai-e2e-{uuid4().hex[:10]}@example.com"
    return create_test_user_context(ai_client, email=email, password="SecurePass123!")

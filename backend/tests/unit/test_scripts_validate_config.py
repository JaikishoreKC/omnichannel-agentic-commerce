from __future__ import annotations

import pytest

from app.core.config import Settings
from app.scripts import validate_config


def test_collect_issues_requires_non_default_token_secret() -> None:
    settings = Settings(token_secret="replace-with-strong-secret")
    issues = validate_config._collect_issues(settings)
    assert any("TOKEN_SECRET" in issue for issue in issues)


def test_collect_issues_requires_llm_keys_when_enabled() -> None:
    settings = Settings(
        token_secret="x" * 40,
        llm_enabled=True,
        openrouter_api_key_planner="",
        openrouter_api_key_general="",
    )
    issues = validate_config._collect_issues(settings)
    assert any("OPENROUTER_API_KEY_PLANNER" in issue for issue in issues)
    assert any("OPENROUTER_API_KEY_GENERAL" in issue for issue in issues)


def test_collect_issues_requires_superu_fields_when_enabled() -> None:
    settings = Settings(
        token_secret="x" * 40,
        superu_enabled=True,
        superu_api_key="",
        superu_assistant_id="",
        superu_from_phone_number="",
        superu_webhook_secret="",
    )
    issues = validate_config._collect_issues(settings)
    assert any("SUPERU_API_KEY" in issue for issue in issues)
    assert any("SUPERU_ASSISTANT_ID" in issue for issue in issues)
    assert any("SUPERU_FROM_PHONE_NUMBER" in issue for issue in issues)
    assert any("SUPERU_WEBHOOK_SECRET" in issue for issue in issues)


def test_run_reports_ok_when_config_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    safe_settings = Settings(
        environment="development",
        token_secret="x" * 40,
        llm_enabled=False,
        superu_enabled=False,
    )
    monkeypatch.setattr(validate_config.Settings, "from_env", classmethod(lambda cls: safe_settings))

    summary = validate_config.run(strict=True)
    assert summary["ok"] is True
    assert summary["issues"] == []


def test_run_includes_validate_security_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    insecure_settings = Settings(
        environment="production",
        token_secret="short",
    )
    monkeypatch.setattr(validate_config.Settings, "from_env", classmethod(lambda cls: insecure_settings))

    summary = validate_config.run(strict=True)
    assert summary["ok"] is False
    assert any("TOKEN_SECRET" in issue for issue in summary["issues"])

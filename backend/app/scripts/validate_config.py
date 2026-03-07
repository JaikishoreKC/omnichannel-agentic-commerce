from __future__ import annotations

import argparse
import json
from typing import Any

from app.core.config import Settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate runtime environment configuration for release safety.")
    parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Return non-zero exit code when any config validation issue is found.",
    )
    return parser


def _collect_issues(settings: Settings) -> list[str]:
    issues: list[str] = []

    token_secret = str(settings.token_secret or "").strip()
    if not token_secret or token_secret == "replace-with-strong-secret":
        issues.append("TOKEN_SECRET must be explicitly set and cannot use default placeholder")

    if settings.admin_mfa_required:
        mfa_secret = str(settings.admin_mfa_totp_secret or "").strip()
        if not mfa_secret or mfa_secret == "JBSWY3DPEHPK3PXP":
            issues.append("ADMIN_MFA_TOTP_SECRET must be non-default when ADMIN_MFA_REQUIRED is enabled")

    if settings.llm_enabled:
        planner_key = str(settings.openrouter_api_key_planner or "").strip()
        general_key = str(settings.openrouter_api_key_general or "").strip()
        if not planner_key:
            issues.append("OPENROUTER_API_KEY_PLANNER is required when LLM_ENABLED=true")
        if not general_key:
            issues.append("OPENROUTER_API_KEY_GENERAL is required when LLM_ENABLED=true")

    if settings.superu_enabled:
        required_superu = {
            "SUPERU_API_KEY": str(settings.superu_api_key or "").strip(),
            "SUPERU_ASSISTANT_ID": str(settings.superu_assistant_id or "").strip(),
            "SUPERU_FROM_PHONE_NUMBER": str(settings.superu_from_phone_number or "").strip(),
            "SUPERU_WEBHOOK_SECRET": str(settings.superu_webhook_secret or "").strip(),
        }
        for key, value in required_superu.items():
            if not value:
                issues.append(f"{key} is required when SUPERU_ENABLED=true")

    if settings.voice_recovery_scheduler_enabled and not settings.superu_enabled:
        issues.append("VOICE_RECOVERY_SCHEDULER_ENABLED=true requires SUPERU_ENABLED=true")

    return issues


def run(*, strict: bool) -> dict[str, Any]:
    settings = Settings.from_env()
    issues = _collect_issues(settings)

    # Reuse production-grade checks when running in production-like environments.
    try:
        settings.validate_security()
    except ValueError as exc:
        issue = str(exc).strip()
        if issue and issue not in issues:
            issues.append(issue)

    summary = {
        "ok": len(issues) == 0,
        "strict": strict,
        "issues": issues,
        "environment": settings.environment,
        "flags": {
            "llmEnabled": settings.llm_enabled,
            "superuEnabled": settings.superu_enabled,
            "voiceRecoverySchedulerEnabled": settings.voice_recovery_scheduler_enabled,
            "adminMfaRequired": settings.admin_mfa_required,
        },
    }
    return summary


def main() -> int:
    args = _parser().parse_args()
    summary = run(strict=args.strict)
    print(json.dumps(summary, indent=2))
    if args.strict and not summary["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

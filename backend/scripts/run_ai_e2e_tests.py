from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _print(msg: str) -> None:
    print(msg, flush=True)


def _validate_env(mode: str) -> None:
    if mode == "replay":
        return
    planner_key = str(os.getenv("OPENROUTER_API_KEY_PLANNER", "")).strip()
    general_key = str(os.getenv("OPENROUTER_API_KEY_GENERAL", "")).strip()
    if not planner_key or not general_key:
        raise SystemExit(
            "Missing OpenRouter keys. Set OPENROUTER_API_KEY_PLANNER and OPENROUTER_API_KEY_GENERAL "
            "or run with AI_E2E_MODE=replay"
        )


def _resolve_suite(mode: str) -> str:
    raw = str(os.getenv("AI_E2E_SUITE", "")).strip().lower()
    if not raw:
        suite = "provider" if mode == "provider" else "behavior"
        os.environ["AI_E2E_SUITE"] = suite
        return suite

    if raw in {"behavior", "provider", "all"}:
        return raw

    suite = "provider" if mode == "provider" else "behavior"
    os.environ["AI_E2E_SUITE"] = suite
    return suite


def _build_pytest_cmd(suite: str) -> list[str]:
    cmd = [sys.executable, "-m", "pytest", "tests/ai_e2e", "-s"]
    if suite == "behavior":
        cmd.extend(["-m", "not provider_suite"])
    elif suite == "provider":
        cmd.extend(["-m", "provider_suite"])
    return cmd


def _collect_provider_stats(trace_files: list[Path]) -> dict[str, int]:
    stats = {
        "interactions_with_provider_data": 0,
        "calls_attempted": 0,
        "calls_succeeded": 0,
        "calls_failed": 0,
    }
    for trace_file in trace_files:
        try:
            payload = json.loads(trace_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        provider = payload.get("LLM_PROVIDER_PROOF")
        if not isinstance(provider, dict):
            continue
        stats["interactions_with_provider_data"] += 1
        stats["calls_attempted"] += int(provider.get("calls_attempted_delta", 0) or 0)
        stats["calls_succeeded"] += int(provider.get("calls_succeeded_delta", 0) or 0)
        stats["calls_failed"] += int(provider.get("calls_failed_delta", 0) or 0)
    return stats


def _bootstrap_data() -> None:
    backend_root = _backend_root()
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from tests.ai_e2e.harness import create_test_user_context, make_client, seed_deterministic_catalog

    client = make_client()
    seed_deterministic_catalog()
    _print("Catalog seeded")

    email = f"ai-e2e-runner-{uuid4().hex[:10]}@example.com"
    create_test_user_context(client, email=email, password="SecurePass123!")
    _print("Test user created")


def _parse_summary(output: str) -> dict[str, int]:
    summary = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    # Works for lines like:
    # "206 passed, 8 skipped in 41.70s"
    # "1 failed, 9 errors in 139.85s"
    matches = re.findall(r"(\d+)\s+(passed|failed|skipped|errors?)", output)
    for count_raw, label in matches:
        label_norm = label.rstrip("s")
        count = int(count_raw)
        if label_norm == "error":
            summary["errors"] += count
        else:
            summary[label_norm] += count
    return summary


def _run_pytest_streaming(cmd: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    """Run pytest and stream logs in real time while keeping combined output for summary parsing."""
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        bufsize=1,
    )

    lines: list[str] = []
    if process.stdout is not None:
        for line in process.stdout:
            lines.append(line)
            print(line, end="")

    return_code = process.wait()
    return return_code, "".join(lines)


def main() -> int:
    mode = str(os.getenv("AI_E2E_MODE", "live")).strip().lower() or "live"
    if mode not in {"live", "record", "replay", "provider"}:
        mode = "live"
        os.environ["AI_E2E_MODE"] = mode
    suite = _resolve_suite(mode)

    _print("Running AI E2E suite...")
    _print(f"AI_E2E_MODE={mode}")
    _print(f"AI_E2E_SUITE={suite}")

    # Load .env file from backend directory
    load_dotenv(_backend_root() / ".env")

    _validate_env(mode)
    _print("Environment validated")

    _bootstrap_data()

    backend_root = _backend_root()
    trace_dir = backend_root / "tests" / "ai_e2e" / "traces"
    record_dir = backend_root / "tests" / "ai_e2e" / "llm_recordings"
    trace_dir.mkdir(parents=True, exist_ok=True)
    record_dir.mkdir(parents=True, exist_ok=True)
    existing_trace_names = {path.name for path in trace_dir.glob("*.json")}

    cmd = _build_pytest_cmd(suite)
    _print("Running conversation scenarios...")
    return_code, combined_output = _run_pytest_streaming(
        cmd=cmd,
        cwd=backend_root,
        env=os.environ.copy(),
    )

    summary = _parse_summary(combined_output)
    trace_files = list(trace_dir.glob("*.json"))
    recording_files = list(record_dir.glob("*.json"))
    new_trace_files = [path for path in trace_files if path.name not in existing_trace_names]
    provider_stats = _collect_provider_stats(new_trace_files)

    _print("Summary:")
    _print(f"tests executed: {summary['passed'] + summary['failed'] + summary['errors'] + summary['skipped']}")
    _print(f"tests passed: {summary['passed']}")
    _print(f"tests failed: {summary['failed']}")
    _print(f"tests errored: {summary['errors']}")
    _print(f"tests skipped: {summary['skipped']}")
    _print(f"database mutations verified: {'yes' if return_code == 0 else 'partial'}")
    _print(f"LLM traces saved: {len(trace_files)}")
    _print(f"LLM recordings saved: {len(recording_files)}")
    _print(f"provider-proof traces (new): {provider_stats['interactions_with_provider_data']}")
    _print(f"provider calls attempted (new): {provider_stats['calls_attempted']}")
    _print(f"provider calls succeeded (new): {provider_stats['calls_succeeded']}")
    _print(f"provider calls failed (new): {provider_stats['calls_failed']}")

    tests_executed = summary["passed"] + summary["failed"] + summary["errors"]
    if suite == "provider" and tests_executed > 0 and provider_stats["calls_succeeded"] == 0:
        _print("Provider suite failed strict validation: no successful provider calls were recorded")
        return_code = 1

    if return_code == 0:
        _print("AI E2E run completed successfully")
    else:
        _print("AI E2E run completed with failures")

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())

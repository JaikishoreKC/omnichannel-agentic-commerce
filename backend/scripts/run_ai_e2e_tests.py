from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


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
    summary = {"passed": 0, "failed": 0, "skipped": 0}
    # Example: "206 passed, 8 skipped in 41.70s"
    m = re.search(r"(?P<passed>\d+) passed(?:, (?P<failed>\d+) failed)?(?:, (?P<skipped>\d+) skipped)?", output)
    if m:
        summary["passed"] = int(m.group("passed") or 0)
        summary["failed"] = int(m.group("failed") or 0)
        summary["skipped"] = int(m.group("skipped") or 0)
    return summary


def main() -> int:
    mode = str(os.getenv("AI_E2E_MODE", "live")).strip().lower() or "live"
    if mode not in {"live", "record", "replay"}:
        mode = "live"
        os.environ["AI_E2E_MODE"] = mode

    _print("Running AI E2E suite...")
    _print(f"AI_E2E_MODE={mode}")

    _validate_env(mode)
    _print("Environment validated")

    _bootstrap_data()

    backend_root = _backend_root()
    trace_dir = backend_root / "tests" / "ai_e2e" / "traces"
    record_dir = backend_root / "tests" / "ai_e2e" / "llm_recordings"
    trace_dir.mkdir(parents=True, exist_ok=True)
    record_dir.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "pytest", "tests/ai_e2e", "-s"]
    _print("Running conversation scenarios...")
    proc = subprocess.run(
        cmd,
        cwd=str(backend_root),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    # Stream captured output after completion so logs are preserved in CI.
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)

    summary = _parse_summary((proc.stdout or "") + "\n" + (proc.stderr or ""))
    trace_files = list(trace_dir.glob("*.json"))
    recording_files = list(record_dir.glob("*.json"))

    _print("Summary:")
    _print(f"tests executed: {summary['passed'] + summary['failed'] + summary['skipped']}")
    _print(f"tests passed: {summary['passed']}")
    _print(f"tests failed: {summary['failed']}")
    _print(f"tests skipped: {summary['skipped']}")
    _print(f"database mutations verified: {'yes' if proc.returncode == 0 else 'partial'}")
    _print(f"LLM traces saved: {len(trace_files)}")
    _print(f"LLM recordings saved: {len(recording_files)}")

    if proc.returncode == 0:
        _print("AI E2E run completed successfully")
    else:
        _print("AI E2E run completed with failures")

    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())

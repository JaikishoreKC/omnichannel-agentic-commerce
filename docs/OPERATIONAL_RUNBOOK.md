# Operational Runbook

Last updated: 2026-03-07

## 1) Preflight Before Deployment

Run from `backend/`:

```bash
python -m app.scripts.validate_config --strict
```

Expected behavior:
- Exit code `0`: configuration is release-safe.
- Exit code `1`: at least one required setting is unsafe or missing.

Common preflight failures:
- `TOKEN_SECRET` still default placeholder.
- `LLM_ENABLED=true` without `OPENROUTER_API_KEY_PLANNER` and `OPENROUTER_API_KEY_GENERAL`.
- `SUPERU_ENABLED=true` missing SuperU keys/identifiers.
- `VOICE_RECOVERY_SCHEDULER_ENABLED=true` while `SUPERU_ENABLED=false`.

## 2) Mongo Index + Bootstrap Sequence

Run from `backend/` in this order:

```bash
python -m app.scripts.create_indexes
python -m app.scripts.bootstrap_db --seed-runtime-state
```

Notes:
- Both scripts include Mongo retry behavior for startup races.
- Index creation is intended to be idempotent.
- Bootstrap seeds baseline entities for local/staging validation.

## 3) Local Recovery Reset (Staging-Like Repro)

From repo root:

```bash
docker compose down
docker compose up -d --build
```

Then from `backend/`:

```bash
python -m app.scripts.create_indexes
python -m app.scripts.bootstrap_db --seed-runtime-state
```

Verification checks:
- `GET /health` returns `200`.
- `GET /metrics` is scrapeable.
- Admin login and dashboard load succeed.

## 4) Fallback Mode (LLM Disabled)

Set:
- `LLM_ENABLED=false`

Operational impact:
- No OpenRouter calls are attempted.
- Orchestrator continues with rule-based/heuristic behavior.
- Chat remains available but with reduced model-driven quality.

Use cases:
- Provider outage mitigation.
- Cost control mode.
- Incident isolation while preserving core commerce flows.

## 5) Secret Rotation

### App token secret
1. Set new `TOKEN_SECRET` value.
2. Restart backend deployment.
3. Validate login/refresh flows.

### OpenRouter keys
1. Update `OPENROUTER_API_KEY_PLANNER` and `OPENROUTER_API_KEY_GENERAL`.
2. Restart backend deployment.
3. Verify `/health` and a chat interaction that exercises planner + general paths.

### SuperU credentials
1. Update `SUPERU_API_KEY`, `SUPERU_ASSISTANT_ID`, `SUPERU_FROM_PHONE_NUMBER`, `SUPERU_WEBHOOK_SECRET`.
2. Run preflight script.
3. Restart backend deployment.
4. Verify voice webhook and admin voice pages.

## 6) Release Gate Commands

From repo root:

```bash
python -m pytest backend/tests -q
python -m pytest backend/tests -q --cov=app --cov-fail-under=80
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

From `backend/`:

```bash
python -m app.scripts.validate_config --strict
```

## 7) Incident Triage Quick Checks

1. Check `GET /health` and `GET /metrics` first.
2. If auth failures spike, validate `TOKEN_SECRET` consistency across instances.
3. If chat quality degrades, check LLM circuit-breaker state and key validity.
4. If admin data appears stale, validate Mongo connectivity and index/bootstrap status.
5. If voice operations fail, verify SuperU settings and webhook secret alignment.

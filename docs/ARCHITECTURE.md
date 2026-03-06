# Architecture (Consolidated)

Date: 2026-03-07
Status: Canonical architecture reference for current and target-state structure.

## Purpose

This document consolidates the previous architecture baseline and migration-structure notes into one source of truth.

## Current Runtime Architecture

### Scope

Implemented in current web app:
- Responsive React + Vite + Tailwind client
- FastAPI backend with REST and WebSocket APIs
- Guest browsing/cart + authenticated checkout gate
- Session/cart continuity and memory-aware conversational flows
- Admin APIs for catalog/inventory/support/voice
- SuperU voice-recovery orchestration with guardrails

Deferred:
- Native mobile/kiosk shells
- Production payment processor integration
- Compliance/regulatory workflows

### Layered View

1. Client Interface Layer
   - `frontend/src/*`
2. Interface/API Layer
   - `backend/app/api/routes/*`, `backend/app/api/deps.py`, `backend/app/middleware/*`
3. Orchestration/Application Layer
   - `backend/app/orchestrator/*` and `backend/app/application/*`
4. Domain Services Layer
   - `backend/app/services/*`
5. Data Access Layer
   - `backend/app/repositories/*`
6. Infrastructure Layer
   - `backend/app/infrastructure/*`
7. State Layer
   - `backend/app/store/in_memory.py` + optional Mongo/Redis

### Core Flow

1. Client sends REST or WebSocket request.
2. API/deps resolve identity + session context.
3. Middleware enforces hardening/rate limits/metrics.
4. Orchestrator classifies intent (rule-first, optional LLM).
5. Actions are extracted and routed to domain agents.
6. Services/repositories execute business logic and persistence.
7. Interaction and session state are updated; authenticated memory updates async.

## Target Architecture Boundary Rules

Allowed direction:
- `api -> application -> services -> repositories -> infrastructure`
- `orchestrator -> agents/services`

Disallowed direction:
- `api/routes -> container` direct imports
- `api/routes -> repositories` direct imports
- `services -> api`

## Target Package Layout

```text
backend/app/
  api/
    deps.py
    routes/
  application/
    __init__.py
    session_workflows.py
    interaction_workflows.py
  services/
  repositories/
  infrastructure/
  orchestrator/
  agents/
```

## Migration Sequence

1. Keep provider functions in `api/deps.py` as route/middleware dependency boundary.
2. Keep API workflow glue in `application/*` (not in route handlers).
3. Continue reducing direct container coupling in transport layers.
4. Enforce import boundaries via architecture guard tests.
5. Continue frontend page decomposition into feature hooks/components.

## Security/Resilience/Observability Highlights

- JWT auth + role checks on admin endpoints
- Request hardening, per-tier rate limiting, WS origin checks
- Authenticated rate limiting keyed by stable user identity (token digest fallback for invalid bearer values)
- Inventory reservation/commit/rollback serialization in `InventoryService` to prevent in-process oversell races
- Same-idempotency-key order creation serialization in `OrderService` to avoid duplicate in-process checkout execution
- SuperU callback signature verification
- LLM fallback with circuit breaker
- Optional per-intent confidence floors for classifier/planner selection via settings override
- Orchestrator decision telemetry for intent source/confidence buckets, planner step failures/skips, and action truncation
- `/health` and `/metrics` for runtime visibility

## Notes

- This document supersedes the prior standalone baseline architecture text file.
- Detailed runtime intelligence and recent architectural deltas remain in `docs/REPOSITORY_INTELLIGENCE.md`.

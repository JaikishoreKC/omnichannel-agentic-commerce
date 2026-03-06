# Product and Delivery Spec (Consolidated)

Date: 2026-03-07
Status: Canonical merged product/spec/blueprint document.

## Purpose

This document consolidates prior product intent and execution docs into one implementation-aligned reference.

## Product Statement

Build an agentic commerce platform for persistent omnichannel conversational sales and autonomous retail task orchestration.

Current release is a responsive web implementation sharing backend contracts intended for future channels.

## Problem Statement

Traditional ecommerce creates friction:
- Multi-page flows for simple tasks
- Context loss across sessions/channels
- Fragmented support and order operations
- High cart abandonment with inconsistent recovery

## Users

- Guest shoppers: browse and build cart before account creation
- Registered shoppers: continue context and checkout efficiently
- Returning shoppers: memory-aware recommendations and assistance
- Admin/operations users: manage catalog, inventory, support, voice controls

## Scope

In scope (v1):
- Responsive web app
- Catalog browse + product detail
- Guest session/cart + guest->auth merge
- Auth-required order creation with idempotency
- Conversational assistant (REST + WS) across product/cart/order/support/memory intents
- Preference memory and history-aware responses
- Admin management endpoints and dashboard flows
- SuperU voice-recovery orchestration and callbacks

Out of scope (v1):
- Native mobile and kiosk shells
- Real payment processor integration
- Compliance/regulatory workflows

## Functional Requirements Summary

- FR-1 Guest shopping: implemented
- FR-2 Authentication and transition: implemented
- FR-3 Checkout gate: implemented
- FR-4 Conversational orchestration: implemented
- FR-5 Preference memory: implemented
- FR-6 Product detail UX: implemented
- FR-7 Voice recovery for abandoned carts: implemented (provider-config dependent)

## Non-Functional Targets

- API latency p95: < 500ms
- LLM latency p95 (enabled mode): < 3s
- WebSocket delivery latency: < 200ms
- DB query latency p95: < 100ms
- Availability target: 99.9%

## Security and Operations Requirements

- JWT auth + refresh rotation
- Role-based admin access
- Request hardening + rate limiting
- WebSocket origin validation
- Prometheus metrics + health checks
- Admin activity integrity verification
- In-process reliability hardening for checkout/inventory race windows

## Recently Delivered Reliability Hardening (2026-03-07)

- Inventory reservation and inventory mutation paths are serialized in-process to reduce oversell races.
- Order creation is serialized per `(user, Idempotency-Key)` in-process to reduce duplicate concurrent checkout execution.
- Rate limiting now prefers validated user-id subjects for authenticated requests (with token-digest fallback for invalid bearer tokens).

## Runtime Blueprint

### Backend
- `backend/app/api/routes/*`: transport handlers
- `backend/app/orchestrator/*`: intent/context/action/router pipeline
- `backend/app/agents/*`: domain execution
- `backend/app/services/*`: business policy
- `backend/app/repositories/*`: data access
- `backend/app/infrastructure/*`: integrations/resilience/observability
- `backend/app/scripts/*`: index/bootstrap/perf smoke scripts

### Frontend
- `frontend/src/App.tsx`: routing/shell composition
- `frontend/src/api/*`: HTTP/WS wrappers
- `frontend/src/context/*`: auth/session/cart/chat/theme state
- `frontend/src/pages/*`: customer and admin views
- `frontend/tests/e2e/*`: Playwright user journeys

## Build and Run Sequence

1. Backend
   - `cd backend`
   - create/activate venv
   - `pip install -r requirements.txt`
   - `python -m uvicorn app.main:app --reload --port 8000`
2. Frontend
   - `cd frontend`
   - `npm install`
   - `npm run dev`
3. Optional external persistence bootstrap
   - `python -m app.scripts.create_indexes`
   - `python -m app.scripts.bootstrap_db`
4. Optional full-stack runtime
   - `docker compose up --build`

## Validation Gates

- Backend: `pytest tests -q --cov=app --cov-fail-under=80`
- Frontend: `npm run lint`, `npm run build`, `npm run test:e2e`
- Local end-to-end validation: `scripts/validate_local.ps1`

## Post-v1 Priorities

1. Native mobile shell using current API/WS contracts
2. Native kiosk shell using shared orchestration backend
3. External payment processor and reconciliation
4. Compliance and regulatory controls

## Notes

- This document supersedes and consolidates previous idea/PRD/SDD/implementation blueprint text documents.
- Detailed ongoing technical deltas are tracked in `docs/REPOSITORY_INTELLIGENCE.md`.

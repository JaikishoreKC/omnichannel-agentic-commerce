# Repository Intelligence Report

Generated: 2026-03-05
Scope: `omnichannel-agentic-commerce` (branch `main`)
Purpose: durable “repository brain” for safe future development.

## 1) Repository Map

### Root Structure
- `backend/`: FastAPI application, orchestration, agents, services, repositories, tests
- `frontend/`: React + Vite SPA, API client modules, contexts, pages, e2e tests
- `docs/`: architecture, contracts, PRD/SDD/security/testing documentation
- `monitoring/`: Prometheus config and Grafana provisioning/dashboards
- `.github/workflows/`: CI pipeline
- `scripts/`: local validation tooling
- `docker-compose.yml`: local multi-service runtime (backend/frontend/mongo/redis/prometheus/grafana)

### Backend Structure (`backend/app`)
- `main.py`: app startup, middleware registration, routes, health/metrics, websocket
- `container.py`: DI/composition root for all services/repos/agents/orchestrator
- `api/routes/`: REST endpoints and webhook entrypoints
- `orchestrator/`: intent → action → route → execute pipeline
- `agents/`: product/cart/order/support/memory/general executors
- `services/`: business logic and policy enforcement
- `repositories/`: persistence adapters (Mongo/Redis + in-memory mirrors)
- `infrastructure/`: LLM client, SuperU client, rate limiter, metrics, persistence clients
- `middleware/`: request hardening, rate limits, security headers, metrics
- `models/schemas.py`: request/response DTOs
- `store/in_memory.py`: seed data + in-process state model

### Frontend Structure (`frontend/src`)
- `main.tsx`: provider stack and app bootstrap
- `App.tsx`: route graph (customer shell + admin routes)
- `api/`: HTTP/WebSocket transport and domain API wrappers
- `context/`: auth/session/cart/chat/theme/toast global state
- `pages/`: customer and admin screens
- `components/`: UI primitives, layout, feature modules
- `types.ts`: frontend domain contract types

### Test/Quality Structure
- Backend: `backend/tests/unit`, `backend/tests/integration`, `backend/tests/nl_eval`
- Frontend: `frontend/tests/e2e/p0-shopping-flows.spec.ts`
- CI: backend tests + coverage, NL eval, security scans, frontend build + e2e

---

## 2) System Architecture

## High-Level Layers
1. **Client Layer**: React app (customer + admin experiences)
2. **Transport Layer**: REST (`/v1/*`) + WebSocket (`/ws`)
3. **API Layer**: route handlers + dependency resolution
4. **Cross-Cutting Middleware**: hardening, rate limiting, security headers, metrics
5. **Orchestrator Layer**: intent classification, context build, action extraction, agent routing, response formatting
6. **Agent Layer**: domain-specific action execution
7. **Service Layer**: business rules and workflows
8. **Repository Layer**: Mongo/Redis access patterns + caching behavior
9. **Infrastructure Layer**: LLM provider, voice provider, observability, circuit breaker, limiter

## Interaction Model
- Rule-first NLU always runs first.
- Optional LLM planning/classification can be enabled by policy and canary settings.
- Session/cart/memory context is assembled before action execution.
- Interactions are persisted and session conversation state is updated after each message.

---

## 3) Module Responsibility Map

## Core Runtime Modules
- **`backend/app/main.py`**
  - Initializes FastAPI app and lifecycle
  - Connects external clients at startup
  - Registers middlewares and route modules
  - Hosts `/health`, `/metrics`, and `/ws`

- **`backend/app/container.py`**
  - Wires settings, stores, managers, repositories, services, agents, orchestrator
  - Central dependency hub (high coupling hotspot)

- **`backend/app/orchestrator/*`**
  - `intent_classifier.py`: rule-based classification with optional LLM override
  - `action_extractor.py`: maps intents to executable actions
  - `agent_router.py`: maps intent/action to agent
  - `context_builder.py`: builds session/cart/memory context
  - `orchestrator_core.py`: end-to-end orchestration and streaming pipeline

- **`backend/app/agents/*`**
  - `product_agent.py`: product search/recommendation + preference-aware ranking
  - `cart_agent.py`: add/update/remove/discount/clear cart actions
  - `order_agent.py`: checkout summary, status, cancel/refund/address updates
  - `support_agent.py`: support ticket lifecycle and FAQ-like handling
  - `memory_agent.py`: memory show/save/forget/clear flows
  - `general_agent.py`: LLM-backed generic answers

- **`backend/app/services/*`**
  - Auth/session/cart/order/memory/interaction/support/admin/inventory/product logic
  - `voice_recovery_service.py`: abandoned-cart voice campaign workflow

- **`backend/app/repositories/*`**
  - Persistence abstraction by domain (auth, cart, product, memory, orders, voice, etc.)
  - Predominantly Mongo source + Redis cache patterns

## Frontend Modules
- **`frontend/src/api/client.ts`**
  - Auth/session token storage, request wrapper, silent refresh/retry, websocket connector
- **`frontend/src/context/*`**
  - Session bootstrap, auth lifecycle, cart sync, websocket chat lifecycle
- **`frontend/src/pages/*`**
  - Customer flows (home/products/detail/cart/account/auth)
  - Admin flows (login/dashboard)

---

## 4) System Flows

## A. User Request Flow (REST)
1. Client calls `/v1/...` via `request()` in frontend API client.
2. API deps resolve auth user + session context (`Authorization`, `X-Session-Id`, cookie fallback).
3. Middleware enforces hardening/rate/security and records metrics.
4. Route delegates to service layer.
5. Service executes business rules and repository operations.
6. Response returned in normalized shape (error envelope standardized by handlers).

## B. Conversational AI Flow (REST/WS)
1. Message received (`/v1/interactions/message` or `/ws`).
2. Session resolved (guest or authenticated continuity).
3. Orchestrator classifies intent (rules first; optional LLM path).
4. Context built from session + cart + memory + recent interactions.
5. Actions extracted and routed to target agent(s).
6. Agent(s) execute via services and repositories.
7. Response formatted and streamed/finalized.
8. Interaction persisted; session conversation updated; async memory recording (if authenticated).

## C. Guest → Auth Continuity Flow
1. Guest creates session/cart.
2. On login/register, guest cart merged into user cart by `productId + variantId`.
3. User session resolved or upgraded and linked to identity metadata.
4. Subsequent history/memory/cart retrieval uses authenticated context.

## D. Checkout Flow
1. Authenticated user calls `POST /v1/orders` with `Idempotency-Key`.
2. Order service validates idempotency and non-empty cart.
3. Inventory reserved, payment authorized (stub), order persisted.
4. Cart marked converted; inventory committed; notification emitted.

## E. Voice Recovery Flow
1. Scheduler/admin trigger scans abandoned carts and enqueues jobs.
2. Guardrails enforce quiet hours/caps/budget/suppressions.
3. SuperU outbound call attempted (if configured).
4. Callback webhook verifies signature/timestamp and updates call/job state.
5. Alerts/stats and follow-up actions updated.

---

## 5) Dependency Analysis

## High-Coupling Areas
- **`container.py` as service locator** is imported directly by routes/middleware.
- **`orchestrator_core.py`** depends on multiple cross-domain services/agents.
- **`voice_recovery_service.py` + `services/voice/*`** are broad integration points.

## Shared Foundations
- `core/config.py`: all runtime toggles and limits
- `core/security.py`: token + hashing primitives
- `core/utils.py`: id/time/id-generation utility functions
- `infrastructure/observability.py`: metric counters/histograms

## Critical Integration Points
- Auth/session consistency across REST and WS paths
- Cart merge and order idempotency behavior
- LLM decision policy/canary logic
- Webhook verification path for SuperU callbacks

---

## 6) Documentation Alignment (Docs vs Implementation)

## Strong Alignment
- Layered architecture in docs matches implementation modules.
- Session/cart continuity and auth-gated checkout are implemented.
- Voice recovery subsystem exists with guardrails and callbacks.
- Metrics and health endpoints match stated observability model.

## Notable Drift / Mismatches
1. **LLM provider docs vs runtime config**
   - Docs emphasize OpenAI/Anthropic dual mode.
   - Runtime currently centers OpenRouter fields in config/client paths.

2. **Admin MFA doc wording vs implementation**
   - Security doc references static code semantics.
   - Auth service uses TOTP secret validation path (with fallback behavior).

3. **Frontend memory API contract mismatch**
   - Frontend `api/memory.ts` expects shapes/endpoints not matching backend memory route contracts.
   - `AiMemoryTab` currently calls `/memory` as if returning an array and deletes `/memory/{key}`, which does not match backend route definitions.

4. **Frontend admin health typing mismatch**
   - Frontend expects fields like `circuit_breaker` while backend health currently exposes `circuitBreakerState` structure.

These are key risk zones for future feature work.

---

## 7) Critical Files

## Entry Points / Composition
- `backend/app/main.py`
- `backend/app/container.py`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`

## Core Orchestration / Business
- `backend/app/orchestrator/orchestrator_core.py`
- `backend/app/services/cart_service.py`
- `backend/app/services/order_service.py`
- `backend/app/services/voice_recovery_service.py`

## Security / Transport / Contracts
- `backend/app/api/deps.py`
- `backend/app/middleware/request_hardening.py`
- `backend/app/middleware/rate_limiting.py`
- `backend/app/models/schemas.py`
- `frontend/src/api/client.ts`

## Infrastructure / Runtime Ops
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `monitoring/prometheus.yml`

---

## 8) Knowledge Synthesis (Repository Brain)

## System Architecture Summary
- Monorepo with FastAPI backend + React frontend + local observability stack.
- Backend follows layered modular design with orchestrated AI capabilities.
- Persistence is external-service-first in many repositories (Mongo/Redis), with in-memory seeds/mirrors and optional fallback behavior.

## Module Responsibilities Summary
- Routes: transport and dependency boundaries
- Orchestrator/Agents: conversational intent/action execution
- Services: domain policy and workflows
- Repositories: storage interface and cache behavior
- Frontend contexts/API modules: session/auth/chat/cart application state and backend coordination

## Key Dependencies Summary
- Container-driven dependency graph dominates backend coupling.
- Orchestrator and voice modules are most integration-dense and highest-risk for regressions.

## Core Flows Summary
- Guest/cart continuity to auth checkout
- Conversational AI request handling via REST/WS
- Idempotent order creation + inventory/payment workflow
- Abandoned-cart voice recovery with guardrails and signed callbacks

## Critical Components Summary
- `container.py`, `main.py`, `orchestrator_core.py`, `api/client.ts` are strategic files for safe future change planning.

---

## 9) Safe Development Guidance (for future tasks)

1. Trace changes through **route → service → repository** before editing.
2. Validate both REST and WS paths when touching conversation/session logic.
3. Treat `container.py` edits as high impact; verify all dependent imports.
4. Reconcile frontend API contracts with backend schemas before adding UI features.
5. For voice features, always verify guardrails + webhook signature behavior.
6. Keep docs and implementation synchronized to reduce future drift.

---

## 10) Future Update Protocol

When implementation changes materially, update this file in the same PR under:
- repository map deltas,
- module responsibility deltas,
- flow changes,
- new coupling hotspots,
- docs alignment notes.

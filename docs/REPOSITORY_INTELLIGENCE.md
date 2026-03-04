# Repository Intelligence Report

Generated: 2026-03-05
Last Updated: 2026-03-05
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
- Frontend: `frontend/tests/e2e/p0-shopping-flows.spec.ts` + API contract unit tests in `frontend/src/api/*.test.ts`
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
- **`container.py` as service locator** remains a central coupling point, now accessed for transport concerns primarily via `api/deps.py` providers (direct imports in routes/middleware removed).
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

3. **Frontend memory/admin contract drift (remediated on 2026-03-05)**
  - Memory API wrapper and `AiMemoryTab` now align with backend memory snapshot/history/delete contracts.
  - Admin health typing/UI now supports backend `circuitBreakerState` while retaining snake_case compatibility as a transitional fallback.

4. **Test-runtime dependency on local Mongo/Redis (remediated on 2026-03-05)**
  - Backend tests now fall back to in-memory `mongomock` + `fakeredis` clients when local services are unavailable.
  - This removed environment-coupled false negatives and restored deterministic suite execution.

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

---

## 11) Change Log (2026-03-05)

### Implemented
- Frontend memory contract alignment: `frontend/src/api/memory.ts` and `frontend/src/components/account/AiMemoryTab.tsx`
- Frontend admin health compatibility: `frontend/src/api/admin.ts` and `frontend/src/pages/AdminDashboard.tsx`
- Frontend unit test harness + adapter contract tests: `frontend/package.json`, `frontend/vitest.config.ts`, `frontend/src/api/admin.test.ts`, `frontend/src/api/memory.test.ts`
- Backend test determinism fallback: `backend/tests/conftest.py` with added test dependencies in `backend/requirements.txt`
- Duplicate helper removal in inventory service: `backend/app/services/inventory_service.py`

### Validation Snapshot
- Backend tests: `167 passed`
- Frontend tests: `5 passed`
- Frontend lint: `passed`
- Frontend build: `passed`

---

## 12) Change Log (2026-03-05, Performance Pass)

### Implemented
- Product semantic search artifact caching to avoid repeated TF-IDF rebuilds: `backend/app/services/product_service.py`
- Session cleanup throttling and hot-path cleanup removal: `backend/app/services/session_service.py`, `backend/app/api/deps.py`
- Voice recovery polling and lookup optimizations (bounded concurrent polling, provider-call indexed callback matching, user-scoped newer-order checks): `backend/app/services/voice_recovery_service.py`
- Async route hot-path offloading of blocking service calls (`asyncio.to_thread`) for interactions and websocket handlers: `backend/app/api/routes/interaction_routes.py`, `backend/app/api/routes/ws_route.py`
- Short-TTL cart read-path cache with write invalidation: `backend/app/services/cart_service.py`

### Validation Snapshot
- Backend tests (unit + integration): `146 passed`
- Frontend tests: `5 passed`
- Frontend lint: `passed`
- Frontend build: `passed`

### Notes
- Backend test fallback dependencies (`fakeredis`, `mongomock`) were required in the local virtual environment for deterministic execution when local Redis/Mongo are unavailable.

---

## 13) Change Log (2026-03-05, Complexity Reduction Pass)

### Implemented
- Simplified intent-to-action extraction by replacing the long conditional chain with declarative mapping and targeted special handling: `backend/app/orchestrator/action_extractor.py`
- Refactored agent execution branching into dispatch-based handlers for readability and maintainability: `backend/app/agents/cart_agent.py`, `backend/app/agents/order_agent.py`
- Introduced shared session resolution/linking workflows to reduce duplicated route logic: `backend/app/application/session_workflows.py`, reused by `backend/app/api/routes/interaction_routes.py` and `backend/app/api/routes/ws_route.py`
- Decomposed classifier rule flow into grouped intent-classification helpers to reduce nesting: `backend/app/orchestrator/intent_classifier.py`
- Decomposed orchestrator stream lifecycle into focused helper methods (recent-load, metadata application, streaming, persistence): `backend/app/orchestrator/orchestrator_core.py`
- Consolidated duplicate LLM retry-delay logic into shared helper path: `backend/app/infrastructure/llm_client.py`
- Simplified product repository update API by removing ambiguous variadic signature and aligned service callsites: `backend/app/repositories/product_repository.py`, `backend/app/services/product_service.py`
- Removed dead/duplicate code in websocket and orchestrator modules: `backend/app/api/routes/ws_route.py`, `backend/app/orchestrator/orchestrator_core.py`
- Removed obsolete API helper duplicate after application-layer extraction: `backend/app/api/session_utils.py`

### Validation Snapshot
- Backend tests (full suite): `168 passed`
- Frontend tests: `5 passed`
- Frontend lint: `passed`
- Frontend build: `passed`

---

## 14) Change Log (2026-03-05, Architecture Boundary Hardening Pass)

### Implemented
- Added explicit dependency providers in `backend/app/api/deps.py`, including `get_container()` and service/repository/provider accessors used by transport modules.
- Migrated API routes and middleware from direct composition-root imports to provider-backed dependencies: `backend/app/api/routes/*.py`, `backend/app/middleware/*.py`.
- Extracted session orchestration glue to the new application layer module: `backend/app/application/session_workflows.py`.
- Rewired interaction/websocket paths to use application workflows: `backend/app/api/routes/interaction_routes.py`, `backend/app/api/routes/ws_route.py`.
- Added boundary regression test to enforce no direct `from app.container import container` in routes/middleware: `backend/tests/unit/test_architecture_boundaries.py`.
- Added architecture target/migration blueprint doc: `docs/ARCHITECTURE_TARGET_STRUCTURE.md`.

### Validation Snapshot
- Backend tests (full suite): `168 passed`
- Frontend tests: `5 passed`
- Frontend lint: `passed`
- Frontend build: `passed`

### Notes
- `fakeredis` was installed in the backend virtual environment to satisfy test fallback dependencies during local execution.

---

## 15) Change Log (2026-03-05, Security Hardening Pass)

### Implemented
- Removed insecure admin MFA fallback (`000000`) and fail-closed when MFA dependency is unavailable: `backend/app/services/auth_service.py`.
- Reworked password reset flow to avoid token disclosure in logs and store only hashed reset tokens with expiry: `backend/app/services/auth_service.py`, `backend/app/repositories/auth_repository.py`.
- Moved refresh token persistence to hashed-at-rest storage with legacy read/revoke compatibility paths: `backend/app/repositories/auth_repository.py`.
- Added production-like startup security validation for secrets and admin MFA defaults: `backend/app/core/config.py`, `backend/app/container.py`.
- Increased session ID entropy and added guest session mismatch checks for interactions/websocket paths: `backend/app/services/session_service.py`, `backend/app/api/routes/interaction_routes.py`, `backend/app/api/routes/ws_route.py`.
- Tightened transport defaults and reduced sensitive operational exposure in health/logging: `backend/app/main.py`, `backend/app/infrastructure/persistence_clients.py`, `backend/app/api/routes/ws_route.py`.
- Shifted frontend auth/refresh token storage from `localStorage` to in-memory state and enabled cookie credentials for refresh flow: `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`, `backend/app/api/routes/auth_routes.py`, `backend/app/models/schemas.py`.
- Added regression tests for security validation and reset-token handling: `backend/tests/unit/test_security_hardening.py`.

### Validation Snapshot
- Backend tests (full suite): `171 passed`
- Frontend tests: `5 passed`
- Frontend lint: `passed`
- Frontend build: `passed`

### Follow-up Completion (2026-03-05)
- Completed cookie-first auth transport: access token now accepted via secure cookie in API auth dependencies and set on auth flows (`backend/app/api/deps.py`, `backend/app/api/routes/auth_routes.py`).
- Removed frontend bearer-header usage from request pipeline; auth relies on credentialed cookie transport (`frontend/src/api/client.ts`, `frontend/src/context/AuthContext.tsx`).
- Restricted detailed `/health` diagnostics to authenticated admin context and returns reduced public snapshot otherwise (`backend/app/main.py`, `frontend/src/api/admin.ts`).
- Updated affected frontend health test contract for credentialed fetch (`frontend/src/api/admin.test.ts`).

### Follow-up Validation Snapshot
- Backend tests (full suite): `171 passed`
- Frontend tests: `5 passed`
- Frontend lint: `passed`
- Frontend build: `passed`

### Final Follow-up Completion (2026-03-05)
- Added server-side logout endpoint that revokes refresh tokens from cookie context and clears both access/refresh cookies: `backend/app/api/routes/auth_routes.py`.
- Wired frontend logout to call backend logout before navigation and clear local auth/session state: `frontend/src/api/auth.ts`, `frontend/src/context/AuthContext.tsx`, `frontend/src/pages/AdminDashboard.tsx`, `frontend/src/pages/AccountPage.tsx`.
- Added integration coverage for logout revocation and cookie clearing behavior: `backend/tests/integration/test_auth_refresh_rotation.py`.

### Final Validation Snapshot
- Backend tests (full suite): `172 passed`
- Frontend tests: `5 passed`
- Frontend lint: `passed`
- Frontend build: `passed`

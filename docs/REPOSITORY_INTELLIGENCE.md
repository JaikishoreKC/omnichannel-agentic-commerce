# Repository Intelligence Report

Date: 2026-03-07  
Scope: Full repository mental model for safe future development.

Update note (2026-03-07):
- Added in-process hardening for inventory reservation/mutation races and order idempotency concurrency.
- Updated authenticated rate-limit keying to use stable user identity with invalid-token fallback.
- Backend validation status: `241 passed, 11 skipped`.

## REPOSITORY MAP

### Root

- `README.md`: project overview, quickstart, runtime behavior, feature matrix.
- `docker-compose.yml`: local stack orchestration (backend, frontend, mongo, redis, prometheus, grafana).
- `scripts/validate_local.ps1`: local quality gate runner.
- `monitoring/`: Prometheus/Grafana config and dashboards.
- `docs/`: architecture/spec/security/testing/release documents.

### Backend (`backend/`)

- `app/main.py`: FastAPI entrypoint, middleware, route registration, health/metrics, websocket endpoint, lifespan startup/shutdown.
- `app/container.py`: central composition root for managers, repositories, services, agents, orchestrator.
- `app/core/`: config, security, utility primitives.
- `app/api/routes/`: transport endpoints for auth, products, cart, orders, sessions, interactions, memory, support, admin, voice callback.
- `app/application/`: cross-service use-case workflows (session/user/cart linking).
- `app/orchestrator/`: intent classifier, action extractor, router, context builder, formatter, orchestration core.
- `app/agents/`: specialized agents (product/cart/order/support/memory/general).
- `app/services/`: business logic layer.
- `app/repositories/`: persistence abstractions over Mongo/Redis/in-memory.
- `app/infrastructure/`: LLM client, circuit breaker, observability, persistence clients, rate limiter, index management, state persistence, SuperU client.
- `app/middleware/`: rate limiting, hardening, security headers, metrics.
- `app/models/schemas.py`: API request/response contracts.
- `app/store/in_memory.py`: in-process state baseline/fallback.
- `app/scripts/`: DB bootstrap/index/perf scripts.
- `tests/`: unit, integration, AI E2E, natural-language evaluation suites.

### Frontend (`frontend/`)

- `src/main.tsx`: provider stack bootstrap and router mount.
- `src/App.tsx`: route tree, admin/customer separation, profile-completion guard.
- `src/api/`: HTTP/WS clients and domain API modules.
- `src/context/`: Session/Auth/Cart/Chat/Theme/Toast state domains.
- `src/pages/`: customer and admin pages.
- `src/components/`: UI kit, layout, feature components.
- `tests/e2e/`: Playwright end-to-end journeys.

### Monitoring

- `monitoring/prometheus.yml`: backend metrics scrape target.
- `monitoring/grafana/provisioning/*`, `monitoring/grafana/dashboards/*`: dashboard provisioning.

## SYSTEM ARCHITECTURE

### Architectural Style

- Layered backend modular monolith with explicit DI composition.
- SPA frontend (React/Vite) with provider-based state architecture.
- Optional external persistence/services with resilient local fallback paths.

### Backend Layers and Interactions

1. Interface/API layer: route handlers in `backend/app/api/routes/*`.
2. Middleware controls: request hardening, rate limiting, security headers, metrics.
3. Application workflows: cross-cutting use-case glue in `backend/app/application/*`.
4. Orchestration layer: classify intent, build context, extract actions, route agents.
5. Domain services: cart/order/auth/memory/support/admin policies.
6. Repositories: persistence + cache adapters.
7. Infrastructure: external clients/resilience/observability.
8. State layer: Mongo + Redis + in-memory baseline/fallback.

Dependency direction (as intended and mostly implemented):

- `api -> application -> services -> repositories -> infrastructure`
- `orchestrator -> agents/services`

### Frontend Layers and Interactions

1. App shell/router.
2. Context providers for session/auth/cart/chat.
3. API client boundary for HTTP/WS.
4. Page components and feature widgets.

Provider order in `frontend/src/main.tsx`:

- `SessionProvider -> AuthProvider -> CartProvider -> ChatProvider`.

## MODULE RESPONSIBILITY MAP

### Module: API Transport

- Responsibility: validate/shape requests, dependency resolution, HTTP/WS contracts.
- Key files: `backend/app/api/routes/*.py`, `backend/app/api/deps.py`.
- Depends on: services, orchestrator, application workflows.
- Interacts with: middleware, frontend API clients.

### Module: Application Workflows

- Responsibility: session creation/resolution and user identity linking workflow.
- Key file: `backend/app/application/session_workflows.py`.
- Depends on: session/cart/auth services.
- Interacts with: auth routes, interaction routes, websocket route.

### Module: Orchestrator

- Responsibility: end-to-end AI interaction execution pipeline.
- Key files: `backend/app/orchestrator/orchestrator_core.py`, `backend/app/orchestrator/intent_classifier.py`, `backend/app/orchestrator/action_extractor.py`.
- Depends on: agents, LLM client, interaction service, memory service.
- Interacts with: interaction REST + websocket endpoints.

### Module: Agents

- Responsibility: action execution adapters for domains.
- Key files: `backend/app/agents/cart_agent.py`, `backend/app/agents/product_agent.py`, `backend/app/agents/order_agent.py`, `backend/app/agents/support_agent.py`, `backend/app/agents/memory_agent.py`, `backend/app/agents/general_agent.py`.
- Depends on: domain services.
- Interacts with: orchestrator.

### Module: Services

- Responsibility: business rules and workflow-internal validation.
- Key files: `backend/app/services/auth_service.py`, `backend/app/services/cart_service.py`, `backend/app/services/order_service.py`, `backend/app/services/memory_service.py`, `backend/app/services/voice_recovery_service.py`, `backend/app/services/admin_service.py`.
- Depends on: repositories, utility/core components.
- Interacts with: routes, agents, orchestrator.

### Module: Repositories

- Responsibility: CRUD/query access with Mongo primary, Redis cache, optional in-memory mirror/fallback.
- Key files: `backend/app/repositories/auth_repository.py`, `backend/app/repositories/cart_repository.py`, `backend/app/repositories/product_repository.py`.
- Depends on: persistence client managers.
- Interacts with: services.

### Module: Infrastructure

- Responsibility: external IO and cross-cutting runtime mechanisms.
- Key files: `backend/app/infrastructure/llm_client.py`, `backend/app/infrastructure/superu_client.py`, `backend/app/infrastructure/persistence_clients.py`, `backend/app/infrastructure/observability.py`, `backend/app/infrastructure/mongo_indexes.py`.
- Depends on: config and third-party libraries.
- Interacts with: services, orchestrator, container.

### Module: Frontend API + Context

- Responsibility: server communication boundary and user/session/cart/chat state.
- Key files: `frontend/src/api/client.ts`, `frontend/src/context/AuthContext.tsx`, `frontend/src/context/SessionContext.tsx`, `frontend/src/context/CartContext.tsx`, `frontend/src/context/ChatContext.tsx`.
- Depends on: backend API contracts.
- Interacts with: page/components.

## SYSTEM FLOWS

### 1) API Request Flow

1. Request reaches FastAPI in `backend/app/main.py`.
2. Middleware enforces hardening, limits, headers, metrics.
3. Route resolves user/session via deps.
4. Route calls service or orchestrator.
5. Service uses repositories (Mongo/Redis/in-memory path).
6. Response emitted with standardized error format if needed.

### 2) Conversational AI Flow (REST/WS)

1. Message enters `/v1/interactions/message` or `/ws`.
2. Session ensured, user identity resolved and cart continuity applied.
3. Orchestrator classifies intent (rules first; optional LLM override).
4. Context builder injects session/cart/preferences/history.
5. Action extractor + router select agent execution path.
6. Optional planner creates multi-step plan with safety gates.
7. Agent(s) execute domain actions.
8. Interaction is persisted; memory is asynchronously recorded for authenticated users.
9. WS optionally emits stream events before final response envelope.

### 3) Auth + Continuity Flow

1. `register/login` returns access/refresh tokens and session id.
2. Guest cart merged into user cart when session exists.
3. User session resolved/linked and identity metadata updated.
4. Frontend stores session id and uses it for HTTP/WS continuity.

### 4) Checkout Flow

1. Authenticated user calls `POST /v1/orders` with `Idempotency-Key`.
2. Order service validates key, checks idempotency mapping.
3. Cart loaded, inventory reserved, payment authorized (stub).
4. Order persisted; cart marked converted; notification attempted.
5. Duplicate idempotent retries return prior successful order.

### 5) Voice Recovery Flow

1. Scheduler tick invokes `voice_recovery_service.process_due_work`.
2. Abandoned-cart jobs are enqueued and processed.
3. SuperU outbound calls are started; provider state is polled.
4. Signed callbacks (`/v1/voice/superu/callback`) update terminal state idempotently.
5. Admin APIs manage settings/process/suppressions/alerts/stats.

## DEPENDENCY ANALYSIS

### Tightly Coupled Components

- `backend/app/container.py`: central fan-in/fan-out dependency hub.
- Orchestrator <-> agent action contract (`action` names/params).
- Frontend chat state and websocket protocol coupling.

### Shared Utilities and Cross-Cutting Components

- `backend/app/core/config.py`: global feature/security behavior.
- `backend/app/api/deps.py`: API dependency boundary.
- `backend/app/infrastructure/observability.py`: metrics collector used by middleware and runtime handlers.
- `frontend/src/api/client.ts`: transport/session/auth behavior shared by all frontend API modules.

### Critical Integration Points

- Session and cart continuity (`auth_routes`, `session_workflows`, `cart_service`).
- LLM planning/classification via `llm_client` with circuit breaker/retries.
- SuperU voice callback signature verification and idempotent event ingestion.
- Mongo index migration/repair logic in `mongo_indexes.py`.

### Modules With Many Dependencies

- `backend/app/container.py`.
- `backend/app/orchestrator/orchestrator_core.py`.
- `backend/app/services/voice_recovery_service.py`.
- `backend/app/api/routes/admin_routes.py`.

## DOCS ALIGNMENT

### Aligned

- `docs/ARCHITECTURE.md`: matches implemented layered design and migration targets.
- `docs/API_Contracts.md`: endpoint surface largely reflects route implementations.
- `docs/PRODUCT_AND_DELIVERY_SPEC.md`: scope and delivery status align with runtime capabilities.
- `docs/RELEASE_CHECKLIST.md`: aligns with available scripts/endpoints.

### Partial Gaps / Drift

- `docs/Database_Schema.md` is broader than runtime shape in places; implementation details are repository-specific and somewhat leaner.

### Missing Documentation Content

- This file (`docs/REPOSITORY_INTELLIGENCE.md`) was previously empty and is now populated.

## CRITICAL FILES

### Application Entry and Composition

- `backend/app/main.py`: runtime boot, middleware stack, health/metrics/ws, exception policy.
- `backend/app/container.py`: complete object graph wiring.
- `backend/app/core/config.py`: operational feature flags and security/runtime defaults.

### Orchestration and Intelligence

- `backend/app/orchestrator/orchestrator_core.py`: central conversational execution logic.
- `backend/app/orchestrator/intent_classifier.py`: intent quality and downstream routing correctness.

### Core Commerce Logic

- `backend/app/services/cart_service.py`: cart lifecycle, merge, pricing/totals.
- `backend/app/services/order_service.py`: checkout transaction flow and idempotency.
- `backend/app/services/memory_service.py`: preference memory and interaction history summarization.

### External Integrations and Guardrails

- `backend/app/infrastructure/llm_client.py`: LLM calls, retry policy, planner sanitization, streaming.
- `backend/app/infrastructure/superu_client.py`: voice provider outbound calls + webhook signature verification.
- `backend/app/infrastructure/mongo_indexes.py`: index creation/repair safety.

### Frontend Runtime Integration

- `frontend/src/api/client.ts`: session persistence, token lifecycle, HTTP/WS contract parsing.
- `frontend/src/context/ChatContext.tsx`: websocket lifecycle, stream assembly, chat event side effects.
- `frontend/src/App.tsx`: route gates and app-level navigation policy.

## KNOWLEDGE SYNTHESIS

### SYSTEM ARCHITECTURE

- Layered backend with orchestrator-centric conversational domain and explicit DI composition.
- Provider-driven frontend state architecture tightly integrated with session-aware backend contracts.

### MODULE RESPONSIBILITIES

- API handles transport/dependencies.
- Application workflows handle cross-service user/session/cart linkage.
- Orchestrator/agents handle natural-language intent execution.
- Services enforce domain business rules.
- Repositories encapsulate persistence and fallback behavior.

### KEY DEPENDENCIES

- Config-driven feature toggles.
- Orchestrator action contracts.
- Session continuity and cart merge pathways.
- LLM and SuperU external integrations.

### CORE FLOWS

- Request lifecycle through middleware and service/orchestrator execution.
- Conversational flow with classification/planning/agent execution.
- Checkout idempotency and inventory/payment orchestration.
- Voice recovery scheduling and callback ingestion.

### CRITICAL COMPONENTS

- `main.py`, `container.py`, orchestrator core, auth/cart/order services, and frontend API/context integration files are highest-impact for system correctness and change risk.


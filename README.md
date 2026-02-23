# Omnichannel Agentic AI Commerce

Implementation repo for:

Project statement: "An Agentic AI Framework for Persistent Omni-Channel Conversational Sales and Autonomous Retail Task Orchestration"

This repo currently delivers a production-style v1 web implementation with:

- FastAPI backend (`backend/`)
- React + Vite + Tailwind frontend (`frontend/`)
- REST + WebSocket conversational commerce flows
- Session/cart continuity across guest -> authenticated transitions
- Optional LLM-based intent classification (OpenAI or Anthropic)
- Abandoned-cart outgoing voice recovery orchestration (SuperU integration hooks)

Native mobile and native kiosk apps are intentionally deferred. The web app is responsive and is the current channel implementation.

## Table Of Contents

1. [Project Scope](#project-scope)
2. [Feature Coverage Matrix](#feature-coverage-matrix)
3. [Architecture](#architecture)
4. [Repository Layout](#repository-layout)
5. [Prerequisites](#prerequisites)
6. [Quick Start](#quick-start)
7. [Environment Variables](#environment-variables)
8. [Session, Cart, And Memory Continuity](#session-cart-and-memory-continuity)
9. [API Guide](#api-guide)
10. [WebSocket Protocol](#websocket-protocol)
11. [Natural Language Capabilities](#natural-language-capabilities)
12. [Voice Recovery (SuperU)](#voice-recovery-superu)
13. [Security Controls](#security-controls)
14. [Observability](#observability)
15. [Testing And Quality Gates](#testing-and-quality-gates)
16. [CI Pipeline](#ci-pipeline)
17. [Troubleshooting](#troubleshooting)
18. [Known Gaps / Deferred Work](#known-gaps--deferred-work)
19. [Supporting Docs](#supporting-docs)

## Project Scope

### In Scope (Current)

- Guest browse and cart operations
- Login/register required before order creation
- Guest cart merge into authenticated cart during auth
- Account-linked session continuity across interactions
- Conversational assistant for catalog/cart/order/support/memory actions
- Product listing + dedicated product detail view
- Admin APIs for catalog, category, inventory, support, and voice controls
- Signed SuperU callback ingestion for voice outcomes
- Rate limiting, request hardening, security headers
- Prometheus metrics + health endpoint

### Explicitly Deferred

- Native iOS/Android app
- Native in-store kiosk app shell
- Real payment processor integration (current payment flow is token-stubbed)
- Regulatory compliance workflows (deferred for now)

## Feature Coverage Matrix

| Capability From Docs | Status | Notes |
| --- | --- | --- |
| Guest browse/cart | Implemented | Guest session + cart supported through `session_id` and `X-Session-Id` |
| Login required before order creation | Implemented | Order endpoints require auth; chat checkout blocks guest users |
| Guest-to-auth cart continuity | Implemented | Guest cart merged into user cart on register/login |
| Session continuity | Implemented | User session resolution across REST/WS interactions |
| Product detail page | Implemented | Frontend supports `/products/{id}` route |
| Conversational cart/order actions | Implemented | Add/remove/update/clear cart, checkout, order status, refund, cancel |
| Preference memory | Implemented | Save/show/forget/clear preferences for authenticated users |
| Interaction history restore | Implemented | Session history + memory fallback for authenticated user |
| Personalized recommendations | Implemented | Preference/affinity-aware ranking in product agent |
| Outgoing voice cart recovery | Implemented | Queue/retry/guardrails/callback ingestion/admin controls |
| Mobile/kiosk native channels | Deferred | Responsive web only in current implementation |

## Architecture

```text
Frontend (React/Vite/Tailwind)
   |
   | HTTP + WebSocket
   v
FastAPI API Layer
   |
   +--> Middleware
   |     - Rate limiting
   |     - Security headers
   |     - Request hardening
   |     - Metrics + persistence triggers
   |
   +--> Route Layer
   |     - Auth, Products, Cart, Orders, Sessions, Interactions, Memory
   |     - Admin and Voice callback endpoints
   |
   +--> Orchestrator
   |     - IntentClassifier (rules + optional LLM)
   |     - ActionExtractor
   |     - AgentRouter
   |     - Product/Cart/Order/Support/Memory agents
   |
   +--> Services + Repositories
   |     - Domain business logic
   |     - In-memory store + optional Mongo/Redis adapters
   |
   +--> Infra Integrations
         - LLM client (OpenAI/Anthropic)
         - SuperU outbound voice client
         - Prometheus metrics + health
```

### Core Runtime Behavior

- Rule-based intent classification always runs first.
- Optional LLM classification can override rule result when confidence is higher.
- Orchestrator records interaction history and updates session conversation state.
- Memory recording runs asynchronously for authenticated users.
- Mutating HTTP requests trigger state snapshot persistence when Mongo is connected.

## Repository Layout

```text
backend/
  app/
    api/routes/              REST endpoints + voice webhook
    agents/                  Product/Cart/Order/Support/Memory agents
    orchestrator/            Intent/action/router/formatter pipeline
    services/                Business logic
    repositories/            Storage abstraction (in-memory + adapters)
    infrastructure/          LLM/SuperU/rate-limit/metrics/persistence
    scripts/                 DB index/bootstrap/perf smoke scripts
  tests/                     Unit + integration tests

frontend/
  src/
    App.tsx                  Main app UI and chat workflow
    api.ts                   API/WebSocket client helpers
    styles.css               Tailwind + visual system
    types.ts                 Shared frontend types
  tests/e2e/                 Playwright journeys

docs/                        PRD, SDD, architecture, API contracts, etc.
monitoring/                  Prometheus + Grafana provisioning
scripts/                     Local validation orchestration
.github/workflows/ci.yml     CI pipeline
```

## Prerequisites

- Python `3.11+`
- Node.js `20.19+` or `22.12+` (Vite 7 compatible)
- npm `10+`
- Docker Desktop + Docker Compose (optional but recommended)
- Optional external services for persistence mode:
  - MongoDB 7
  - Redis 7

## Quick Start

## Option A: Docker Compose (Recommended)

```bash
docker compose up --build
```

Before running compose, set secrets in your shell or local `.env` (never commit real values):

- `TOKEN_SECRET`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

Default local endpoints:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- MongoDB: `mongodb://localhost:27017`
- Redis: `redis://localhost:6379`

Notes:

- Compose runs backend with `ENABLE_EXTERNAL_SERVICES=true`.
- Mongo indexes are created before backend startup.

## Option B: Local Dev (In-Memory Only)

### Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
. .venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install and run:

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Option C: Local Dev With Mongo/Redis Persistence

1. Run Mongo + Redis locally.
1. Set `ENABLE_EXTERNAL_SERVICES=true` in `backend/.env`.
1. Run index and seed scripts:

```bash
cd backend
python -m app.scripts.create_indexes
python -m app.scripts.bootstrap_db
```

1. Start backend and frontend as in Option B.

## Environment Variables

Copy examples first:

- Backend: `backend/.env.example`
- Frontend: `frontend/.env.example`

### Why Both `OPENAI_API_KEY` And `ANTHROPIC_API_KEY`?

The backend supports two LLM providers behind one abstraction. Only one is active at a time via `LLM_PROVIDER`:

- `LLM_PROVIDER=openai` -> uses `OPENAI_API_KEY`
- `LLM_PROVIDER=anthropic` -> uses `ANTHROPIC_API_KEY`

Keeping both keys in `.env.example` allows provider switching without editing source.

### Frontend Variables

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:8000/v1` | REST API base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | WebSocket endpoint |

### Backend Variables (Full Reference)

#### Core App + Auth

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `Omnichannel Agentic Commerce API` | FastAPI app title |
| `API_PREFIX` | `/v1` | API namespace prefix |
| `TOKEN_SECRET` | `replace-with-strong-secret` | JWT signing secret |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | Access token TTL (15 min) |
| `REFRESH_TOKEN_TTL_SECONDS` | `604800` | Refresh token TTL (7 days) |

#### Commerce Defaults

| Variable | Default | Description |
| --- | --- | --- |
| `CART_TAX_RATE` | `0.08` | Tax multiplier for cart totals |
| `DEFAULT_SHIPPING_FEE` | `5.99` | Flat shipping fee |

#### Connectivity + Persistence

| Variable | Default | Description |
| --- | --- | --- |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) |
| `MONGODB_URI` | `mongodb://localhost:27017/commerce` | Mongo URI |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URI |
| `ENABLE_EXTERNAL_SERVICES` | `false` | Enable Mongo/Redis integrations |

#### Rate Limits + Request Hardening

| Variable | Default | Description |
| --- | --- | --- |
| `RATE_LIMIT_ANONYMOUS_PER_MINUTE` | `120` | Anonymous request/minute limit |
| `RATE_LIMIT_AUTHENTICATED_PER_MINUTE` | `600` | Authenticated request/minute limit |
| `RATE_LIMIT_ADMIN_PER_MINUTE` | `2000` | Admin request/minute limit |
| `REQUEST_MAX_BODY_BYTES` | `10485760` | Request body max bytes (10MB) |
| `SESSION_COOKIE_SECURE` | `true` | Secure cookie flag |
| `SESSION_COOKIE_SAMESITE` | `lax` | Cookie same-site policy |
| `ENFORCE_JSON_CONTENT_TYPE` | `true` | Reject non-JSON mutation requests |
| `REJECT_DUPLICATE_CRITICAL_HEADERS` | `true` | Reject duplicated critical headers |
| `ADMIN_MFA_REQUIRED` | `false` | Enforce OTP for admin login |
| `ADMIN_MFA_STATIC_CODE` | `` | Static OTP value when MFA enabled |

#### LLM

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_ENABLED` | `false` | Enable external LLM calls |
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | Model name sent to provider |
| `LLM_TIMEOUT_SECONDS` | `8` | Provider call timeout |
| `LLM_MAX_TOKENS` | `200` | Max response tokens |
| `LLM_TEMPERATURE` | `0` | Sampling temperature |
| `LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before open state |
| `LLM_CIRCUIT_BREAKER_TIMEOUT_SECONDS` | `60` | Circuit open duration |
| `LLM_INTENT_CLASSIFIER_ENABLED` | `false` | Enable LLM intent classifier path |
| `LLM_PLANNER_ENABLED` | `true` | Enable LLM action planner path |
| `LLM_DECISION_POLICY` | `planner_first` | `planner_first` or `classifier_first` |
| `PLANNER_FEATURE_ENABLED` | `true` | Global planner feature flag (independent of `LLM_ENABLED`) |
| `PLANNER_CANARY_PERCENT` | `100` | Percent of sessions eligible for planner rollout |
| `LLM_PLANNER_MAX_ACTIONS` | `5` | Hard cap on planner action steps |
| `LLM_PLANNER_MIN_CONFIDENCE` | `0.55` | Minimum confidence required to execute plan |
| `LLM_PLANNER_EXECUTION_MODE` | `partial` | `partial` or `atomic` multi-step execution |
| `ORCHESTRATOR_MAX_ACTIONS_PER_REQUEST` | `5` | Max executed actions per user request |
| `OPENAI_API_KEY` | `` | OpenAI key (when provider=openai) |
| `ANTHROPIC_API_KEY` | `` | Anthropic key (when provider=anthropic) |

Planner/classifier decision policy:

- This project enforces one primary LLM decision path per request.
- `LLM_DECISION_POLICY=planner_first`: planner is attempted first (rule-based classifier still provides fallback intent/actions).
- `LLM_DECISION_POLICY=classifier_first`: classifier is primary; planner is only attempted for multi-action requests.

#### WebSocket

| Variable | Default | Description |
| --- | --- | --- |
| `WS_HEARTBEAT_INTERVAL_SECONDS` | `25` | Ping interval |
| `WS_HEARTBEAT_TIMEOUT_SECONDS` | `70` | Disconnect threshold without pong |

#### SuperU + Voice Recovery

| Variable | Default | Description |
| --- | --- | --- |
| `SUPERU_ENABLED` | `false` | Enable SuperU API usage |
| `SUPERU_API_URL` | `https://api.superu.ai` | SuperU base URL |
| `SUPERU_API_KEY` | `` | SuperU API key |
| `SUPERU_ASSISTANT_ID` | `` | Default assistant id |
| `SUPERU_FROM_PHONE_NUMBER` | `` | Outbound caller number |
| `SUPERU_WEBHOOK_SECRET` | `` | HMAC secret for callback verification |
| `SUPERU_WEBHOOK_TOLERANCE_SECONDS` | `300` | Allowed callback timestamp drift |
| `VOICE_RECOVERY_SCHEDULER_ENABLED` | `false` | Background scan loop enable |
| `VOICE_RECOVERY_SCAN_INTERVAL_SECONDS` | `30` | Scheduler interval |
| `VOICE_ABANDONMENT_MINUTES` | `30` | Cart inactivity threshold |
| `VOICE_MAX_ATTEMPTS_PER_CART` | `3` | Max retry attempts per recovery key |
| `VOICE_MAX_CALLS_PER_USER_PER_DAY` | `2` | User daily cap |
| `VOICE_MAX_CALLS_PER_DAY` | `300` | Global daily cap |
| `VOICE_DAILY_BUDGET_USD` | `300` | Soft daily spend guardrail |
| `VOICE_ESTIMATED_COST_PER_CALL_USD` | `0.7` | Cost estimate per call |
| `VOICE_QUIET_HOURS_START` | `21` | Quiet hours start (local) |
| `VOICE_QUIET_HOURS_END` | `8` | Quiet hours end (local) |
| `VOICE_RETRY_BACKOFF_SECONDS_CSV` | `60,300,900` | Retry delays |
| `VOICE_SCRIPT_VERSION` | `v1` | Script version label |
| `VOICE_SCRIPT_TEMPLATE` | `Hi {name}, ...` | Voice script template |
| `VOICE_GLOBAL_KILL_SWITCH` | `false` | Stop/cancel jobs immediately |
| `VOICE_DEFAULT_TIMEZONE` | `UTC` | Fallback timezone |
| `VOICE_ALERT_BACKLOG_THRESHOLD` | `50` | Alert threshold for queued+retrying jobs |
| `VOICE_ALERT_FAILURE_RATIO_THRESHOLD` | `0.35` | Alert threshold for failure ratio |

## Session, Cart, And Memory Continuity

### Guest -> Auth Transition

On `POST /v1/auth/register` and `POST /v1/auth/login`:

1. If session id exists (`X-Session-Id` or `session_id` cookie), guest cart is merged into user cart.
2. A user-scoped session is resolved/created.
3. User identity is linked to that channel/session.
4. Response includes `sessionId`.

### Cart Merge Rules

- Match key: `productId + variantId`
- If both carts contain same item, quantities are added (capped to 50)
- Guest discount is carried only when user cart has no discount
- Guest cart is deleted after successful merge

### Cross-Channel Continuity (Current Behavior)

- Sessions are persisted and linked to user identity.
- `session_service.resolve_user_session(...)` reuses latest active user session when possible.
- This enables continuity across web channel surfaces and reconnects.

### Memory Model

- Guest users: no long-term memory write.
- Authenticated users:
  - Preferences (`size`, brands, categories, styles, colors, price range)
  - Interaction history (truncated summaries)
  - Affinity counters (product/category/brand)
- Memory APIs allow view/update/forget/clear operations.

## API Guide

Base URLs:

- REST: `http://localhost:8000/v1`
- WebSocket: `ws://localhost:8000/ws`
- OpenAPI UI: `http://localhost:8000/docs`

### Auth Model

- Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

- Anonymous cart/session flows rely on:
  - `X-Session-Id` header, or
  - `session_id` cookie

### Endpoint Map

#### Public/Anonymous

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `GET /v1/products`
- `GET /v1/products/{product_id}`
- `GET /v1/cart`
- `POST /v1/cart/items`
- `PUT /v1/cart/items/{item_id}`
- `DELETE /v1/cart/items/{item_id}`
- `POST /v1/cart/apply-discount`
- `POST /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `DELETE /v1/sessions/{session_id}`
- `POST /v1/interactions/message`
- `GET /v1/interactions/history`
- `POST /v1/voice/superu/callback`
- `GET /health`
- `GET /metrics`
- `WS /ws`

#### Authenticated User

- `POST /v1/orders`
- `GET /v1/orders`
- `GET /v1/orders/{order_id}`
- `POST /v1/orders/{order_id}/cancel`
- `POST /v1/orders/{order_id}/refund`
- `PUT /v1/orders/{order_id}/shipping-address`
- `GET /v1/memory`
- `GET /v1/memory/preferences`
- `PUT /v1/memory/preferences`
- `GET /v1/memory/history`
- `DELETE /v1/memory`
- `DELETE /v1/memory/preferences`
- `DELETE /v1/memory/preferences/{key}`
- `DELETE /v1/memory/history`

#### Admin (Requires Admin Role)

- `GET /v1/admin/stats`
- `GET /v1/admin/categories`
- `GET /v1/admin/categories/records`
- `POST /v1/admin/categories`
- `PUT /v1/admin/categories/{category_id}`
- `DELETE /v1/admin/categories/{category_id}`
- `POST /v1/admin/products`
- `PUT /v1/admin/products/{product_id}`
- `DELETE /v1/admin/products/{product_id}`
- `GET /v1/admin/inventory/{variant_id}`
- `PUT /v1/admin/inventory/{variant_id}`
- `GET /v1/admin/support/tickets`
- `PATCH /v1/admin/support/tickets/{ticket_id}`
- `GET /v1/admin/activity`
- `GET /v1/admin/activity/integrity`
- `GET /v1/admin/voice/settings`
- `PUT /v1/admin/voice/settings`
- `POST /v1/admin/voice/process`
- `GET /v1/admin/voice/calls`
- `GET /v1/admin/voice/jobs`
- `GET /v1/admin/voice/suppressions`
- `POST /v1/admin/voice/suppressions`
- `DELETE /v1/admin/voice/suppressions/{user_id}`
- `GET /v1/admin/voice/alerts`
- `GET /v1/admin/voice/stats`

### API Smoke Examples

Set base URL:

```bash
export API=http://localhost:8000/v1
```

Windows PowerShell:

```powershell
$env:API="http://localhost:8000/v1"
```

Register:

```bash
curl -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email":"user1@example.com",
    "password":"SecurePass123!",
    "name":"User One"
  }'
```

Login:

```bash
curl -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email":"user1@example.com",
    "password":"SecurePass123!"
  }'
```

Create session:

```bash
curl -X POST "$API/sessions" \
  -H "Content-Type: application/json" \
  -d '{"channel":"web","initialContext":{}}'
```

List products:

```bash
curl "$API/products?query=running%20shoes&limit=5"
```

Add cart item (guest/session):

```bash
curl -X POST "$API/cart/items" \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: session_000001" \
  -d '{"productId":"prod_001","variantId":"var_001","quantity":1}'
```

Create order (auth required + idempotency key required):

```bash
curl -X POST "$API/orders" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Idempotency-Key: order-attempt-001" \
  -d '{
    "shippingAddress":{
      "name":"User One",
      "line1":"123 Main St",
      "city":"Austin",
      "state":"TX",
      "postalCode":"78701",
      "country":"US"
    },
    "paymentMethod":{
      "type":"card",
      "token":"pm_test_123"
    }
  }'
```

Send conversational message via REST:

```bash
curl -X POST "$API/interactions/message" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId":"session_000001",
    "content":"add 2 running shoes to cart",
    "channel":"web"
  }'
```

## WebSocket Protocol

Connect:

```text
ws://localhost:8000/ws?sessionId=<session_id>
```

If `sessionId` is missing, server creates one and emits:

```json
{"type":"session","payload":{"sessionId":"session_...","expiresAt":"..."}}
```

### Client -> Server Events

- `message`
- `typing`
- `ping`
- `pong`

Example message:

```json
{
  "type": "message",
  "payload": {
    "content": "show me running shoes under $150 and add to cart",
    "typing": true,
    "stream": true
  }
}
```

### Server -> Client Events

- `session`
- `typing`
- `stream_start`
- `stream_delta`
- `stream_end`
- `response`
- `error`
- `ping`
- `pong`

Heartbeat is enforced using `WS_HEARTBEAT_INTERVAL_SECONDS` and `WS_HEARTBEAT_TIMEOUT_SECONDS`.

## Natural Language Capabilities

Current intents recognized by the orchestrator:

- Product discovery:
  - `product_search`
  - `search_and_add_to_cart`
- Cart management:
  - `add_to_cart`
  - `add_multiple_to_cart`
  - `apply_discount`
  - `update_cart`
  - `adjust_cart_quantity`
  - `remove_from_cart`
  - `clear_cart`
  - `view_cart`
- Order lifecycle:
  - `checkout`
  - `order_status`
  - `change_order_address`
  - `cancel_order`
  - `request_refund`
  - `multi_status`
- Memory:
  - `show_memory`
  - `save_preference`
  - `forget_preference`
  - `clear_memory`
- Support:
  - `support_escalation`
  - `support_status`
  - `support_close`
- Fallback:
  - `general_question`

Example utterances that work well:

- `show me running shoes under $150`
- `add 2 running shoes and 1 hoodie to my cart`
- `increase quantity of running shoes in my cart`
- `remove one running shoe from cart`
- `empty my cart`
- `checkout`
- `where is my order`
- `cancel order order_000001`
- `refund order order_000001`
- `change order address line1=500 Main St, city=Austin, state=TX, postalCode=78701, country=US`
- `remember I like denim and size M`
- `what do you remember about me`
- `forget my color preference`

## Voice Recovery (SuperU)

Voice recovery pipeline is implemented with:

- abandoned cart job enqueueing
- retry/backoff
- dead-letter handling
- quiet-hours checks
- daily cap and budget guardrails
- user suppression list
- alert generation
- signed callback ingestion endpoint

### Enable Voice Recovery

1. Configure env:
   - `SUPERU_ENABLED=true`
   - `SUPERU_API_KEY=<key>`
   - `SUPERU_ASSISTANT_ID=<assistant>`
   - `SUPERU_FROM_PHONE_NUMBER=<number>`
   - `SUPERU_WEBHOOK_SECRET=<secret>`
   - `VOICE_RECOVERY_SCHEDULER_ENABLED=true`
2. Optionally tune voice guardrail settings in env or via admin endpoints.
3. Use admin endpoint `POST /v1/admin/voice/process` to force immediate processing.

### Callback Endpoint

- `POST /v1/voice/superu/callback`
- Signature headers accepted:
  - `X-SuperU-Signature` or `X-Signature`
  - `X-SuperU-Timestamp` or `X-Timestamp`
- Signature verification:
  - HMAC SHA256 over `"<timestamp>.<raw_body>"`
  - secret: `SUPERU_WEBHOOK_SECRET`
  - timestamp drift bounded by `SUPERU_WEBHOOK_TOLERANCE_SECONDS`

## Security Controls

Implemented controls in current codebase:

- JWT access/refresh tokens
- refresh token rotation
- role checks for admin routes
- per-tier rate limiting (anonymous/authenticated/admin)
- abuse escalation with penalty windows
- request body size limit
- strict JSON content type checks for mutating API calls
- duplicate critical header rejection
- secure response headers:
  - `Content-Security-Policy`
  - `X-Content-Type-Options`
  - `X-Frame-Options`
  - `Referrer-Policy`
  - `Permissions-Policy`
- WebSocket origin validation against allowed CORS origins
- tamper-evident admin activity logging + integrity check endpoint

## Observability

### Health

`GET /health` returns status for:

- Mongo connectivity
- Redis connectivity
- state persistence enablement
- LLM circuit breaker state
- voice recovery runtime/provider flags

### Metrics

`GET /metrics` emits Prometheus format metrics including:

- `commerce_http_requests_total`
- `commerce_http_errors_total`
- `commerce_http_request_duration_ms_*`
- `commerce_checkout_total`
- `commerce_security_events_total`

## Testing And Quality Gates

### Backend Tests

```bash
cd backend
pytest tests -q
```

Coverage gate:

```bash
cd backend
pytest tests -q --cov=app --cov-fail-under=80
```

### NL Intent/Action Eval Suite

```bash
cd backend
pytest tests/nl_eval -q
```

### Frontend Lint + Build

```bash
cd frontend
npm run lint
npm run build
```

### Frontend E2E

```bash
cd frontend
npm run test:e2e
```

### Performance Smoke

```bash
cd backend
python -m app.scripts.perf_smoke --iterations 40 --ws-iterations 20
```

### One-Command Local Validation

Windows PowerShell:

```powershell
./scripts/validate_local.ps1
```

Optional flags:

- `-SkipE2E`
- `-SkipPerf`

## CI Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`) includes:

- Mongo index/bootstrap verification
- backend tests + coverage gate
- NL intent/action evaluation gate (`tests/nl_eval`)
- security scans (Bandit + pip-audit)
- backend perf smoke
- frontend build
- frontend Playwright E2E

## Troubleshooting

### `401 Authentication required`

- Ensure `Authorization: Bearer <access_token>` is set for protected endpoints.

### `400 Missing Idempotency-Key header` on order creation

- Include `Idempotency-Key` on `POST /v1/orders`.

### `Checkout complete` fails in chat as guest

- Expected behavior. Login is required before order creation.

### WebSocket disconnects frequently

- Check heartbeat settings:
  - `WS_HEARTBEAT_INTERVAL_SECONDS`
  - `WS_HEARTBEAT_TIMEOUT_SECONDS`
- Verify browser/network proxies are not terminating idle websockets.

### Voice callbacks return `401`

- Verify `SUPERU_WEBHOOK_SECRET`.
- Ensure callback timestamp is within `SUPERU_WEBHOOK_TOLERANCE_SECONDS`.

### No persistence across restarts

- Confirm `ENABLE_EXTERNAL_SERVICES=true`.
- Verify Mongo connectivity in `/health`.
- Run index/bootstrap scripts.

### `admin` endpoint returns `403`

- Login using admin account and pass admin bearer token.
- Demo admin credentials:
  - Email: `admin@example.com`
  - Password: `AdminPass123!`

## Known Gaps / Deferred Work

- Native mobile app and native kiosk app are not implemented yet.
- Real payment provider integration is not implemented (payment path is stubbed).
- Compliance/regulatory workflows are intentionally deferred in current scope.
- Voice provider integration depends on valid SuperU credentials and webhook setup.

## Supporting Docs

Primary docs in `docs/`:

- `docs/idea.txt`
- `docs/prd.txt`
- `docs/sdd.txt`
- `docs/architecture.txt`
- `docs/API_Contracts.txt`
- `docs/Database_Schema.txt`
- `docs/Agent_Logic_Specs.txt`
- `docs/implementation_blueprint.txt`
- `docs/SECURITY.txt`
- `docs/TESTING_STRATEGY.txt`
- `docs/RELEASE_CHECKLIST.txt`

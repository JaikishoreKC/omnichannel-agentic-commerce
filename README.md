# Omnichannel Agentic AI Commerce

Monorepo scaffold for an agentic commerce platform with:

- FastAPI backend (`backend/`)
- React + Vite frontend (`frontend/`)
- Aligned spec set in `docs/`

## Current State

The initial implementation includes:

- Guest browsing and cart management
- Authenticated checkout requirement (guests cannot create orders)
- Session bootstrap and cart transfer on login/register
- Core endpoints under `/v1`
- Agent orchestration pipeline (intent -> actions -> router -> specialized agents)
- Real-time chat via WebSocket (`/ws`) and REST interactions endpoint
- Inventory reservation, payment authorization stub, and order confirmation notifications
- Admin inventory operations and richer admin analytics (agent performance, message volume, support queue)
- Support escalation tickets from conversational assistant
- Preference-aware recommendations (memory-informed product suggestions)
- API gateway rate limiting with standard rate-limit headers
- In-memory persistence with optional MongoDB/Redis connectivity
- Optional runtime state persistence to MongoDB (with Redis session cache mirrors) when `ENABLE_EXTERNAL_SERVICES=true`
- Repository-backed persistence path implemented for sessions, carts, orders, and memory (Mongo/Redis adapters)
- Backend unit/integration tests for auth, interactions, checkout, and websocket flows
- Playwright E2E coverage for 3 P0 user journeys (guest cart transfer, checkout, chat-driven checkout)
- Prometheus metrics endpoint and Grafana dashboards for latency/error/checkout success tracking

## Run Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

## Run Tests

```bash
cd backend
python -m pytest tests -q
```

```bash
cd frontend
npm run test:e2e
```

## Docker Compose

```bash
docker compose up --build
```

Services:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- MongoDB: `mongodb://localhost:27017`
- Redis: `redis://localhost:6379`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (anonymous viewer enabled)

## API Summary

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `GET /v1/products`
- `GET /v1/products/{productId}`
- `GET /v1/cart`
- `POST /v1/cart/items`
- `POST /v1/orders` (auth required)
- `POST /v1/orders/{orderId}/cancel`
- `POST /v1/sessions`
- `POST /v1/interactions/message`
- `GET /v1/memory/history`
- `GET /v1/admin/categories`
- `POST /v1/admin/products`
- `GET /v1/admin/inventory/{variantId}`
- `PUT /v1/admin/inventory/{variantId}`
- `GET /health`
- `GET /metrics`

## Demo Admin Account

- Email: `admin@example.com`
- Password: `AdminPass123!`

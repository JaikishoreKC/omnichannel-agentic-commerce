# API Server Instructions

> **FastAPI Backend Configuration & Deployment** — Setup, routing, dependency injection, async patterns, and troubleshooting for omnichannel-agentic-commerce backend.

## Server Architecture

### Tech Stack
- **Framework:** FastAPI 0.100+
- **ASGI Server:** Uvicorn (local dev), Gunicorn + Uvicorn workers (production)
- **Python:** 3.11+
- **Async Runtime:** asyncio (native)
- **Database:** MongoDB (async with motor)
- **Cache:** Redis (async with aioredis)
- **Logging:** Structlog + Python logging (JSON output in production)

### Directory Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app instantiation + startup/shutdown
│   ├── container.py         # Dependency injection container
│   ├── api/
│   │   ├── deps.py          # Dependency providers for routes
│   │   └── routes/          # Route modules (auth, cart, orders, etc.)
│   │       ├── auth_routes.py
│   │       ├── cart_routes.py
│   │       ├── order_routes.py
│   │       ├── product_routes.py
│   │       └── ...
│   ├── agents/              # Conversational agents
│   ├── application/         # Business workflows  
│   ├── services/            # Service layer (cart_service, order_service, etc.)
│   ├── repositories/        # Data access layer
│   ├── models/              # Pydantic schemas + database models
│   ├── infrastructure/      # External integrations (payments, shipping)
│   ├── orchestrator/        # Intent classification + agent routing
│   └── middleware/          # CORS, logging, tracing
├── Dockerfile               # Container image
├── requirements.txt         # Python dependencies
├── pytest.ini              # Pytest configuration
└── tests/
    ├── conftest.py         # Test fixtures
    ├── unit/               # Unit tests
    ├── integration/        # Integration tests (with real/mock services)
    └── ai_e2e/            # End-to-end agent tests
```

---

## Local Development Setup

### 1. Environment Configuration

```bash
# At repo root:
cd backend

# Copy template
cp .env.example .env

# Edit with local values
cat .env
```

**Required .env variables:**

```bash
# Database
MONGODB_URI=mongodb://localhost:27017/commerce
MONGODB_NAME=commerce

# Redis
REDIS_URI=redis://localhost:6379/0

# API Keys (optional for local dev, required for external services)
OPENROUTER_API_KEY=sk_...(from dashboard)
SUPERUSER_API_KEY=api_key_...(for admin endpoints)

# Features (default disabled for local dev)
ENABLE_EXTERNAL_SERVICES=false
ENABLE_VOICE_AGENT=false
ENABLE_PAYMENTS=false  # Set true only if testing payment flows

# Logging (local: console, production: JSON)
LOG_LEVEL=DEBUG
LOG_FORMAT=console  # or "json" for production
```

### 2. Install Dependencies

```bash
# From backend/ directory
pip install -r requirements.txt

# Optional: for performance testing
pip install -r requirements-perf.txt
```

### 3. Start Local Services

```bash
# Option A: Docker Compose (all services: MongoDB, Redis, backend, frontend)
cd .. && docker compose up --build

# Option B: Manual (MongoDB + Redis must be running separately)
# Terminal 1: MongoDB
mongod --dbpath ./data/mongodb

# Terminal 2: Redis
redis-server

# Terminal 3: Backend
cd backend && python -m uvicorn app.main:app --reload --port 8000

# Terminal 4: Frontend (optional)
cd frontend && npm run dev
```

### 4. Verify Server

```bash
# Health check
curl http://localhost:8000/health

# OpenAPI docs
open http://localhost:8000/docs  # Swagger UI
open http://localhost:8000/redoc  # ReDoc

# Check dependency injection container
curl -s http://localhost:8000/health | jq .
```

---

## FastAPI Application Structure

### Main App (`app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth_routes, cart_routes, order_routes

app = FastAPI(
    title="Omnichannel Commerce API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# CORS (allow frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://example.com"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# Routes
app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(cart_routes.router, prefix="/api/cart", tags=["cart"])
app.include_router(order_routes.router, prefix="/api/orders", tags=["orders"])

@app.on_event("startup")
async def startup():
    # Initialize services
    from app.container import container
    await container.init()

@app.on_event("shutdown")
async def shutdown():
    # Cleanup
    from app.container import container
    await container.close()

@app.get("/health")
async def health():
    return { "status": "healthy", "version": "1.0.0" }
```

### Dependency Injection (`app/container.py` & `app/api/deps.py`)

**Container Pattern:**
All services instantiated once at startup, injected into routes.

```python
# app/container.py
class Container:
    def __init__(self):
        self._mongo_client = None
        self._redis_client = None
        self._services = {}
    
    async def init(self):
        # Connect to MongoDB
        self._mongo_client = motor.motor_asyncio.AsyncMongoClient(MONGODB_URI)
        self._db = self._mongo_client[MONGODB_NAME]
        
        # Connect to Redis
        self._redis_client = aioredis.from_url(REDIS_URI)
        
        # Instantiate services
        self._services['cart_service'] = CartService(db=self._db, cache=self._redis_client)
        self._services['order_service'] = OrderService(db=self._db)
        self._services['user_service'] = UserService(db=self._db)
    
    async def close(self):
        if self._mongo_client:
            self._mongo_client.close()
        if self._redis_client:
            await self._redis_client.close()
    
    def get_service(self, name: str):
        return self._services[name]

container = Container()

# app/api/deps.py
from fastapi import Depends
from app.container import container

async def get_cart_service():
    return container.get_service('cart_service')

async def get_current_user(request: Request) -> User:
    # Extract user from JWT token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    # ... validate token ...
    return User(id=token_data.sub)

# Usage in route:
@router.get("/cart")
async def get_cart(
    user: User = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service)
):
    return await cart_service.get_user_cart(user.id)
```

### Route Handlers

**Thin Route Layer → Thick Service Layer**

```python
# ❌ WRONG: Business logic in route
@router.post("/cart/add")
async def add_to_cart_bad(request: AddCartRequest):
    if request.quantity < 1 or request.quantity > 50:
        raise HTTPException(status_code=400, detail="Invalid quantity")
    
    # Complex validation logic
    product = db.products.findOne(...)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Cart merge logic
    cart = db.carts.findOne(...)
    # ... merge items ...
    db.carts.update(...)
    return cart

# ✅ CORRECT: Route delegates to service
@router.post("/cart/add")
async def add_to_cart(
    request: AddCartRequest,
    session_id: str = Depends(get_session_id),
    cart_service: CartService = Depends(get_cart_service)
):
    try:
        result = await cart_service.add_item(
            session_id=session_id,
            product_id=request.productId,
            quantity=request.quantity
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Async & Concurrency Patterns

### Async Rules

**Rule 1: Use `async def` for I/O-bound operations**
```python
# ✓ Good: Database queries are I/O
async def fetch_user(user_id: str):
    return await db.users.find_one({"id": user_id})

# ✗ Bad: Sync call blocks event loop
def fetch_user(user_id: str):
    return db.users.find_one({"id": user_id})  # Sync MongoDB client
```

**Rule 2: `await` all async calls**
```python
# ✓ Good: Proper await
cart = await cart_service.get_user_cart(user_id)

# ✗ Bad: Missing await (returns coroutine, not result)
cart = cart_service.get_user_cart(user_id)  # Type: Coroutine, not dict
```

**Rule 3: Wrap sync calls with `asyncio.to_thread()` (when necessary)**
```python
# Example: Calling httpx.post() from sync code in async context
import asyncio
import httpx

async def make_payment_call():
    # ✓ Good: Wrap sync library call
    response = await asyncio.to_thread(httpx.post, "https://payment.api", json=data)
    
    # ✗ Bad: Direct sync call blocks event loop
    response = httpx.post("https://payment.api", json=data)  # Blocks!
```

**Rule 4: Test async code with proper fixtures**
```python
# conftest.py
import pytest

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_add_to_cart():
    cart_service = CartService(...)
    result = await cart_service.add_item(...)
    assert result.items.count > 0
```

### Concurrency Best Practices

```python
# ✓ Good: Concurrent async calls
async def fetch_user_and_cart(user_id: str):
    user, cart = await asyncio.gather(
        user_service.get_user(user_id),
        cart_service.get_user_cart(user_id)
    )
    return { "user": user, "cart": cart }

# ✗ Bad: Sequential calls (slower)
async def fetch_user_and_cart_slow(user_id: str):
    user = await user_service.get_user(user_id)
    cart = await cart_service.get_user_cart(user_id)  # Waits for user first
    return { "user": user, "cart": cart }

# ✓ Good: Timeout handling
try:
    result = await asyncio.wait_for(
        cart_service.process_payment(order_id),
        timeout=30.0
    )
except asyncio.TimeoutError:
    raise HTTPException(status_code=504, detail="Payment processing timeout")
```

---

## Error Handling & Logging

### Request Exception Handler

```python
# app/middleware/exception_handler.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

async def exception_handler(request: Request, exc: Exception):
    logger.error(
        "Request failed",
        exc_info=exc,
        extra={"path": request.url.path, "method": request.method}
    )
    
    if isinstance(exc, ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

# Register in main.py
app.add_exception_handler(Exception, exception_handler)
```

### Structured Logging

```python
# Setup (once at startup)
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
)

logger = structlog.get_logger()

# Usage in routes/services
logger.info("cart_item_added", user_id=user_id, product_id=product_id, quantity=quantity)
logger.error("payment_failed", order_id=order_id, error=str(exc), status_code=exc.status_code)
```

---

## Testing

### Unit Tests (No External Services)

```bash
# Run unit tests (mocked services)
python -m pytest backend/tests/unit -q

# With coverage
python -m pytest backend/tests/unit --cov=app --cov-report=term --cov-fail-under=80
```

**Test Pattern:**
```python
# tests/unit/test_cart_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.cart_service import CartService

@pytest.mark.asyncio
async def test_add_item_success():
    # Mock database
    mock_db = AsyncMock()
    mock_db.carts.find_one.return_value = {"_id": "1", "items": []}
    mock_db.carts.update_one.return_value = AsyncMock()
    
    service = CartService(db=mock_db)
    result = await service.add_item(
        session_id="sess_123",
        product_id="prod_abc",
        quantity=2
    )
    
    assert result["items"]["count"] == 1
    assert result["items"][0]["quantity"] == 2
```

### Integration Tests (Real Services)

```bash
# Run integration tests (real MongoDB, mocked external APIs)
python -m pytest backend/tests/integration -q

# With specific test
python -m pytest backend/tests/integration/test_auth_flow.py::test_register_and_login -v
```

### AI E2E Tests (Full Agent Loops)

```bash
# Run AI end-to-end tests (full conversational flows)
python -m pytest backend/tests/ai_e2e -s --tb=short
```

---

## Production Deployment

### Docker Image

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY app/ ./app
COPY pytest.ini .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start server
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Uvicorn Configuration (Production)

```bash
# Using Gunicorn + Uvicorn workers (recommended for production)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -

# Alternative: Direct uvicorn with multiple workers
python -m uvicorn app.main:app \
  --workers 4 \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info 
```

### Environment in Production

```bash
# .env (production)
DATABASE_URL=mongodb+srv://user:pass@cluster.mongodb.net/commerce
REDIS_URL=redis://:pass@redis.example.com:6379/0
LOG_FORMAT=json
LOG_LEVEL=INFO
ENABLE_EXTERNAL_SERVICES=true
ENABLE_PAYMENTS=true
CORS_ORIGINS=https://example.com,https://app.example.com
```

---

## Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| **Event loop already running** | `RuntimeError: asyncio loop already running` | Use `asyncio.new_event_loop()` in tests; check for nested `asyncio.run()` |
| **Connection timeout** | `asyncio.TimeoutError` when connecting to MongoDB | Check MongoDB service running; verify MONGODB_URI correct |
| **Coroutine never awaited** | `RuntimeWarning: coroutine ... was never awaited` | Add `await` to async function calls; check route handler is async |
| **Slow endpoint response** | API response >1s | Enable slow query logging; check database indexes; use `asyncio.gather()` for concurrent calls |
| **Memory leak** | Process memory grows over time | Check for unclosed database connections; enable profiling with `tracemalloc` |
| **CORS errors in frontend** | `Cross-Origin Request Blocked` | Verify `allow_origins` in CORS middleware includes frontend origin |
| **Docker build fails** | Package installation error | Check Python version compatibility; clear Docker cache: `docker builder prune` |

### Debug Utilities

```python
# Add to app/main.py for development
import asyncio

@app.get("/debug/info")
async def debug_info():
    return {
        "event_loop": asyncio.get_event_loop_policy(),
        "tasks": len(asyncio.all_tasks()),
        "connections": {
            "mongodb": "connected" if container._mongo_client else "disconnected",
            "redis": "connected" if container._redis_client else "disconnected"
        }
    }

# Check slow queries
@app.middleware("http")
async def log_request_time(request: Request, call_next):
    import time
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    if duration > 0.5:
        logger.warning(f"Slow request: {request.method} {request.url.path} took {duration:.2f}s")
    return response
```

---

## Quick Checklist: Server Readiness

- [ ] Python 3.11+ installed
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` file created and configured (MONGODB_URI, REDIS_URI)
- [ ] MongoDB service running (local or Docker)
- [ ] Redis service running (local or Docker)
- [ ] FastAPI app starts: `uvicorn app.main:app --reload`
- [ ] Health endpoint responds: `curl http://localhost:8000/health`
- [ ] Swagger docs loads: http://localhost:8000/docs
- [ ] Unit tests pass: `pytest backend/tests/unit -q`
- [ ] CORS middleware configured for frontend origin
- [ ] Logging configured (console for dev, JSON for production)
- [ ] Error handlers registered (500, 404, validation errors)


# Backend Development Instructions

> **Python FastAPI Backend** — Patterns, conventions, and guardrails for omnichannel-agentic-commerce backend development.

## Architecture Constraints

### Dependency Direction (ENFORCED)
Backend must respect strict layer dependency flow:

```
API Routes → Orchestrator/Application Workflows → Services → Repositories → Infrastructure
```

**Rules:**
- Route handlers MUST stay thin—no business logic
- Services contain ALL workflows and validation
- Repositories handle persistence abstractions (Mongo, Redis, in-memory)
- Infrastructure is isolated client/connection code
- **NEVER** import upward (e.g., repo importing services)
- **NEVER** put logic directly in routes

**Example:** Adding discount to cart
```python
# ❌ WRONG: Logic in route
@router.post("/apply-discount")
def apply_discount(...):
    cart = repo.get(...)
    cart["discount"] = ...  # ← Business rule in route
    repo.update(cart)
    return cart

# ✅ RIGHT: Logic in service
@router.post("/apply-discount")
def apply_discount(payload, ..., cart_service=Depends(get_cart_service)):
    cart = cart_service.apply_discount(...)  # ← Service owns rule
    return cart
```

---

## Dependency Injection Pattern

### Container-Based DI (REQUIRED)
All service instantiation goes through `backend/app/container.py`:

```python
# ✅ Correct: Access via container dependency
@router.get("")
def get_cart(..., cart_service=Depends(get_cart_service)):
    return cart_service.get_cart(...)

# ✅ Correct: Import only dependency functions
from app.api.deps import get_cart_service, get_product_service
```

**Never:**
```python
# ❌ WRONG: Direct instantiation
cart_service = CartService(...)

# ❌ WRONG: Global singletons
_cart_service = None
def get_service():
    global _cart_service
    if not _cart_service:
        _cart_service = CartService(...)
```

### File Locations
- **Container init:** `backend/app/container.py` (single source of truth)
- **Dependency exports:** `backend/app/api/deps.py` (route-facing getters)
- **Route handlers:** `backend/app/api/routes/*.py` (consume via Depends)
- **Service layer:** `backend/app/services/*.py` (orchestration logic)
- **Repository layer:** `backend/app/repositories/*.py` (data access only)

---

## Request/Response Contracts

### API Response Format (CRITICAL)
**All mutation endpoints MUST return the full resource object, never metadata.**

```python
# ❌ WRONG: Incomplete response metadata
@router.post("/items")
def add_cart_item(payload, ..., cart_service=Depends(...)) -> dict:
    cart = cart_service.add_item(...)
    return {"success": True, "cartId": cart["id"]}  # ← Missing cart state

# ✅ CORRECT: Return authoritative resource
@router.post("/items")
def add_cart_item(payload, ..., cart_service=Depends(...)) -> dict:
    cart = cart_service.add_item(...)
    return cart  # ← {id, items, itemCount, total, ...}
```

**Why:** Frontend state reconciliation depends on response body containing updated resource. Metadata-only responses break optimistic updates and cause UI render failures.

### Error Responses (ENFORCED)
All errors use `HTTPException` with proper status codes:

```python
from fastapi import HTTPException

# ✅ Correct
if not user:
    raise HTTPException(status_code=401, detail="Authentication required")

if user.role != "admin":
    raise HTTPException(status_code=403, detail="Admin role required")

if not cart:
    raise HTTPException(status_code=404, detail="Cart not found")

# Validation error details auto-formatted by Pydantic
# ❌ WRONG: Return error as dict
return {"error": "Something failed"}  # Don't do this
```

---

## Session & Cart Continuity

### Known Constraint: Planner Safeguards (ENFORCED)
For `add_to_cart` intents, planner is **gated and bounded** by rule-engine:
- **Single-item phrasing** (deterministic): Routed directly via rule-engine, planner BYPASSED
- **Multi-item phrasing** (e.g., "add X and Y"): Planner allowed only with:
  - Confidence floor: `intent_classifier.confidence >= 0.85`
  - Canary percent: Gated by `PLANNER_CANARY_PERCENT` (default 10%)
- **Why:** Planner can strip query params; single adds must stay deterministic via cart service rules

**Important:** This constraint is enforced in `backend/app/orchestrator/intent_classifier.py`. Do NOT remove or weaken these gates without explicit business approval.

### Cart State Flow During Auth
When user registers/logs in, session cart must attach to user account:

```python
# In auth_routes.py: _resolve_user_session_context
def _resolve_user_session_context(..., user_id: str, ...):
    # 1. Extract guest session cart (if exists)
    session_id = request.headers.get("X-Session-Id")
    
    # 2. Merge guest cart → user cart
    if session_id:
        cart_service.merge_guest_cart_into_user(session_id=session_id, user_id=user_id)
    
    # 3. Resolve user session (attach or create)
    resolved = session_service.resolve_user_session(
        user_id=user_id,
        preferred_session_id=session_id,
        ...
    )
    return resolved
```

**Guarantee:** Guest cart items persist through registration.

---

## Persistence & Caching

### Write-Through Caching Pattern (ENFORCED)
All persistence operations use three-tier caching:

```python
# ✅ Required pattern in repositories
def create(self, cart: dict[str, Any]) -> dict[str, Any]:
    self._write_to_redis(cart)        # ← Tier 1 (cache)
    self._write_to_mongo(cart)        # ← Tier 2 (primary)
    self._write_to_in_memory(cart)    # ← Tier 3 (fallback)
    return deepcopy(cart)
```

**Cache Invalidation:** Always invalidate on mutation
```python
def _invalidate_cache(self, *, user_id: str | None, session_id: str) -> None:
    cache_key = self._cache_key(user_id=user_id, session_id=session_id)
    with self._cart_read_cache_lock:
        self._cart_read_cache.pop(cache_key, None)
```

### Fallback Resilience (REQUIRED)
When Redis/Mongo unavailable, in-memory store must maintain consistency:

```python
# Test fallback mode with ENABLE_EXTERNAL_SERVICES=false
# Verify core flows still work:
# - Session creation & lookup
# - Cart CRUD operations
# - Order persistence
```

---

## Thread Safety & Concurrency

### Lock Usage (ENFORCED)
For shared state and race conditions, use `threading.Lock` or `threading.RLock`:

```python
from threading import RLock

class CartService:
    def __init__(self):
        self._cart_read_cache_lock = RLock()  # ← Per-operation locks
        self._cart_read_cache = {}
    
    def _read_cache_get(self, cache_key: str):
        with self._cart_read_cache_lock:
            entry = self._cart_read_cache.get(cache_key)
            return deepcopy(entry) if entry else None
```

**When to Lock:**
- Reading/writing shared mutable state (cache, fallback store)
- Concurrent auth operations (session resolution)
- Idempotency key guards (order creation)

**Never:** Use locks across request boundaries (FastAPI handles concurrency).

---

## Testing & Validation

### Test Execution (REQUIRED)
Run tests from repository root, not subdirectory:

```bash
# ✅ Correct: From repo root
python -m pytest backend/tests -q --cov=app --cov-report=term --cov-fail-under=80

# ✅ Correct: Specific suite
python -m pytest backend/tests/unit -q
python -m pytest backend/tests/integration -q
python -m pytest backend/tests/ai_e2e -s

# ❌ WRONG: From backend/ directory (breaks import paths)
cd backend && pytest tests/  # Don't do this
```

### Coverage Gate (ENFORCED)
- Minimum coverage: **80%**
- Run after service/repo changes: `--cov-fail-under=80`
- Fail the gate if below threshold

### Environment Setup (REQUIRED)
Before running backend locally:

```bash
# Copy templates (don't commit secrets)
cp backend/.env.example backend/.env

# Install & activate
python -m venv .venv
source .venv/Scripts/activate  # Windows
pip install -r backend/requirements.txt
```

---

## Docker & Deployment

### Docker Compose Configuration (IMPORTANT)
When using `docker-compose.yml`, remember:
- `${VAR}` syntax gets parsed by compose; escape templates with `$$`
- Example: `VOICE_SCRIPT_TEMPLATE` should use `$$` for literal `${placeholder}`

```yaml
# ❌ WRONG: Literal templates break
environment:
  VOICE_SCRIPT_TEMPLATE: "Hello ${name}"  # compose tries to substitute

# ✅ CORRECT: Escape with $$
environment:
  VOICE_SCRIPT_TEMPLATE: "Hello $${name}"  # compose leaves as literal
```

---

## Error Handling & Logging

### Exception Logging (RECOMMENDED)
Use structured logging for errors:

```python
from app.infrastructure.logging import get_logger

logger = get_logger(__name__)

def process_order(...):
    try:
        ...
    except ValueError as e:
        logger.error(f"Invalid order data: {e}", extra={"order_id": order_id})
        raise HTTPException(status_code=400, detail="Invalid order")
    except Exception as e:
        logger.exception(f"Unexpected error processing order")  # auto-traces
        raise HTTPException(status_code=500, detail="Internal server error")
```

### Windows UTF-8 Encoding (REQUIRED for CI)
Tests on Windows require UTF-8 mode to avoid `UnicodeEncodeError (cp1252)`:

```bash
# PowerShell (Windows development)
$env:PYTHONUTF8=1
python -m pytest backend/tests -q

# Bash/Linux (CI pipeline)
PYTHONUTF8=1 pytest backend/tests -q
```

**Why:** Rich exception formatting uses UTF-8 symbols; Windows cmd defaults to cp1252. Set `PYTHONUTF8=1` globally for local development.

---

## Security & Configuration

### Required Environment Variables (ENFORCED)
Before deployment set:

```bash
# ✅ REQUIRED: Always set, must differ from defaults
TOKEN_SECRET="<32+-char-random-string>"    # Not "super-secret-key"
ADMIN_MFA_TOTP_SECRET="<base32-encoded>"   # REQUIRED in production (SENSITIVE setting)

# ✅ REQUIRED in Production / OPTIONAL in Dev
# (Set SENSITIVE=true in production .env to enforce MFA)
ADMIN_MFA_REQUIRED=false  # Set to true in production

# ✅ RECOMMENDED: External service keys (if enabled)
ENABLE_EXTERNAL_SERVICES=true   # Dev: may set false for local testing
OPENROUTER_API_KEY="..."
SUPERU_API_KEY="..."
SUPERU_FROM_NUMBER="..."
```

**Security Validation:** `container.settings.validate_security()` runs on startup and will:
- ❌ Reject default TOKEN_SECRET in production (SENSITIVE=true)
- ❌ Reject missing ADMIN_MFA_TOTP_SECRET if ADMIN_MFA_REQUIRED=true
- ✅ Allow defaults in dev/test (SENSITIVE=false)

### Password Hashing (ENFORCED)
Always use provided security module:

```python
from app.core.security import hash_password, verify_password

# ✅ Correct
user["passwordHash"] = hash_password(user_password)
if not verify_password(supplied_password, user["passwordHash"]):
    raise HTTPException(status_code=401, detail="Invalid credentials")

# ❌ WRONG: Never store plaintext or use weak hashing
user["password"] = user_password  # Don't store plaintext
```

---

## Async & Concurrency

### Async in FastAPI (BEST PRACTICE)
FastAPI handlers are async-compatible; use for I/O:

```python
from app.services.external_api import ExternalAPI

@router.post("/external-call")
async def call_external(payload, service=Depends(...)):
    # ✅ Async I/O operations run concurrently
    result = await service.fetch_data_async()
    return result

# For sync functions, FastAPI runs in thread pool
@router.get("/blocking-compute")
def compute_something(...):
    # FastAPI detects sync, runs in thread pool
    heavy_result = expensive_computation()
    return heavy_result
```

### Test Seams (REQUIRED for Testability)
When wrapping sync operations in async contexts, use `asyncio.to_thread()` to preserve test mocking:

```python
import asyncio
import httpx

async def my_async_handler(...):
    # ✅ CORRECT: Seam remains visible to pytest monkeypatch
    result = await asyncio.to_thread(httpx.post, url, json=payload)
    return result

# pytest can still monkeypatch:
# monkeypatch.setattr("httpx.post", mock_post)
```

**Why:** Direct `await` calls bypass test seams. Using `to_thread()` ensures the sync function runs in the thread pool where monkeypatch can intercept it. This pattern is essential for unit test isolation.

---

## Code Organization

### File Naming
```
backend/app/
├── api/
│   ├── routes/         # One file per resource: cart_routes.py, order_routes.py
│   ├── deps.py         # Dependency getters (Depends() exports)
│   └── __init__.py
├── services/           # Business logic: cart_service.py, auth_service.py
├── repositories/       # Data access: cart_repository.py, session_repository.py
├── agents/             # Orchestrator agents: cart_agent.py, product_agent.py
├── orchestrator/       # Conversational intent/action pipeline
├── infrastructure/     # External clients: llm_client.py, mongo_client.py
├── models/
│   └── schemas.py      # Pydantic request/response models
├── core/
│   ├── security.py     # Password hashing, JWT creation
│   ├── config.py       # Environment loading
│   └── utils.py        # ID generation, timestamp utilities
├── middleware/         # Request/response processing
└── container.py        # DI container (SINGLE SOURCE OF TRUTH)
```

### Import Conventions
```python
# ✅ Correct: Import by layer, top-to-bottom
from app.api.deps import get_cart_service

# ✅ Correct: Service imports repository
from app.repositories.cart_repository import CartRepository

# ✅ Correct: Repository imports infrastructure
from app.infrastructure.persistence_clients import MongoClientManager

# ❌ WRONG: Skip layers
from app.services.cart_service import CartService  # in routes; use Depends instead

# ❌ WRONG: Circular imports
from app.repositories.cart_repository import CartRepository  # in repository itself
```

---

## Validation & Input Sanitization

### Use Pydantic Models (ENFORCED)
All route inputs must use Pydantic `BaseModel`:

```python
from pydantic import BaseModel, Field

class AddCartItemRequest(BaseModel):
    productId: str
    variantId: str
    quantity: int = Field(ge=1, le=50)  # ← Constraints enforced

# ✅ In route
@router.post("/items")
def add_cart_item(payload: AddCartItemRequest, ...):
    # payload is pre-validated; safe to access
    return cart_service.add_item(
        product_id=payload.productId,  # ← Type-safe, validated
        ...
    )
```

### Email/Phone Validation
```python
class RegisterRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = None  # Optional
    timezone: str | None = None

# Database layer then sanitizes/normalizes:
normalized_email = email.strip().lower()
normalized_phone = phone.strip() if phone else None
```

---

## Common Mistakes to Avoid

| Mistake | Why It's Wrong | Solution |
|---------|---------------|----------|
| Route returns `{"success": True}` | Frontend can't update state | Return full resource object |
| Bare `except:` clauses | Hides programming errors | Catch specific exceptions |
| Global singletons | Thread safety issues in tests | Use DI container instead |
| Importing services in repos | Reverse dependency violation | Repos are leaf layer |
| Storing plaintext passwords | Major security breach | Use `hash_password()` |
| Skipping idempotency keys | Duplicate charges possible | Check `Idempotency-Key` header |
| No cache invalidation | Stale data serves to clients | Invalidate on every mutation |
| Async in sync code without `to_thread` | Blocks other requests | Wrap with `asyncio.to_thread()` |
| Tests from backend/ directory | Import path breaks | Run from repo root |
| Committing .env files | Secrets exposed | Use `.env.example` templates |

---

## Quick Checklist: Before Pushing

- [ ] Route handler thin (logic in service)
- [ ] HTTPException used for errors (not `return {"error": ...}`)
- [ ] Mutations return full resource object
- [ ] Pydantic models validate all inputs
- [ ] Tests pass: `python -m pytest backend/tests -q --cov=app --cov-fail-under=80`
- [ ] Linting passes: `python -m pylint app/ --fail-under=8.0`
- [ ] No plaintext passwords or secrets in code
- [ ] Cache invalidated on mutation
- [ ] Thread-safe: locks used for shared state
- [ ] Dependency injection used (no global singletons)
- [ ] Imports respect layer boundaries (downward only)


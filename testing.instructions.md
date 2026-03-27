# Testing Instructions

> **Comprehensive Testing Strategy** — Unit, integration, E2E, performance, and agent testing across omnichannel-agentic-commerce backend and frontend.

## Testing Philosophy

**Coverage Goal:** 80%+ unit test coverage, integration tests for critical paths, E2E tests for agent flows.

**Test Pyramid:**
```
          ╱╲  E2E & Performance
         ╱  ╲  (10% - slow, expensive)
        ╱    ╲
       ╱──────╲
      ╱ Integration ╲  (20% - moderate speed)
     ╱────────────────╲
    ╱  Unit Tests     ╲  (70% - fast)
   ╱──────────────────────╲
```

---

## Backend Testing

### Test Structure

```
backend/tests/
├── conftest.py              # Shared fixtures (asyncio, mocks, database)
├── unit/                    # Fast, isolated, mocked dependencies
│   ├── test_cart_service.py
│   ├── test_order_service.py
│   ├── test_user_service.py
│   └── ...
├── integration/             # Medium speed, real DB + mocked external APIs
│   ├── test_auth_flow.py
│   ├── test_checkout_flow.py
│   ├── test_cart_persistence.py
│   └── ...
├── ai_e2e/                  # Slow, full agent loops with real decisions
│   ├── test_shopping_agent_flow.py
│   ├── test_support_agent_flow.py
│   └── ...
└── nl_eval/                 # Natural language model evaluation
    ├── test_intent_classification.py
    └── test_entity_extraction.py
```

### Unit Tests

**Goal:** Fast validation of business logic with mocked dependencies.

```bash
# Run unit tests only
python -m pytest backend/tests/unit -q

# With coverage report
python -m pytest backend/tests/unit --cov=app --cov-report=html --cov-report=term

# Run single test file
python -m pytest backend/tests/unit/test_cart_service.py -v

# Run single test
python -m pytest backend/tests/unit/test_cart_service.py::test_add_item_exceeds_quantity_limit -v
```

**Example Unit Test:**

```python
# backend/tests/unit/test_cart_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.cart_service import CartService
from app.models.schemas import AddCartItemRequest

@pytest.fixture
async def cart_service():
    """Mocked cart service for unit tests"""
    mock_db = AsyncMock()
    mock_cache = AsyncMock()
    service = CartService(db=mock_db, cache=mock_cache)
    return service

@pytest.mark.asyncio
async def test_add_item_success(cart_service):
    """Test adding item to cart"""
    cart_service._db.carts.find_one.return_value = {"_id": "1", "items": [], "userId": "user_123"}
    cart_service._db.carts.update_one.return_value = AsyncMock()
    
    result = await cart_service.add_item(
        session_id="sess_123",
        product_id="prod_abc",
        variant_id="var_xyz",
        quantity=2
    )
    
    assert result["success"] == True
    assert len(result["items"]) >= 1

@pytest.mark.asyncio
async def test_add_item_exceeds_max_quantity(cart_service):
    """Test quantity validation"""
    with pytest.raises(ValueError) as exc_info:
        await cart_service.add_item(
            session_id="sess_123",
            product_id="prod_abc",
            variant_id="var_xyz",
            quantity=101  # Exceeds limit
        )
    assert "Quantity must be 1-100" in str(exc_info.value)

@pytest.mark.asyncio
async def test_add_item_product_not_found(cart_service):
    """Test product validation"""
    cart_service._db.products.find_one.return_value = None
    
    with pytest.raises(ValueError) as exc_info:
        await cart_service.add_item(
            session_id="sess_123",
            product_id="prod_nonexistent",
            variant_id="var_xyz",
            quantity=1
        )
    assert "Product not found" in str(exc_info.value)
```

### Integration Tests

**Goal:** Validate workflows with real database and mocked external APIs.

```bash
# Run integration tests (uses MongoDB + mocked APIs)
python -m pytest backend/tests/integration -q

# Run with verbose output to see test names
python -m pytest backend/tests/integration -v

# Run specific integration test
python -m pytest backend/tests/integration/test_checkout_flow.py::test_guest_checkout -v

# Run with live external services (if needed)
ENABLE_EXTERNAL_SERVICES=true python -m pytest backend/tests/integration -v
```

**Example Integration Test:**

```python
# backend/tests/integration/test_checkout_flow.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def client():
    """HTTP client for API testing"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_guest_checkout_flow(client, mongodb_container):
    """Test complete checkout as guest user"""
    # 1. Add item to cart
    add_response = await client.post(
        "/api/cart/add",
        json={
            "productId": "prod_test_123",
            "variantId": "var_red_m",
            "quantity": 2
        },
        headers={"X-Session-ID": "sess_guest_123"}
    )
    assert add_response.status_code == 200
    cart = add_response.json()
    assert len(cart["items"]) == 1
    
    # 2. Create order from cart
    checkout_response = await client.post(
        "/api/orders/checkout",
        json={
            "cartId": cart["id"],
            "shippingAddress": {
                "name": "John Doe",
                "line1": "123 Main St",
                "city": "Boston",
                "state": "MA",
                "postalCode": "02101",
                "country": "US"
            },
            "email": "john@example.com"
        },
        headers={"X-Session-ID": "sess_guest_123"}
    )
    assert checkout_response.status_code == 200
    
    # 3. Verify order created
    order = checkout_response.json()
    assert order["status"] == "confirmed"
    assert order["total"] > 0
    
    # 4. Verify cart cleared
    cart_resp = await client.get(
        "/api/cart",
        headers={"X-Session-ID": "sess_guest_123"}
    )
    assert cart_resp.json()["items"] == []
```

### AI E2E Tests

**Goal:** Test full agent conversational flows with real decision-making.

```bash
# Run AI E2E tests (may take 5-10 minutes)
python -m pytest backend/tests/ai_e2e -s --tb=short

# Run specific agent test
python -m pytest backend/tests/ai_e2e/test_shopping_agent_flow.py::test_multi_turn_product_search -v

# Run with faster LLM (use mock responses)
MOCK_LLM_RESPONSES=true python -m pytest backend/tests/ai_e2e -s
```

**Example AI E2E Test:**

```python
# backend/tests/ai_e2e/test_shopping_agent_flow.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_multi_turn_product_search():
    """Test agent conversation: search → filter → add to cart"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        session_id = "sess_e2e_001"
        
        # Turn 1: User asks for shoes
        res1 = await client.post(
            "/api/conversate",
            json={"message": "I'm looking for running shoes"},
            headers={"X-Session-ID": session_id}
        )
        assert res1.status_code == 200
        response1 = res1.json()
        assert response1["agent"] == "shopping"  # Routed to shopping agent
        assert "shoes" in response1["message"].lower()
        
        # Turn 2: Filter by brand
        res2 = await client.post(
            "/api/conversate",
            json={"message": "Show me Nike ones"},
            headers={"X-Session-ID": session_id}
        )
        assert res2.status_code == 200
        response2 = res2.json()
        # Agent should have narrowed results
        assert response2["products"] is not None
        
        # Turn 3: Add to cart
        res3 = await client.post(
            "/api/conversate",
            json={"message": "I'll take the first one"},
            headers={"X-Session-ID": session_id}
        )
        assert res3.status_code == 200
        response3 = res3.json()
        assert response3.get("cartUpdated") == True
```

### Test Fixtures (conftest.py)

```python
# backend/tests/conftest.py
import pytest
import asyncio
from motor.motor_asyncio import AsyncMongoClient
import mongomock_motor
from app.container import Container
from app.main import app

# Event loop configured for async tests
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

# Mock database for unit tests
@pytest.fixture
def mock_db():
    """In-memory MongoDB mock for fast testing"""
    import mongomock
    return mongomock.MongoClient().test_db

# Real database for integration tests (isolated)
@pytest.fixture
async def mongodb_container():
    """Real MongoDB in Docker for integration tests"""
    import testcontainers.mongodb
    container = testcontainers.mongodb.MongoDbContainer()
    with container:
        yield container.get_connection_client()

# Mock Redis
@pytest.fixture
def mock_redis():
    """In-memory Redis mock"""
    import fakeredis
    return fakeredis.FakeStrictRedis()

# FastAPI test client
@pytest.fixture
async def test_client():
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac

# Session ID fixture
@pytest.fixture
def session_id():
    return "test_session_12345"

# User fixture
@pytest.fixture
def test_user():
    return {
        "id": "user_test_123",
        "email": "test@example.com",
        "name": "Test User"
    }
```

### Coverage Reporting

```bash
# Generate HTML coverage report
python -m pytest backend/tests/unit --cov=app \
  --cov-report=html:coverage_report \
  --cov-report=term

# View report
open coverage_report/index.html

# Check coverage for specific module
python -m pytest backend/tests --cov=app.services.cart_service --cov-report=term-missing
```

**Coverage Requirements:**
- Minimum: 80% overall
- Critical paths (auth, cart, orders): 90%+
- Infrastructure (logging, migrations): 60%+

---

## Frontend Testing

### Unit & Component Tests

```bash
# Run all tests
npm --prefix frontend run test

# Run specific test file
npm --prefix frontend run test -- test/components/Cart.test.tsx

# Watch mode (re-run on changes)
npm --prefix frontend run test -- --watch

# Coverage report
npm --prefix frontend run test -- --coverage
```

**Example Component Test:**

```typescript
// frontend/tests/components/Cart.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { Cart } from '@/components/Cart';
import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('Cart Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays empty cart message when no items', () => {
    render(<Cart items={[]} />);
    expect(screen.getByText('Your cart is empty')).toBeInTheDocument();
  });

  it('renders cart items with price', () => {
    const items = [
      { id: '1', name: 'Shoe', price: 89.99, quantity: 1 }
    ];
    render(<Cart items={items} />);
    expect(screen.getByText('Shoe')).toBeInTheDocument();
    expect(screen.getByText('$89.99')).toBeInTheDocument();
  });

  it('calls onRemove when delete button clicked', () => {
    const onRemove = vi.fn();
    const items = [
      { id: '1', name: 'Shoe', price: 89.99, quantity: 1 }
    ];
    render(<Cart items={items} onRemove={onRemove} />);
    
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(onRemove).toHaveBeenCalledWith('1');
  });
});
```

### E2E Tests (Playwright)

```bash
# Run E2E tests
npm --prefix frontend run test:e2e

# Run specific test
npm --prefix frontend run test:e2e -- test/e2e/checkout.spec.ts

# Run in headed mode (see browser)
npm --prefix frontend run test:e2e -- --headed

# Debug failing test
npm --prefix frontend run test:e2e -- --debug
```

**Example E2E Test:**

```typescript
// frontend/tests/e2e/checkout.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Checkout Flow', () => {
  test('guest user checkout', async ({ page }) => {
    // Navigate to product
    await page.goto('http://localhost:5173/products');
    
    // Add item to cart
    await page.click('text=Running Shoes');
    await page.click('button:has-text("Add to Cart")');
    
    // Verify toast
    await expect(page.locator('.toast-success')).toContainText('Added to cart');
    
    // Go to checkout
    await page.click('button:has-text("Checkout")');
    
    // Fill shipping form
    await page.fill('input[name="name"]', 'John Doe');
    await page.fill('input[name="email"]', 'john@example.com');
    await page.fill('input[name="address"]', '123 Main St');
    
    // Submit
    await page.click('button:has-text("Complete Order")');
    
    // Verify success page
    await expect(page).toHaveURL(/\/order\/\d+/);
    await expect(page.locator('h1')).toContainText('Order Confirmed');
  });
});
```

---

## Performance Testing

### Backend Performance Tests

```bash
# Run performance tests (measures response times, throughput)
python -m pytest backend/tests -k "perf" -v

# Load test with Locust (5 users, 10 requests/sec)
python -m locust -f backend/perf/locustfile.py \
  --host http://localhost:8000 \
  -u 5 \
  -r 1 \
  -t 60s
```

**Example Performance Test:**

```python
# backend/tests/perf_tests.py
import pytest
import time
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_cart_performance(client, session_id):
    """Cart retrieval must respond in < 100ms"""
    start = time.time()
    response = await client.get(
        "/api/cart",
        headers={"X-Session-ID": session_id}
    )
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 0.1, f"GetCart took {duration:.3f}s, must be < 0.1s"
```

### Frontend Performance Tests

```bash
# Lighthouse audit
npm --prefix frontend run lighthouse

# Bundle size analysis
npm --prefix frontend run analyze

# Performance profiling
npm --prefix frontend run build && npm --prefix frontend run profile
```

---

## Continuous Integration

### Local CI Validation

```bash
# From repo root: Full validation gate
powershell scripts/validate_local.ps1

# Or skip expensive tests
powershell scripts/validate_local.ps1 -SkipE2E -SkipPerf
```

**Steps in validation script:**
1. **Backend lint:** `pylint backend/app`
2. **Backend unit tests:** `pytest backend/tests/unit --cov=app --cov-fail-under=80`
3. **Backend integration tests:** `pytest backend/tests/integration`
4. **Frontend lint:** `npm lint`
5. **Frontend unit tests:** `npm test -- --coverage`
6. **Frontend build:** `npm run build`
7. **E2E tests:** `npm run test:e2e` (optional with `-SkipE2E`)
8. **Performance tests:** (optional with `-SkipPerf`)

---

## Test Configuration Files

### Backend (pytest.ini)

```ini
# backend/pytest.ini
[pytest]
asyncio_mode = auto
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --tb=short
    -ra
testpaths = backend/tests
markers =
    asyncio: async test
    integration: integration test
    ai_e2e: AI end-to-end test
    perf: performance test
```

### Frontend (vitest.config.ts)

```typescript
// frontend/vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.d.ts'
      ],
      lines: 80,
      functions: 80,
      branches: 75,
      statements: 80
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
});
```

---

## Debugging Failed Tests

### Backend Test Debugging

```bash
# Show print statements + exceptions
python -m pytest backend/tests/unit -s --tb=long

# Drop into pdb on failure
python -m pytest backend/tests/unit --pdb

# Run with verbose logging
LOG_LEVEL=DEBUG python -m pytest backend/tests/unit -v

# Capture logs
python -m pytest backend/tests/unit --log-cli-level=DEBUG
```

**Debugging async issues:**
```python
# Add to test to inspect event loop
import asyncio

@pytest.mark.asyncio
async def test_something():
    loop = asyncio.get_event_loop()
    print(f"Loop running: {loop.is_running()}")
    print(f"Active tasks: {len(asyncio.all_tasks())}")
    # ... test code ...
```

### Frontend Test Debugging

```bash
# Run with full error output
npm --prefix frontend run test -- --reporter=verbose

# Debug in browser (Playwright)
npm --prefix frontend run test:e2e -- --debug

# Save trace for failed tests
npm --prefix frontend run test:e2e -- --trace=retain-on-failure
```

---

## Test Data & Mocking

### Data Fixtures

```python
# backend/tests/fixtures.py
import pytest

MOCK_PRODUCTS = [
    {
        "id": "prod_shoe_001",
        "name": "Running Shoe",
        "price": 89.99,
        "stock": 100,
        "variants": [
            {"id": "var_red_m", "color": "Red", "size": "M"},
            {"id": "var_blue_l", "color": "Blue", "size": "L"}
        ]
    }
]

MOCK_USER = {
    "id": "user_test_001",
    "email": "test@example.com",
    "password": "hashed_pwd_123"
}

@pytest.fixture
def mock_products():
    return MOCK_PRODUCTS

@pytest.fixture
def mock_user():
    return MOCK_USER
```

### Mocking HTTP Calls

```python
# Mock external API calls
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_payment_processing(mocker):
    # Mock payment API
    mock_payment = mocker.patch(
        'app.infrastructure.payment_client.charge',
        AsyncMock(return_value={"status": "success", "txn_id": "txn_123"})
    )
    
    result = await process_payment(order_id="order_123", amount=99.99)
    
    assert result["status"] == "success"
    mock_payment.assert_called_once()
```

---

## Quick Checklist: Test Readiness

- [ ] Backend unit tests pass: `pytest backend/tests/unit -q`
- [ ] Backend coverage ≥80%: `pytest backend/tests --cov=app --cov-report=term --cov-fail-under=80`
- [ ] Backend integration tests pass: `pytest backend/tests/integration -q`
- [ ] Frontend unit tests pass: `npm --prefix frontend run test`
- [ ] Frontend lint passes: `npm --prefix frontend run lint`
- [ ] E2E tests pass: `npm --prefix frontend run test:e2e` (or skip if time-constrained)
- [ ] No test warnings/errors in logs
- [ ] Test data fixtures set up correctly
- [ ] Environment variables configured (`.env` files)
- [ ] CI validation script passes: `powershell scripts/validate_local.ps1`


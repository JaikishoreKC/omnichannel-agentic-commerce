# Testing Strategy

Last updated: 2026-03-07

## Current Validation Snapshot

- Latest backend full-suite run: `244 passed, 11 skipped`.
- Recently added high-signal hardening tests:
  - `backend/tests/unit/test_inventory_service_concurrency.py`
  - `backend/tests/unit/test_rate_limiting_middleware.py`
  - `backend/tests/integration/test_order_idempotency_concurrency.py`
- Newly added intent/orchestrator quality tests:
  - `backend/tests/unit/test_intent_classifier_thresholds.py`
  - `backend/tests/unit/test_orchestrator_policies.py`
  - `backend/tests/nl_eval/metrics_helper.py` diagnostics integrated into NL eval suites

This document outlines the comprehensive testing strategy for the omnichannel agentic commerce platform.

## Testing Philosophy

Our testing approach follows the principle of "shift left" - catching defects early in the development cycle. We believe in:

- **Fast feedback**: Tests should run quickly to provide rapid feedback
- **Reliability**: Flaky tests erode trust; we prioritize deterministic tests
- **Coverage**: High coverage doesn't mean good testing; we focus on meaningful coverage
- **Maintenance**: Test code is production code and should be maintained with equal rigor

## Testing Pyramid

```
                    ┌─────────────┐
                    │     E2E     │  5%
                   │   Tests     │
                  └──────┬──────┘
                ┌────────┴────────┐
                │  Integration   │  15%
                │    Tests       │
               └───────┬─────────┘
           ┌───────────┴───────────┐
           │     Unit Tests       │  80%
           └───────────────────────┘
```

### Distribution Guidelines

| Layer | Percentage | Execution Time | When to Run |
|-------|------------|----------------|-------------|
| Unit Tests | 70-80% | < 5 minutes | Every commit |
| Integration Tests | 15-20% | < 15 minutes | Every PR |
| E2E Tests | 5-10% | < 1 hour | Before release |

## Unit Testing Guidelines

### Purpose

Unit tests verify the smallest testable parts of the application in isolation. They should be fast, deterministic, and focused on a single behavior.

### Naming Conventions

```
# Format: test_<module>_<method>_<scenario>_<expected>
test_cart_service_add_item_success
test_cart_service_add_item_out_of_stock
test_order_processor_calculate_total_with_discount
test_auth_service_validate_token_expired
```

### Unit Test Structure

```python
# Using AAA (Arrange-Act-Assert) pattern
class TestCartService:
    """Tests for CartService"""
    
    def test_add_item_success(self):
        # Arrange
        cart_service = CartService(mock_repository, mock_inventory)
        user_id = "user_123"
        product_id = "prod_456"
        quantity = 2
        
        mock_inventory.check_availability.return_value = True
        mock_repository.get.return_value = Cart(id="cart_1", items=[])
        
        # Act
        result = cart_service.add_item(user_id, product_id, quantity)
        
        # Assert
        assert result.success is True
        assert result.cart.items[0].product_id == product_id
        assert result.cart.items[0].quantity == quantity
        mock_repository.save.assert_called_once()
```

### Unit Test Coverage Requirements

| Category | Minimum Coverage | Critical Areas |
|----------|-----------------|----------------|
| Services | 80% | Cart, Order, Auth |
| Orchestrator | 90% | Intent classification, Action extraction |
| Models | 70% | Validation, Serialization |
| Utilities | 85% | Security, Formatting |

### Mocking Guidelines

- **Mock external dependencies**: Database, cache, external APIs
- **Don't mock value objects**: Test with real simple objects
- **Use spies sparingly**: Prefer explicit setup over verification
- **Limit mock complexity**: If a mock has >5 expectations, reconsider the test

## Integration Testing

### Purpose

Integration tests verify that components work correctly together. They test the boundaries of modules and ensure data flows correctly through the system.

### Integration Test Categories

#### Database Integration

```python
@pytest.fixture
def test_db():
    """Create test database with sample data"""
    db = TestDatabase()
    db.reset()
    db.seed(sample_data)
    yield db
    db.cleanup()

class TestProductRepository:
    """Product repository integration tests"""
    
    async def test_find_by_category_returns_filtered_results(self, test_db):
        # Arrange
        repo = ProductRepository(test_db)
        
        # Act
        results = await repo.find_by_category("electronics")
        
        # Assert
        assert len(results) == 5
        assert all(p.category == "electronics" for p in results)
```

#### API Integration

```python
class TestCartAPI:
    """Cart API endpoint tests"""
    
    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test_token"}
    
    async def test_add_to_cart_requires_auth(self, client):
        response = await client.post(
            "/v1/cart/items",
            json={"productId": "prod_1", "quantity": 1}
        )
        assert response.status_code == 401
    
    async def test_add_to_cart_success(self, client, auth_headers, test_db):
        response = await client.post(
            "/v1/cart/items",
            json={"productId": "prod_1", "quantity": 1},
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["items"][0]["productId"] == "prod_1"
```

#### Service Integration

```python
class TestCheckoutFlow:
    """End-to-end checkout flow tests"""
    
    async def test_complete_checkout_flow(self):
        # Test the entire flow: cart → order → payment → confirmation
        cart = await cart_service.get_cart(user_id)
        
        # Calculate totals
        totals = await checkout_service.calculate_totals(cart)
        
        # Process payment
        payment = await payment_service.process(
            totals.total,
            payment_method="card"
        )
        
        # Create order
        order = await order_service.create_from_cart(cart, payment)
        
        # Verify
        assert order.status == "confirmed"
        assert order.total == totals.total
```

### Integration Test Best Practices

1. **Use real databases**: Test against real MongoDB, not mocks
2. **Isolate test data**: Each test should have clean data
3. **Clean up after tests**: Never leave test data in the database
4. **Use transactions**: Wrap tests in transactions for rollback
5. **Test failure scenarios**: Don't just test happy paths

## E2E Testing

### Purpose

End-to-end tests verify the complete user journey from the UI perspective. They ensure the system works as a whole and catch issues that unit/integration tests might miss.

### E2E Test Structure

```typescript
// Using Playwright
import { test, expect } from '@playwright/test';

test.describe('Shopping Flow', () => {
  test('complete purchase journey', async ({ page }) => {
    // 1. Navigate to homepage
    await page.goto('https://app.example.com');
    
    // 2. Search for product
    await page.fill('[data-testid="search-input"]', 'laptop');
    await page.click('[data-testid="search-button"]');
    
    // 3. Select product
    await page.click('[data-testid="product-card"]:first-child');
    await expect(page).toHaveURL(/.*\/product\/.*/);
    
    // 4. Add to cart
    await page.click('[data-testid="add-to-cart"]');
    await expect(page.locator('.cart-count')).toHaveText('1');
    
    // 5. Checkout
    await page.click('[data-testid="checkout-button"]');
    await page.fill('[data-testid="card-number"]', '4242424242424242');
    await page.fill('[data-testid="expiry"]', '12/25');
    await page.fill('[data-testid="cvv"]', '123');
    await page.click('[data-testid="place-order"]');
    
    // 6. Verify confirmation
    await expect(page.locator('.order-confirmation')).toBeVisible();
    await expect(page.locator('.order-number')).toHaveText(/ORD-\d+/);
  });
});
```

### Critical User Journeys

| Priority | Journey | Test Frequency |
|----------|---------|----------------|
| P0 | Complete purchase flow | Every deployment |
| P0 | User authentication | Every deployment |
| P0 | Cart management | Every deployment |
| P1 | Product search and browse | Daily |
| P1 | Order history and tracking | Daily |
| P1 | User profile management | Daily |
| P2 | Admin product management | Weekly |
| P2 | Agent assistance flow | Weekly |

### E2E Test Configuration

```typescript
// playwright.config.ts
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'https://app.example.com',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
    {
      name: 'firefox',
      use: { browserName: 'firefox' },
    },
    {
      name: 'mobile',
      use: {
        browserName: 'chromium',
        deviceScaleFactor: 2,
        isMobile: true,
        viewport: { width: 375, height: 812 },
      },
    },
  ],
});
```

## Performance Testing

### Performance Test Categories

#### Load Testing

```python
# Load test using Locust
from locust import HttpUser, task, between

class ShoppingUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def browse_products(self):
        self.client.get("/v1/products")
    
    @task(2)
    def search_products(self):
        self.client.get("/v1/products?query=laptop")
    
    @task(1)
    def add_to_cart(self):
        self.client.post("/v1/cart/items", json={
            "productId": "prod_1",
            "quantity": 1
        })
```

#### Stress Testing

- Gradually increase load until system breaks
- Identify failure points and bottlenecks
- Verify auto-scaling behavior
- Test graceful degradation

#### Spike Testing

- Sudden increase in load (10x normal)
- Verify system handles burst traffic
- Test cache effectiveness
- Verify rate limiting behavior

#### Endurance Testing

- Sustained load over extended period (24+ hours)
- Detect memory leaks
- Verify connection pool behavior
- Check log rotation

### Performance Benchmarks

| Metric | Target | Threshold |
|--------|--------|-----------|
| API Response Time (p50) | < 100ms | 200ms |
| API Response Time (p95) | < 300ms | 500ms |
| API Response Time (p99) | < 500ms | 1000ms |
| Page Load Time | < 2s | 4s |
| Time to Interactive | < 3s | 5s |
| Throughput (per instance) | 100 rps | 75 rps |
| Error Rate | < 0.1% | 1% |

### Performance Test Scenarios

1. **Normal Load**: 500 concurrent users, 1000 requests/minute
2. **Peak Load**: 2000 concurrent users, 5000 requests/minute
3. **Stress Test**: 5000 concurrent users, gradual increase over 30 minutes
4. **Soak Test**: 1000 concurrent users, 24-hour duration

## Security Testing

### Security Test Categories

#### Static Application Security Testing (SAST)

- **Tool**: SonarQube, Bandit
- **Frequency**: Every commit
- **Checks**:
  - SQL injection vulnerabilities
  - XSS vulnerabilities
  - Hardcoded credentials
  - Insecure dependencies

#### Dynamic Application Security Testing (DAST)

- **Tool**: OWASP ZAP, Burp Suite
- **Frequency**: Weekly + before release
- **Checks**:
  - Authentication bypass
  - Authorization flaws
  - Input validation
  - Session management

#### Penetration Testing

- **Frequency**: Quarterly + before major release
- **Scope**: Full application + API
- **Deliverables**: Security report with remediation plan

#### Vulnerability Scanning

- **Tool**: Snyk, Dependabot
- **Frequency**: Daily
- **Checks**: Known vulnerabilities in dependencies

### Security Test Cases

```python
class TestAuthenticationSecurity:
    """Security tests for authentication"""
    
    def test_password_not_returned_in_response(self, client):
        response = client.post("/v1/auth/login", json={
            "email": "user@example.com",
            "password": "password123"
        })
        assert "password" not in response.json()
    
    def test_sql_injection_in_login(self, client):
        response = client.post("/v1/auth/login", json={
            "email": "' OR '1'='1",
            "password": "anything"
        })
        assert response.status_code == 401
    
    def test_brute_force_protection(self, client):
        for _ in range(10):
            response = client.post("/v1/auth/login", json={
                "email": "user@example.com",
                "password": "wrongpassword"
            })
        # Should be rate limited
        assert response.status_code == 429
```

## Test Coverage Targets

### Coverage Goals

| Category | Target | Minimum |
|----------|--------|---------|
| Overall Coverage | 80% | 70% |
| Business Logic | 90% | 85% |
| API Endpoints | 95% | 90% |
| Security Functions | 100% | 95% |
| Error Handling | 80% | 70% |

### Coverage Enforcement

- **CI Pipeline**: Block merge if coverage drops > 5%
- **Code Review**: Coverage decrease requires justification
- **New Code**: New modules require 80% coverage

## Testing Tools

### Testing Framework Stack

| Layer | Tool | Language |
|-------|------|----------|
| Unit Testing | pytest | Python |
| API Testing | httpx + pytest | Python |
| E2E Testing | Playwright | TypeScript/JavaScript |
| Load Testing | Locust | Python |
| Property Testing | Hypothesis | Python |
| Mutation Testing | mutmut | Python |

### Additional Tools

| Purpose | Tool | Purpose |
|---------|------|---------|
| Mocking | pytest-mock | Python |
| Fixtures | pytest-fixture | Python |
| Code Coverage | coverage.py | Python |
| Static Analysis | mypy, ruff | Python |
| Security Scanning | Bandit, Safety | Python |
| Browser Automation | Playwright | TypeScript |
| API Mocking | MirageJS | JavaScript |

### Test Data Management

```python
# Factory pattern for test data
class UserFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "email": f"user_{uuid4()}@example.com",
            "password": "SecurePass123!",
            "name": "Test User"
        }
        return {**defaults, **kwargs}

# Usage
user = UserFactory.create(name="John Doe")
```

## Continuous Testing

### CI Pipeline Integration

```yaml
# GitHub Actions test workflow
name: Test

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: pytest tests/unit --cov --cov-report=xml
      
  integration-tests:
    runs-on: ubuntu-latest
    services:
      mongodb:
        image: mongo:7.0
      redis:
        image: redis:7-alpine
    steps:
      - uses: actions/checkout@v4
      - name: Run integration tests
        run: pytest tests/integration --tb=short

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: npm ci
      - name: Run E2E tests
        run: npm run test:e2e

  security-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run security scans
        run: |
          npm audit
          pip install bandit safety
          bandit -r backend/app
          safety check
```

### Test Execution Strategy

| Trigger | Tests Run | Time Limit |
|---------|-----------|------------|
| Every Commit | Unit tests | 5 minutes |
| Every PR | Unit + Integration | 20 minutes |
| Nightly | All tests + extended | 2 hours |
| Before Release | Full suite + performance | 4 hours |

## Test Maintenance

### Test Review Checklist

- [ ] Test name clearly describes what it tests
- [ ] Test follows AAA pattern
- [ ] Test has single responsibility
- [ ] Test is deterministic (no flakiness)
- [ ] Test documents expected behavior
- [ ] Test includes both positive and negative cases
- [ ] Test cleanup is handled properly

### Handling Flaky Tests

1. **Identify**: Track flaky tests over time
2. **Investigate**: Understand root cause
3. **Fix**: Improve test reliability
4. **Monitor**: Track test stability metrics
5. **Quarantine**: If unfixable, mark with `@pytest.mark.flaky`

### Test Code Quality

- Same standards as production code
- Regular refactoring
- Remove dead tests
- Update tests with requirements
- Document complex test scenarios

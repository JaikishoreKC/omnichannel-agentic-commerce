# analysis_backend_logic

## Business Logic Validation
- Cart lifecycle: add/update/remove/discount/merge in `cart_service.py`.
- Checkout lifecycle: idempotency, reservation, payment, persistence, notification in `order_service.py`.
- Auth lifecycle: register/login/refresh rotation/profile update in `auth_service.py`.
- Memory lifecycle: preference updates/history/affinity scoring in `memory_service.py`.

## Service-Layer Mutation Rule
- DB writes occur in repository methods invoked by services.
- No agent file contains direct Mongo collection write calls.

## Runtime Integrity
- Backend test status after targeted fix: 219 passed, 11 skipped.

# Release Checklist (v1)

Last updated: 2026-03-07

Latest backend baseline: `244 passed, 11 skipped`.

## 1) Quality Gates
- [ ] Backend tests pass: `python -m pytest backend/tests -q`
- [ ] Backend coverage >= 80%: `python -m pytest backend/tests -q --cov=app --cov-fail-under=80`
- [ ] Frontend build passes: `npm --prefix frontend run build`
- [ ] Frontend E2E passes: `npm --prefix frontend run test:e2e`
- [ ] Perf smoke passes: `cd backend && python -m app.scripts.perf_smoke`
- [ ] Concurrency hardening tests pass:
  - [ ] `python -m pytest backend/tests/unit/test_inventory_service_concurrency.py -q`
  - [ ] `python -m pytest backend/tests/integration/test_order_idempotency_concurrency.py -q`
- [ ] Rate-limit identity tests pass:
  - [ ] `python -m pytest backend/tests/unit/test_rate_limiting_middleware.py -q`

## 2) API and Runtime Checks
- [ ] `/health` reports expected service status
- [ ] `/metrics` is scrapeable
- [ ] Core flows manually verified:
  - [ ] guest browse/cart
  - [ ] login/register cart transfer
  - [ ] authenticated checkout
  - [ ] refund request
  - [ ] shipping address update before shipment
  - [ ] websocket chat (response + streaming + typing + ping/pong)

## 3) Deployment and Observability
- [ ] Docker image build succeeds
- [ ] DB index script run: `python -m app.scripts.create_indexes`
- [ ] Bootstrap script run: `python -m app.scripts.bootstrap_db`
- [ ] Dashboards reachable (Prometheus/Grafana)

## 4) Change Control
- [ ] API contract changes reflected in `docs/API_Contracts.md`
- [ ] README updated for new endpoints/ops commands
- [ ] Migration/rollback notes included in release notes

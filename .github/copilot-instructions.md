# Project Guidelines

## Architecture
- Respect backend dependency direction: api routes -> application workflows -> services -> repositories -> infrastructure.
- Keep route handlers thin. Put business rules in services/workflows, not in route modules.
- Use dependency injection through backend/app/container.py and backend/app/api/deps.py patterns; avoid new global singletons.
- For conversational flows, preserve orchestrator-first behavior (intent classification, action extraction, agent routing, interaction persistence).
- References: docs/ARCHITECTURE.md, docs/REPOSITORY_INTELLIGENCE.md, docs/API_Contracts.md.

## Build and Test
- Backend tests (from repo root): python -m pytest backend/tests -q --cov=app --cov-report=term --cov-fail-under=80.
- Backend targeted suites: python -m pytest backend/tests/unit -q, python -m pytest backend/tests/integration -q, python -m pytest backend/tests/ai_e2e -s.
- Frontend checks: npm --prefix frontend run lint, npm --prefix frontend run build, npm --prefix frontend run test.
- Frontend E2E: npm --prefix frontend run test:e2e (or npm --prefix frontend run test:e2e:headed for local debugging).
- Full local gate: powershell scripts/validate_local.ps1 (use -SkipE2E or -SkipPerf when needed).
- Use docker compose up --build for integrated local stack (backend/frontend/mongo/redis/monitoring).

## Conventions and Pitfalls
- Backend pytest path quirk: from repo root use backend/tests/... paths. Do not use tests/... at root.
- scripts/validate_local.ps1 runs backend tests from inside backend/ using tests/... path; this is expected.
- Copy environment templates before running: backend/.env.example -> backend/.env and frontend/.env.example -> frontend/.env.
- Never commit secrets from .env files (TOKEN_SECRET, OPENROUTER keys, SUPERU keys).
- Docker compose parses ${...} in env values; escape literal templates with $$ (for example VOICE_SCRIPT_TEMPLATE currency placeholders).
- Keep planner safeguards intact: deterministic single-item add_to_cart turns should stay rule-driven; planner is for clearly multi-item phrasing.
- With ENABLE_EXTERNAL_SERVICES=false, verify core persistence flows still work (sessions/orders/cart continuity) using in-memory fallbacks.
- Frontend auth reliability: keep token hydration behavior in frontend/src/api/client.ts (memory + localStorage) when refactoring auth/session logic.
- Keep architecture boundary checks green: backend/tests/unit/test_architecture_boundaries.py validates route/service/repository dependency rules.

## Documentation Links
- Primary overview and setup: README.md.
- Architecture and boundaries: docs/ARCHITECTURE.md and docs/ARCHITECTURE_TARGET_STRUCTURE.md.
- API contracts: docs/API_Contracts.md.
- Security and operational controls: docs/SECURITY.md and docs/OPERATIONAL_RUNBOOK.md.
- Testing standards and coverage expectations: docs/TESTING_STRATEGY.md.
- Data model and index behavior: docs/Database_Schema.md.
- Agent behavior specifics: docs/Agent_Logic_Specs.md.

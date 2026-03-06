# analysis_repo_map

## Root Discovery
- backend/
- frontend/
- docs/
- monitoring/
- scripts/
- tmp/

## Subsystem Identification
- Conversational commerce backend (FastAPI + orchestrator + agents + services + repositories)
- React frontend (routes + contexts + API clients + chat UX)
- Monitoring stack (Prometheus/Grafana)
- Documentation corpus under docs/

## Documentation Reconstruction (from /docs)
- Architecture layers and dependency direction defined in `docs/ARCHITECTURE.md`.
- API contract and error envelope in `docs/API_Contracts.txt`.
- Security controls and guardrails in `docs/SECURITY.txt`.
- Testing strategy and gates in `docs/TESTING_STRATEGY.txt` + `docs/RELEASE_CHECKLIST.txt`.

## Architecture Model
- API Routes -> Application workflows -> Services -> Repositories -> Infra/Persistence.
- Orchestrator -> Agents -> Services.
- DB mutation should occur via services/repositories only.

## Docs vs Implementation Discrepancies
- MFA env var naming mismatch was resolved: `docs/SECURITY.txt` now references `ADMIN_MFA_TOTP_SECRET`, matching `backend/app/core/config.py` and `backend/app/services/auth_service.py`.
- `docs/Agent_Logic_Specs.txt` describes broader lifecycle semantics than implemented in `backend/app/agents/base_agent.py`.

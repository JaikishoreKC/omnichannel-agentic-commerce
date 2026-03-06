# analysis_module_notes

## Backend Modules
- api/routes: request contracts, auth/session resolution, endpoint orchestration.
- application: session and identity linking workflows.
- orchestrator: intent classification, action extraction, planning, routing, response formatting.
- agents: domain action execution adapters.
- services: business policy and validation.
- repositories: Mongo/Redis/in-memory persistence adapters.
- infrastructure: external integrations and reliability controls.

## Frontend Modules
- api/: HTTP/WS clients and auth/session transport concerns.
- context/: Session/Auth/Cart/Chat global state.
- pages/components: conversational commerce UI and admin UI.

## File-by-File Analysis Approach
- Complete inventory captured in `analysis_file_inventory.md`.
- Deep logic review focused on runtime-critical executable files:
  - `backend/app/main.py`
  - `backend/app/container.py`
  - `backend/app/orchestrator/orchestrator_core.py`
  - `backend/app/orchestrator/intent_classifier.py`
  - `backend/app/agents/*.py`
  - `backend/app/services/*.py`
  - `backend/app/repositories/*.py`
  - `frontend/src/api/client.ts`
  - `frontend/src/context/ChatContext.tsx`

## Potential Issues Identified
1. Planner eligibility edge case for phrase `add items to cart` prevented planner metadata in atomic-mode test.
2. Security doc MFA variable drift (`STATIC_CODE` vs TOTP secret) was corrected in `docs/SECURITY.txt`.

## Technical Debt Analysis
- No explicit `TODO`/`FIXME`/`HACK` markers were found in scanned backend/frontend source trees.
- Structural debt remains concentrated in high-fanout modules:
  - `backend/app/container.py`
  - `backend/app/orchestrator/orchestrator_core.py`
- Test trace artifacts under `backend/tests/ai_e2e/traces/` are large and can increase repo noise/churn.

## Feature Gap Analysis
- From docs-vs-implementation comparison, the primary remaining gap is scope richness in `docs/Agent_Logic_Specs.txt` versus practical behavior in `backend/app/agents/base_agent.py` and concrete agents.
- Core commerce assistant flows documented in architecture/contracts are implemented and covered by tests (search, cart, checkout, order status, session continuity).

## Cross-Review
- AI Orchestration Engineer: confirms planner edge case.
- QA/Reliability Engineer: confirms failing integration test reproduced pre-fix.

# analysis_dependency_graph

## Core Dependency Graph
- routes -> deps/application/services/orchestrator
- application -> session_service/cart_service/auth_service
- orchestrator -> intent_classifier/context_builder/action_extractor/agent_router/agents
- agents -> services
- services -> repositories
- repositories -> persistence_clients (Mongo/Redis) + in_memory store

## Critical Chains
- `/v1/interactions/message` -> session_workflows -> orchestrator -> agents -> services -> repositories
- `/ws` -> session_workflows -> orchestrator stream -> agents/services
- `/v1/orders` -> order_service -> inventory/payment/notification/order_repo

## Coupling Hotspots
- `backend/app/container.py`
- `backend/app/orchestrator/orchestrator_core.py`
- `backend/app/services/voice_recovery_service.py`
- `backend/app/api/routes/admin_routes.py`

## Circular Dependency Check
- No explicit circular import failures observed during full backend test run.

## Cross-Review
- System Architect: no boundary-breaking dependency shifts found.
- Performance Engineer: notes orchestrator and voice service as high-fanout paths.

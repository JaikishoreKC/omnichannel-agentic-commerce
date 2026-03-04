# Target Architecture Structure and Migration Plan

Date: 2026-03-05
Scope: backend + frontend architectural boundary hardening

## Target Layer Model

1. Interface Layer
- `backend/app/api/routes/*`
- `backend/app/api/deps.py`
- `backend/app/middleware/*`

2. Application Layer (use-case orchestration)
- `backend/app/application/*`
- Owns multi-service workflows (session merge, interaction history synthesis, admin orchestration flows)

3. Domain Services
- `backend/app/services/*`
- Pure business policies, no transport concerns

4. Data Access Layer
- `backend/app/repositories/*`
- Persistence adapters only

5. Infrastructure Layer
- `backend/app/infrastructure/*`
- External providers, observability, resilience patterns

## Target Package Layout (Incremental)

```text
backend/app/
  api/
    deps.py
    routes/
  application/
    __init__.py
    session_workflows.py
    interaction_workflows.py
  services/
  repositories/
  infrastructure/
  orchestrator/
  agents/
```

## Dependency Rules

Allowed direction:
- `api -> application -> services -> repositories -> infrastructure`
- `orchestrator -> agents/services`

Disallowed direction:
- `api/routes -> container` direct imports
- `api/routes -> repositories` direct imports
- `services -> api`

## Migration Sequence (PR slices)

1. Introduce provider functions in `api/deps.py` for all route/middleware dependencies.
2. Migrate routes/middleware from `from app.container import ...` to provider-backed injection.
3. Move API workflow glue into `application` package.
4. Add architecture guard tests to enforce import boundaries.
5. Continue extracting large UI page orchestration into feature hooks/components.

## Delivered in This Pass

- Provider-backed route/middleware dependency boundary hardening.
- Initial `application` layer extracted for session/interaction workflows.
- Architecture guard tests for import boundary regressions.

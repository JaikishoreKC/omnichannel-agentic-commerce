# Platform Analysis Report (Non-backend/frontend tracked files)

- Total scoped tracked files: 25
- Scope check `.github`: present
- Scope check `.vscode`: present
- Scope check `docs`: present
- Scope check `monitoring`: present
- Scope check `scripts`: present
- Scope check `tmp`: present

## Findings by file

### .github/workflows/ci.yml
- Purpose: CI pipeline definition for lint/test/build quality gates.
- Dependencies: backend, frontend, mongo, pytest, playwright, backend/requirements.txt, perf-smoke-summary.json, backend/perf-smoke-summary.json
- Architecture placement: PASS: CI/CD workflow file placed in standard GitHub Actions path.
- Issues/risk patterns: Environment-specific host binding/reference present. | Uses latest-tag style dependency pinning; may reduce reproducibility.

### .gitignore
- Purpose: VCS hygiene rules to exclude build artifacts, secrets, and local state.
- Dependencies: backend, playwright, backend/perf-smoke-summary.json
- Architecture placement: PASS: Repository-level control file placed at project root.
- Issues/risk patterns: No notable static risk pattern detected.

### .vscode/extensions.json
- Purpose: Recommended VS Code extensions for consistent contributor tooling.
- Dependencies: playwright
- Architecture placement: PASS: Developer IDE workspace settings in expected .vscode/ scope.
- Issues/risk patterns: No notable static risk pattern detected.

### .vscode/settings.json
- Purpose: Workspace IDE settings to standardize formatting and editor behavior.
- Dependencies: typescript.ts
- Architecture placement: PASS: Developer IDE workspace settings in expected .vscode/ scope.
- Issues/risk patterns: No notable static risk pattern detected.

### README.md
- Purpose: Primary onboarding and runbook entrypoint for repository usage.
- Dependencies: backend, frontend, mongo, redis, prometheus, grafana, pytest, playwright
- Architecture placement: PASS: Repository-level control file placed at project root.
- Issues/risk patterns: Environment-specific host binding/reference present.

### docker-compose.yml
- Purpose: Local multi-service orchestration for app + observability stack.
- Dependencies: backend, frontend, mongo, redis, prometheus, grafana, uvicorn, /etc/prometheus/prometheus.yml
- Architecture placement: PASS: Repository-level control file placed at project root.
- Issues/risk patterns: Environment-specific host binding/reference present.

### docs/API_Contracts.txt
- Purpose: Design/operational documentation for API Contracts.
- Dependencies: http://localhost:8000/v1`
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: Environment-specific host binding/reference present.

### docs/Agent_Logic_Specs.txt
- Purpose: Design/operational documentation for Agent Logic Specs.
- Dependencies: none explicit
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/Database_Schema.txt
- Purpose: Design/operational documentation for Database Schema.
- Dependencies: redis
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/RELEASE_CHECKLIST.txt
- Purpose: Design/operational documentation for RELEASE CHECKLIST.
- Dependencies: backend, frontend, prometheus, grafana, pytest, docker, docs/API_Contracts.txt
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/SECURITY.txt
- Purpose: Design/operational documentation for SECURITY.
- Dependencies: backend, backend/app/core/security.py, backend/app/services/auth_service.py, backend/app/core/config.py, backend/app/api/deps.py, backend/app/api/routes/admin_routes.py
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/TESTING_STRATEGY.txt
- Purpose: Design/operational documentation for TESTING STRATEGY.
- Dependencies: locust, backend, mongo, redis, pytest, playwright, response.json, playwright.config.ts
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/architecture.txt
- Purpose: Design/operational documentation for architecture.
- Dependencies: backend, frontend, mongo, redis, prometheus, fastapi, frontend/src/App.ts
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/idea.txt
- Purpose: Design/operational documentation for idea.
- Dependencies: backend, frontend, redis, docker, fastapi, uvicorn
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/implementation_blueprint.txt
- Purpose: Design/operational documentation for implementation blueprint.
- Dependencies: backend, frontend, mongo, redis, pytest, playwright, docker, compose
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/prd.txt
- Purpose: Design/operational documentation for prd.
- Dependencies: backend, frontend, prometheus
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### docs/sdd.txt
- Purpose: Design/operational documentation for sdd.
- Dependencies: backend, frontend, mongo, redis, prometheus, playwright, fastapi, backend/app/main.py
- Architecture placement: PASS: Architecture and process docs correctly isolated under docs/.
- Issues/risk patterns: No notable static risk pattern detected.

### monitoring/grafana/dashboards/commerce-overview.json
- Purpose: Grafana dashboard model for commerce/agent health monitoring.
- Dependencies: prometheus, grafana
- Architecture placement: PASS: Observability assets correctly isolated under monitoring/.
- Issues/risk patterns: Dashboard tightly coupled to datasource naming; verify env consistency.

### monitoring/grafana/provisioning/dashboards/dashboards.yml
- Purpose: Grafana dashboard auto-provisioning configuration.
- Dependencies: grafana
- Architecture placement: PASS: Observability assets correctly isolated under monitoring/.
- Issues/risk patterns: No notable static risk pattern detected.

### monitoring/grafana/provisioning/datasources/datasource.yml
- Purpose: Grafana datasource provisioning for dashboards.
- Dependencies: prometheus, http://prometheus:9090
- Architecture placement: PASS: Observability assets correctly isolated under monitoring/.
- Issues/risk patterns: No notable static risk pattern detected.

### monitoring/prometheus.yml
- Purpose: Prometheus scrape and rule configuration for metrics collection.
- Dependencies: backend
- Architecture placement: PASS: Observability assets correctly isolated under monitoring/.
- Issues/risk patterns: No notable static risk pattern detected.

### scripts/validate_local.ps1
- Purpose: Local environment validation automation for pre-flight checks.
- Dependencies: backend, frontend, pytest
- Architecture placement: PASS: Reusable local automation script correctly under scripts/.
- Issues/risk patterns: No notable static risk pattern detected.

### tmp/check_orders.py
- Purpose: Ad-hoc operational/diagnostic utility script (check_orders).
- Dependencies: os, pymongo, dotenv, backend, mongo
- Architecture placement: WARN: Tracked ad-hoc script in tmp/ can indicate drift from production code boundaries.
- Issues/risk patterns: Environment-specific host binding/reference present. | Temporary script is tracked; can bypass review rigor if reused operationally.

### tmp/check_products.py
- Purpose: Ad-hoc operational/diagnostic utility script (check_products).
- Dependencies: os, pymongo, dotenv, backend, mongo
- Architecture placement: WARN: Tracked ad-hoc script in tmp/ can indicate drift from production code boundaries.
- Issues/risk patterns: Environment-specific host binding/reference present. | Temporary script is tracked; can bypass review rigor if reused operationally.

### tmp/seed_products.py
- Purpose: Ad-hoc operational/diagnostic utility script (seed_products).
- Dependencies: os, random, uuid, datetime, pymongo, dotenv, backend, https://placehold.co/600x800?text={name.replace(
- Architecture placement: WARN: Tracked ad-hoc script in tmp/ can indicate drift from production code boundaries.
- Issues/risk patterns: Environment-specific host binding/reference present. | Temporary script is tracked; can bypass review rigor if reused operationally.

## Aggregate summary
- ad-hoc-ops: 3
- ci-cd: 1
- dev-automation: 1
- developer-tooling: 2
- documentation: 11
- observability: 4
- platform-orchestration: 1
- project-meta: 2
- Placement warnings: 3 (tracked tmp scripts)
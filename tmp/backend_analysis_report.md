Tracked backend files: 148 (Python modules: 143)

## Graph findings
- Layer edges (top 12): [{'from': 'test', 'to': 'composition-root', 'count': 27}, {'from': 'service', 'to': 'repository', 'count': 26}, {'from': 'service', 'to': 'core', 'count': 20}, {'from': 'test', 'to': 'repository', 'count': 20}, {'from': 'composition-root', 'to': 'service', 'count': 15}, {'from': 'test', 'to': 'infrastructure', 'count': 15}, {'from': 'composition-root', 'to': 'repository', 'count': 13}, {'from': 'repository', 'to': 'infrastructure', 'count': 13}, {'from': 'orchestrator', 'to': 'orchestrator', 'count': 11}, {'from': 'api-route', 'to': 'composition-root', 'count': 10}, {'from': 'composition-root', 'to': 'api-route', 'count': 10}, {'from': 'api-route', 'to': 'model', 'count': 8}]
- Detected cycles: 8
  - app.container -> app.services.admin_activity_service -> app.container
  - app.repositories.cart_repository -> app.container -> app.repositories.cart_repository
  - app.repositories.cart_repository -> app.container -> app.services.voice_recovery_service -> app.repositories.cart_repository
  - app.container -> app.services.voice_recovery_service -> app.repositories.voice_repository -> app.container
  - app.services.cart_service -> app.repositories.cart_repository -> app.container -> app.services.cart_service
  - app.agents.cart_agent -> app.services.cart_service -> app.repositories.cart_repository -> app.container -> app.agents.cart_agent
  - app.services.cart_service -> app.repositories.cart_repository -> app.container -> app.agents.order_agent -> app.services.order_service -> app.services.cart_service
  - app.services.cart_service -> app.repositories.cart_repository -> app.container -> app.orchestrator.orchestrator_core -> app.orchestrator.context_builder -> app.services.cart_service
- High fan-out files: ['backend/app/container.py', 'backend/tests/unit/test_repositories.py', 'backend/app/main.py', 'backend/app/orchestrator/orchestrator_core.py', 'backend/app/services/voice_recovery_service.py', 'backend/tests/unit/test_voice_recovery_service.py', 'backend/app/services/voice/jobs.py', 'backend/app/services/admin_service.py', 'backend/app/services/order_service.py', 'backend/tests/unit/test_repository_fallbacks.py', 'backend/app/services/auth_service.py', 'backend/tests/unit/test_admin_activity_service.py']
- Duplicate stems: {}

### backend/.env.example
- Purpose/layer: Environment variable template [other]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/Dockerfile
- Purpose/layer: Container image build definition [other]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/__init__.py
- Purpose/layer: Omnichannel Agentic Commerce backend package. [other]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/agents/__init__.py
- Purpose/layer: Domain-specific agent implementations. [agent]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/agents/base_agent.py
- Purpose/layer: Module implementation [agent]
- Key symbols: BaseAgent; direct internal deps: app.orchestrator.types
- Risks/validation: none notable

### backend/app/agents/cart_agent.py
- Purpose/layer: Module implementation [agent]
- Key symbols: _AddResolution, CartAgent; direct internal deps: app.agents.base_agent, app.orchestrator.types, app.services.cart_service, app.services.product_service
- Risks/validation: broad_exception_handling, placeholder_pass

### backend/app/agents/general_agent.py
- Purpose/layer: Module implementation [agent]
- Key symbols: GeneralAgent; direct internal deps: app.agents.base_agent, app.infrastructure.llm_client, app.orchestrator.types
- Risks/validation: broad_exception_handling

### backend/app/agents/memory_agent.py
- Purpose/layer: Module implementation [agent]
- Key symbols: MemoryAgent; direct internal deps: app.agents.base_agent, app.orchestrator.types, app.services.memory_service
- Risks/validation: none notable

### backend/app/agents/order_agent.py
- Purpose/layer: Module implementation [agent]
- Key symbols: OrderAgent; direct internal deps: app.agents.base_agent, app.orchestrator.types, app.services.order_service
- Risks/validation: none notable

### backend/app/agents/product_agent.py
- Purpose/layer: Module implementation [agent]
- Key symbols: ProductAgent; direct internal deps: app.agents.base_agent, app.orchestrator.types, app.services.product_service
- Risks/validation: none notable

### backend/app/agents/support_agent.py
- Purpose/layer: Module implementation [agent]
- Key symbols: SupportAgent; direct internal deps: app.agents.base_agent, app.orchestrator.types, app.services.support_service
- Risks/validation: none notable

### backend/app/api/__init__.py
- Purpose/layer: API routers and dependencies. [api]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/api/deps.py
- Purpose/layer: Module implementation [api]
- Key symbols: _extract_bearer_token, get_current_user, get_optional_user, require_admin, resolve_session_id; direct internal deps: app.container
- Risks/validation: placeholder_pass

### backend/app/api/routes/__init__.py
- Purpose/layer: Route modules. [api-route]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/api/routes/admin_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: stats, list_orders, list_products, list_users, categories; direct internal deps: app.api.deps, app.container, app.models.schemas
- Risks/validation: none notable

### backend/app/api/routes/auth_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: register, login, refresh, request_password_reset, confirm_password_reset; direct internal deps: app.container, app.models.schemas
- Risks/validation: broad_exception_handling

### backend/app/api/routes/cart_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: get_cart, add_cart_item, update_cart_item, delete_cart_item, apply_discount; direct internal deps: app.api.deps, app.container, app.models.schemas
- Risks/validation: none notable

### backend/app/api/routes/interaction_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: process_message, get_history; direct internal deps: app.api.deps, app.container, app.infrastructure.logging, app.models.schemas
- Risks/validation: broad_exception_handling

### backend/app/api/routes/memory_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: get_memory, get_preferences, update_preferences, get_history, clear_memory; direct internal deps: app.api.deps, app.container, app.models.schemas
- Risks/validation: none notable

### backend/app/api/routes/order_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: create_order, list_orders, get_order, cancel_order, refund_order; direct internal deps: app.api.deps, app.container, app.models.schemas
- Risks/validation: none notable

### backend/app/api/routes/product_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: list_products, get_product, add_product_review; direct internal deps: app.api.deps, app.container, app.models.schemas
- Risks/validation: none notable

### backend/app/api/routes/session_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: create_session, get_session, delete_session; direct internal deps: app.container, app.models.schemas
- Risks/validation: none notable

### backend/app/api/routes/voice_webhook_routes.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: handle_superu_callback; direct internal deps: app.container
- Risks/validation: none notable

### backend/app/api/routes/ws_route.py
- Purpose/layer: Module implementation [api-route]
- Key symbols: _stream_text_chunks, _record_security_event, _send_session_event, _ensure_active_session, _resolve_and_sync_user_session; direct internal deps: app.container, app.infrastructure.logging
- Risks/validation: broad_exception_handling

### backend/app/container.py
- Purpose/layer: Module implementation [composition-root]
- Key symbols: Container; direct internal deps: app.agents.cart_agent, app.agents.general_agent, app.agents.memory_agent, app.agents.order_agent, app.agents.product_agent
- Risks/validation: broad_exception_handling, placeholder_pass

### backend/app/core/__init__.py
- Purpose/layer: Core settings and security helpers. [core]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/core/config.py
- Purpose/layer: Module implementation [core]
- Key symbols: Settings; direct internal deps: none
- Risks/validation: none notable

### backend/app/core/security.py
- Purpose/layer: Module implementation [core]
- Key symbols: hash_password, verify_password, _b64_encode, _b64_decode, _sign; direct internal deps: none
- Risks/validation: none notable

### backend/app/core/utils.py
- Purpose/layer: Module implementation [core]
- Key symbols: utc_now, iso_now, generate_id, default_session_expiry; direct internal deps: none
- Risks/validation: none notable

### backend/app/infrastructure/__init__.py
- Purpose/layer: Infrastructure adapters (MongoDB, Redis, etc.). [infrastructure]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/infrastructure/circuit_breaker.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: CircuitBreakerOpenError, CircuitBreakerSnapshot, CircuitBreaker; direct internal deps: none
- Risks/validation: broad_exception_handling

### backend/app/infrastructure/llm_client.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: LLMIntentPrediction, LLMPlannedAction, LLMActionPlan, LLMClient; direct internal deps: app.core.config, app.infrastructure.circuit_breaker, app.infrastructure.prompts
- Risks/validation: broad_exception_handling, placeholder_pass

### backend/app/infrastructure/logging.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: setup_logging, get_logger; direct internal deps: none
- Risks/validation: none notable

### backend/app/infrastructure/mongo_indexes.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: resolve_database, ensure_mongo_indexes; direct internal deps: none
- Risks/validation: none notable

### backend/app/infrastructure/observability.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: RequestTimer, MetricsCollector; direct internal deps: none
- Risks/validation: none notable

### backend/app/infrastructure/persistence_clients.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: MongoClientManager, RedisClientManager; direct internal deps: none
- Risks/validation: broad_exception_handling, print_statement_in_runtime_code

### backend/app/infrastructure/prompts.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/infrastructure/rate_limiter.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: RateLimitDecision, SlidingWindowRateLimiter; direct internal deps: none
- Risks/validation: none notable

### backend/app/infrastructure/state_persistence.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: StatePersistence; direct internal deps: app.infrastructure.persistence_clients, app.store.in_memory
- Risks/validation: none notable

### backend/app/infrastructure/superu_client.py
- Purpose/layer: Module implementation [infrastructure]
- Key symbols: SuperUClient; direct internal deps: app.core.config
- Risks/validation: broad_exception_handling, print_statement_in_runtime_code

### backend/app/main.py
- Purpose/layer: Module implementation [composition-root]
- Key symbols: ensure_runtime_baseline_data, lifespan, _voice_recovery_scheduler_loop, _error_code, _record_security_event; direct internal deps: app.api.routes.admin_routes, app.api.routes.auth_routes, app.api.routes.cart_routes, app.api.routes.interaction_routes, app.api.routes.memory_routes
- Risks/validation: none notable

### backend/app/middleware/__init__.py
- Purpose/layer: Module implementation [middleware]
- Key symbols: none; direct internal deps: app.metrics, app.rate_limiting, app.request_hardening, app.security_headers
- Risks/validation: layer_violation:app.metrics->other;app.rate_limiting->other;app.request_hardening->other, +1 more

### backend/app/middleware/metrics.py
- Purpose/layer: Module implementation [middleware]
- Key symbols: _rate_limit_scope, _path_group, collect_http_metrics; direct internal deps: app.container, app.infrastructure.observability
- Risks/validation: none notable

### backend/app/middleware/rate_limiting.py
- Purpose/layer: Module implementation [middleware]
- Key symbols: _rate_limit_profile, _rate_limit_scope, _record_security_event, enforce_rate_limits; direct internal deps: app.container
- Risks/validation: none notable

### backend/app/middleware/request_hardening.py
- Purpose/layer: Module implementation [middleware]
- Key symbols: _header_occurrence_count, _request_has_body, _is_mutating_api_request, _record_security_event, enforce_request_hardening; direct internal deps: app.container, app.core.config
- Risks/validation: none notable

### backend/app/middleware/security_headers.py
- Purpose/layer: Module implementation [middleware]
- Key symbols: apply_response_security_headers; direct internal deps: app.core.config
- Risks/validation: none notable

### backend/app/models/__init__.py
- Purpose/layer: Pydantic schemas for API contracts. [model]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/models/schemas.py
- Purpose/layer: Module implementation [model]
- Key symbols: RegisterRequest, LoginRequest, RefreshRequest, PasswordResetRequest, PasswordResetConfirmRequest; direct internal deps: none
- Risks/validation: none notable

### backend/app/orchestrator/__init__.py
- Purpose/layer: Orchestration pipeline for agentic interactions. [orchestrator]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/orchestrator/action_extractor.py
- Purpose/layer: Module implementation [orchestrator]
- Key symbols: ActionExtractor; direct internal deps: app.orchestrator.types
- Risks/validation: none notable

### backend/app/orchestrator/agent_router.py
- Purpose/layer: Module implementation [orchestrator]
- Key symbols: AgentRouter; direct internal deps: app.orchestrator.types
- Risks/validation: none notable

### backend/app/orchestrator/context_builder.py
- Purpose/layer: Module implementation [orchestrator]
- Key symbols: ContextBuilder; direct internal deps: app.orchestrator.types, app.services.cart_service, app.services.memory_service, app.services.session_service
- Risks/validation: none notable

### backend/app/orchestrator/intent_classifier.py
- Purpose/layer: Module implementation [orchestrator]
- Key symbols: IntentClassifier; direct internal deps: app.infrastructure.llm_client, app.orchestrator.types
- Risks/validation: none notable

### backend/app/orchestrator/orchestrator_core.py
- Purpose/layer: Module implementation [orchestrator]
- Key symbols: Orchestrator; direct internal deps: app.agents.base_agent, app.infrastructure.llm_client, app.infrastructure.logging, app.orchestrator.action_extractor, app.orchestrator.agent_router
- Risks/validation: none notable

### backend/app/orchestrator/response_formatter.py
- Purpose/layer: Module implementation [orchestrator]
- Key symbols: ResponseFormatter; direct internal deps: app.orchestrator.types
- Risks/validation: none notable

### backend/app/orchestrator/types.py
- Purpose/layer: Module implementation [orchestrator]
- Key symbols: IntentResult, AgentAction, AgentContext, AgentExecutionResult, AgentResponse; direct internal deps: none
- Risks/validation: none notable

### backend/app/repositories/__init__.py
- Purpose/layer: Repository adapters. [repository]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/repositories/admin_activity_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: AdminActivityRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/auth_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: AuthRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/cart_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: CartRepository; direct internal deps: app.container, app.infrastructure.persistence_clients
- Risks/validation: broad_exception_handling, layer_violation:app.container->composition-root

### backend/app/repositories/category_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: CategoryRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/interaction_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: InteractionRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/inventory_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: InventoryRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/memory_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: MemoryRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/notification_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: NotificationRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/order_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: OrderRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/product_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: ProductRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/session_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: SessionRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/support_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: SupportRepository; direct internal deps: app.infrastructure.persistence_clients
- Risks/validation: none notable

### backend/app/repositories/voice_repository.py
- Purpose/layer: Module implementation [repository]
- Key symbols: VoiceRepository; direct internal deps: app.container, app.infrastructure.persistence_clients
- Risks/validation: broad_exception_handling, layer_violation:app.container->composition-root

### backend/app/scripts/__init__.py
- Purpose/layer: Operational scripts for Mongo bootstrap and index setup. [script]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/scripts/bootstrap_db.py
- Purpose/layer: Module implementation [script]
- Key symbols: _parser, _upsert_map, _upsert_list, run, main; direct internal deps: app.core.config, app.infrastructure.mongo_indexes, app.scripts.create_indexes, app.store.in_memory
- Risks/validation: print_statement_in_runtime_code

### backend/app/scripts/create_indexes.py
- Purpose/layer: Module implementation [script]
- Key symbols: _parser, _connect_with_retry, run, main; direct internal deps: app.core.config, app.infrastructure.mongo_indexes
- Risks/validation: broad_exception_handling, print_statement_in_runtime_code

### backend/app/scripts/perf_smoke.py
- Purpose/layer: Module implementation [script]
- Key symbols: _parser, _percentile, _measure_ms, run, main; direct internal deps: app.main
- Risks/validation: print_statement_in_runtime_code

### backend/app/services/__init__.py
- Purpose/layer: Business services. [service]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/services/admin_activity_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: AdminActivityService; direct internal deps: app.container, app.core.config, app.core.utils, app.repositories.admin_activity_repository
- Risks/validation: broad_exception_handling, layer_violation:app.container->composition-root

### backend/app/services/admin_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: AdminService; direct internal deps: app.core.utils, app.repositories.interaction_repository, app.repositories.order_repository, app.repositories.product_repository, app.repositories.session_repository
- Risks/validation: none notable

### backend/app/services/auth_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: AuthService; direct internal deps: app.core.config, app.core.security, app.core.utils, app.infrastructure.logging, app.repositories.auth_repository
- Risks/validation: none notable

### backend/app/services/cart_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: CartService; direct internal deps: app.core.config, app.core.utils, app.repositories.cart_repository, app.repositories.product_repository
- Risks/validation: none notable

### backend/app/services/category_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: CategoryService; direct internal deps: app.core.utils, app.repositories.category_repository, app.repositories.product_repository
- Risks/validation: none notable

### backend/app/services/interaction_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: InteractionService; direct internal deps: app.core.utils, app.repositories.interaction_repository
- Risks/validation: none notable

### backend/app/services/inventory_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: InventoryService; direct internal deps: app.core.utils, app.repositories.inventory_repository, app.repositories.product_repository
- Risks/validation: none notable

### backend/app/services/memory_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: MemoryService; direct internal deps: app.core.utils, app.repositories.memory_repository
- Risks/validation: broad_exception_handling

### backend/app/services/notification_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: NotificationService; direct internal deps: app.core.utils, app.repositories.notification_repository
- Risks/validation: none notable

### backend/app/services/order_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: OrderService; direct internal deps: app.core.utils, app.repositories.order_repository, app.services.cart_service, app.services.inventory_service, app.services.notification_service
- Risks/validation: broad_exception_handling

### backend/app/services/payment_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: PaymentService; direct internal deps: app.core.utils
- Risks/validation: placeholder_pass

### backend/app/services/product_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: ProductService; direct internal deps: app.core.utils, app.repositories.category_repository, app.repositories.inventory_repository, app.repositories.product_repository
- Risks/validation: broad_exception_handling

### backend/app/services/session_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: SessionService; direct internal deps: app.core.utils, app.repositories.session_repository
- Risks/validation: none notable

### backend/app/services/support_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: SupportService; direct internal deps: app.core.utils, app.repositories.support_repository
- Risks/validation: none notable

### backend/app/services/voice/__init__.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/services/voice/alerts.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: append_alert, evaluate_alerts, get_stats; direct internal deps: app.core.utils, app.repositories.voice_repository
- Risks/validation: none notable

### backend/app/services/voice/calls.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: list_calls, record_call_event, get_or_create_call, update_call_progress, update_call_terminal; direct internal deps: app.core.utils, app.repositories.voice_repository, app.services.voice.outcome
- Risks/validation: none notable

### backend/app/services/voice/campaign.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: build_campaign_payload; direct internal deps: none
- Risks/validation: none notable

### backend/app/services/voice/guardrails.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: in_quiet_hours, next_non_quiet_time, budget_and_cap_guardrails; direct internal deps: none
- Risks/validation: broad_exception_handling

### backend/app/services/voice/helpers.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: parse_iso, normalize_backoff_list, extract_provider_call_id, extract_provider_event_id, provider_event_key; direct internal deps: none
- Risks/validation: none notable

### backend/app/services/voice/jobs.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: enqueue_abandoned_cart_jobs, process_due_jobs, process_single_job, reschedule_job, complete_job; direct internal deps: app.core.utils, app.repositories.cart_repository, app.repositories.voice_repository, app.services.voice.alerts, app.services.voice.campaign
- Risks/validation: none notable

### backend/app/services/voice/outcome.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: apply_outcome_actions; direct internal deps: none
- Risks/validation: none notable

### backend/app/services/voice/settings.py
- Purpose/layer: Module implementation [service-voice]
- Key symbols: get_settings, update_settings, ensure_defaults; direct internal deps: app.repositories.voice_repository, app.services.voice.helpers
- Risks/validation: none notable

### backend/app/services/voice_recovery_service.py
- Purpose/layer: Module implementation [service]
- Key symbols: VoiceRecoveryService; direct internal deps: app.core.config, app.core.utils, app.infrastructure.superu_client, app.repositories.auth_repository, app.repositories.cart_repository
- Risks/validation: layer_violation:app.services.voice->service-voice

### backend/app/store/__init__.py
- Purpose/layer: In-memory persistence for local development. [store]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/app/store/in_memory.py
- Purpose/layer: Module implementation [store]
- Key symbols: InMemoryStore; direct internal deps: app.core.security
- Risks/validation: none notable

### backend/perf/locustfile.py
- Purpose/layer: Module implementation [perf]
- Key symbols: CommerceUser; direct internal deps: none
- Risks/validation: none notable

### backend/pytest.ini
- Purpose/layer: Pytest configuration [other]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/requirements-perf.txt
- Purpose/layer: Python dependency manifest [other]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/requirements.txt
- Purpose/layer: Python dependency manifest [other]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/test_scratch.py
- Purpose/layer: Module implementation [other]
- Key symbols: none; direct internal deps: app.main
- Risks/validation: print_statement_in_runtime_code, layer_violation:app.main->composition-root

### backend/test_scratch2.py
- Purpose/layer: Module implementation [other]
- Key symbols: none; direct internal deps: app.main
- Risks/validation: print_statement_in_runtime_code, layer_violation:app.main->composition-root

### backend/tests/__init__.py
- Purpose/layer: Backend tests. [test]
- Key symbols: none; direct internal deps: none
- Risks/validation: none notable

### backend/tests/conftest.py
- Purpose/layer: Module implementation [test]
- Key symbols: init_test_services, reset_db_state; direct internal deps: app.container
- Risks/validation: placeholder_pass

### backend/tests/integration/test_admin_activity_integrity.py
- Purpose/layer: Module implementation [test]
- Key symbols: _admin_headers, test_admin_activity_integrity_endpoint_detects_tampering; direct internal deps: app.container, app.main
- Risks/validation: none notable

### backend/tests/integration/test_admin_categories_support_and_brand.py
- Purpose/layer: Module implementation [test]
- Key symbols: _admin_headers, test_admin_category_crud_and_activity_logging, test_support_ticket_lifecycle_via_chat_and_admin, test_product_brand_filter_and_brand_search; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_admin_inventory_and_support.py
- Purpose/layer: Module implementation [test]
- Key symbols: _admin_headers, test_admin_can_update_inventory_and_product_stock_flag, test_support_escalation_creates_ticket_and_stats_reflect_it; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_admin_product_crud.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_admin_can_manage_products; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_admin_stats.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_admin_stats_requires_admin_role; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_admin_voice_recovery.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeSuperUClient, _admin_headers, test_admin_voice_recovery_endpoints_and_processing; direct internal deps: app.container, app.main
- Risks/validation: none notable

### backend/tests/integration/test_api_contract_errors_and_orders.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_orders_create_returns_201_for_authenticated_user, test_auth_required_and_validation_errors_use_standard_error_envelope, test_order_shipping_address_update_endpoint, test_order_shipping_address_update_rejected_after_refund; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_auth_refresh_rotation.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_refresh_token_rotation_revokes_previous_token; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_http_hardening.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_http_responses_include_security_headers, test_mutating_endpoint_rejects_non_json_content_type, test_request_body_size_limit_is_enforced, test_duplicate_critical_headers_are_rejected; direct internal deps: app.container, app.main
- Risks/validation: none notable

### backend/tests/integration/test_interaction_history_branches.py
- Purpose/layer: Module implementation [test]
- Key symbols: _create_session, _register_user, test_authenticated_history_builds_fallback_from_memory_when_session_history_is_empty, test_guest_history_requires_session_id, test_process_message_creates_session_when_missing_and_handles_identity_link_failure; direct internal deps: app.api.routes.interaction_routes, app.main
- Risks/validation: none notable

### backend/tests/integration/test_interactions_flow.py
- Purpose/layer: Module implementation [test]
- Key symbols: _create_session, test_interaction_search_and_add_to_cart_guest, test_interaction_checkout_requires_auth_then_succeeds, test_interaction_parallel_multi_status, test_interaction_single_message_search_and_add_to_cart; direct internal deps: app.container, app.infrastructure.llm_client, app.main
- Risks/validation: none notable

### backend/tests/integration/test_memory_controls_and_history.py
- Purpose/layer: Module implementation [test]
- Key symbols: _create_session, test_chat_memory_save_show_forget_and_clear, test_interaction_history_endpoint_returns_transcript_for_guest_session, test_login_merges_guest_cart_into_existing_user_cart; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_personalized_recommendations.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_recommendations_use_user_preferred_category; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_refund_flow.py
- Purpose/layer: Module implementation [test]
- Key symbols: _register_and_get_token, _create_order, test_refund_endpoint_marks_order_as_refunded, test_chat_refund_intent_uses_order_agent; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_session_continuity.py
- Purpose/layer: Module implementation [test]
- Key symbols: _create_session, test_login_reuses_existing_user_session_for_chat_continuity, test_websocket_switches_to_existing_user_session_when_authenticated; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/integration/test_voice_webhook_callback.py
- Purpose/layer: Module implementation [test]
- Key symbols: _sign, _seed_call, test_superu_callback_ingests_signed_event_idempotently, test_superu_callback_rejects_invalid_signature; direct internal deps: app.container, app.main
- Risks/validation: none notable

### backend/tests/integration/test_voice_webhook_route_errors.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_voice_callback_rejects_when_signature_verification_fails, test_voice_callback_rejects_empty_payload_after_signature_check, test_voice_callback_rejects_invalid_json_payload, test_voice_callback_rejects_non_object_json_payload, test_voice_callback_rejects_when_ingest_returns_not_accepted; direct internal deps: app.api.routes.voice_webhook_routes, app.main
- Risks/validation: none notable

### backend/tests/integration/test_websocket_flow.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_websocket_message_flow, test_websocket_streaming_flow_when_requested, test_websocket_assistant_typing_events_when_requested, test_websocket_ping_pong_roundtrip, test_websocket_reconnect_same_session; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/nl_eval/test_nl_accuracy_gate.py
- Purpose/layer: Module implementation [test]
- Key symbols: _build_eval_cases, test_nl_eval_accuracy_gate; direct internal deps: app.orchestrator.action_extractor, app.orchestrator.intent_classifier
- Risks/validation: none notable

### backend/tests/nl_eval/test_nl_intent_and_actions.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_nl_intent_and_action_eval; direct internal deps: app.orchestrator.action_extractor, app.orchestrator.intent_classifier
- Risks/validation: none notable

### backend/tests/unit/conftest.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeRedisClient, mock_external_clients; direct internal deps: app.container
- Risks/validation: none notable

### backend/tests/unit/test_admin_activity_service.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeMongoCollection, _FakeDatabase, _FakeMongoClient, _service, test_admin_activity_hash_chain_and_integrity; direct internal deps: app.core.config, app.infrastructure.persistence_clients, app.repositories.admin_activity_repository, app.services.admin_activity_service, app.store.in_memory
- Risks/validation: placeholder_pass

### backend/tests/unit/test_auth_totp.py
- Purpose/layer: Module implementation [test]
- Key symbols: mock_store, mock_repository, settings, auth_service, test_admin_login_with_valid_totp; direct internal deps: app.core.config, app.services.auth_service
- Risks/validation: none notable

### backend/tests/unit/test_base_agent.py
- Purpose/layer: Module implementation [test]
- Key symbols: BrokenAgent, test_base_agent_execute_raises_not_implemented; direct internal deps: app.agents.base_agent, app.orchestrator.types
- Risks/validation: none notable

### backend/tests/unit/test_circuit_breaker_and_classifier.py
- Purpose/layer: Module implementation [test]
- Key symbols: _StubLLMClient, test_circuit_breaker_opens_and_recovers, test_intent_classifier_prefers_higher_confidence_llm_result, test_intent_classifier_detects_search_and_add_combo, test_intent_classifier_detects_discount_code; direct internal deps: app.infrastructure.circuit_breaker, app.infrastructure.llm_client, app.orchestrator.intent_classifier
- Risks/validation: placeholder_pass

### backend/tests/unit/test_guest_cart_transfer_on_login.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_guest_cart_is_attached_after_login; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/unit/test_guest_checkout_guard.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_guest_can_add_to_cart_but_cannot_create_order; direct internal deps: app.main
- Risks/validation: none notable

### backend/tests/unit/test_llm_client.py
- Purpose/layer: Module implementation [test]
- Key symbols: _DummyResponse, _base_settings, _planner_settings, test_enabled_flag_checks_api_key, test_classify_intent_returns_none_when_disabled; direct internal deps: app.core.config, app.infrastructure.circuit_breaker, app.infrastructure.llm_client
- Risks/validation: none notable

### backend/tests/unit/test_metrics_collector.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_metrics_collector_renders_core_series; direct internal deps: app.infrastructure.observability
- Risks/validation: none notable

### backend/tests/unit/test_mongo_indexes.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_mongo_index_specs_cover_repository_collections, test_mongo_index_specs_use_stable_named_indexes; direct internal deps: app.infrastructure.mongo_indexes
- Risks/validation: none notable

### backend/tests/unit/test_perf_smoke_script.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeResponse, _FakeWebSocket, _FakeClient, test_percentile_helper, test_perf_smoke_run_success; direct internal deps: app.scripts
- Risks/validation: none notable

### backend/tests/unit/test_rate_limiter.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_sliding_window_rate_limiter_blocks_after_limit, test_sliding_window_rate_limiter_applies_progressive_penalties; direct internal deps: app.infrastructure.rate_limiter
- Risks/validation: none notable

### backend/tests/unit/test_repositories.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeRedisClient, _FakeMongoCollection, _FakeDatabase, _FakeMongoClient, _disabled_managers; direct internal deps: app.infrastructure.persistence_clients, app.repositories.admin_activity_repository, app.repositories.auth_repository, app.repositories.cart_repository, app.repositories.category_repository
- Risks/validation: none notable

### backend/tests/unit/test_repository_fallbacks.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeCursor, _FakeCollection, _FakeMongoDatabase, _FakeMongoClient, _FakeRedisClient; direct internal deps: app.core.utils, app.infrastructure.persistence_clients, app.repositories.auth_repository, app.repositories.order_repository, app.repositories.session_repository
- Risks/validation: none notable

### backend/tests/unit/test_scripts_bootstrap_and_indexes.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeAdmin, _FakeCollection, _FakeDB, _FakeMongoClient, test_connect_with_retry_success_after_retry; direct internal deps: app.scripts
- Risks/validation: none notable

### backend/tests/unit/test_state_persistence_and_clients.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeAdmin, _FakeCollection, _FakeMongoDatabase, _FakeMongoClient, _FakeRedisPipeline; direct internal deps: app.infrastructure.persistence_clients, app.infrastructure.state_persistence, app.store.in_memory
- Risks/validation: none notable

### backend/tests/unit/test_store_state_snapshot.py
- Purpose/layer: Module implementation [test]
- Key symbols: test_store_state_export_import_roundtrip; direct internal deps: app.store.in_memory
- Risks/validation: none notable

### backend/tests/unit/test_superu_client.py
- Purpose/layer: Module implementation [test]
- Key symbols: _DummyResponse, _settings, _sign, test_enabled_flag_checks_minimum_configuration, test_start_outbound_call_requires_assistant_and_from_number; direct internal deps: app.core.config, app.infrastructure.superu_client
- Risks/validation: none notable

### backend/tests/unit/test_voice_recovery_service.py
- Purpose/layer: Module implementation [test]
- Key symbols: _FakeRedisClient, _FakeMongoCollection, _FakeDatabase, _FakeMongoClient, _fake_managers; direct internal deps: app.core.config, app.core.utils, app.infrastructure.persistence_clients, app.repositories.auth_repository, app.repositories.cart_repository
- Risks/validation: none notable

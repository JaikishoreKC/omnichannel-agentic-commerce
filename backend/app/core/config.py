from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Omnichannel Agentic Commerce API"
    api_prefix: str = "/v1"
    token_secret: str = "replace-with-strong-secret"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 7 * 24 * 60 * 60
    cart_tax_rate: float = 0.08
    default_shipping_fee: float = 5.99
    cors_origins: str = "http://localhost:5173"
    mongodb_uri: str = "mongodb://localhost:27017/commerce"
    redis_url: str = "redis://localhost:6379/0"
    enable_external_services: bool = False
    rate_limit_anonymous_per_minute: int = 120
    rate_limit_authenticated_per_minute: int = 600
    rate_limit_admin_per_minute: int = 2000
    request_max_body_bytes: int = 10 * 1024 * 1024
    session_cookie_secure: bool = True
    session_cookie_samesite: str = "lax"
    enforce_json_content_type: bool = True
    reject_duplicate_critical_headers: bool = True
    admin_mfa_required: bool = False
    admin_mfa_static_code: str = ""
    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 8.0
    llm_max_tokens: int = 200
    llm_temperature: float = 0.0
    llm_circuit_breaker_failure_threshold: int = 5
    llm_circuit_breaker_timeout_seconds: float = 60.0
    llm_intent_classifier_enabled: bool = False
    llm_planner_enabled: bool = True
    llm_decision_policy: str = "planner_first"
    planner_feature_enabled: bool = True
    planner_canary_percent: int = 100
    llm_planner_max_actions: int = 5
    llm_planner_min_confidence: float = 0.55
    llm_planner_execution_mode: str = "partial"
    orchestrator_max_actions_per_request: int = 5
    ws_heartbeat_interval_seconds: float = 25.0
    ws_heartbeat_timeout_seconds: float = 70.0
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    superu_enabled: bool = False
    superu_api_url: str = "https://api.superu.ai"
    superu_api_key: str = ""
    superu_assistant_id: str = ""
    superu_from_phone_number: str = ""
    superu_webhook_secret: str = ""
    superu_webhook_tolerance_seconds: int = 300
    voice_recovery_scheduler_enabled: bool = False
    voice_recovery_scan_interval_seconds: float = 30.0
    voice_abandonment_minutes: int = 30
    voice_max_attempts_per_cart: int = 3
    voice_max_calls_per_user_per_day: int = 2
    voice_max_calls_per_day: int = 300
    voice_daily_budget_usd: float = 300.0
    voice_estimated_cost_per_call_usd: float = 0.7
    voice_quiet_hours_start: int = 21
    voice_quiet_hours_end: int = 8
    voice_retry_backoff_seconds_csv: str = "60,300,900"
    voice_script_version: str = "v1"
    voice_script_template: str = (
        "Hi {name}, you still have {item_count} item(s) in your cart worth ${cart_total:.2f}. "
        "Would you like help checking out?"
    )
    voice_global_kill_switch: bool = False
    voice_default_timezone: str = "UTC"
    voice_alert_backlog_threshold: int = 50
    voice_alert_failure_ratio_threshold: float = 0.35

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [value.strip() for value in self.cors_origins.split(",")]
        return [value for value in origins if value]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", cls.app_name),
            api_prefix=os.getenv("API_PREFIX", cls.api_prefix),
            token_secret=os.getenv("TOKEN_SECRET", cls.token_secret),
            access_token_ttl_seconds=int(
                os.getenv("ACCESS_TOKEN_TTL_SECONDS", str(cls.access_token_ttl_seconds))
            ),
            refresh_token_ttl_seconds=int(
                os.getenv("REFRESH_TOKEN_TTL_SECONDS", str(cls.refresh_token_ttl_seconds))
            ),
            cart_tax_rate=float(os.getenv("CART_TAX_RATE", str(cls.cart_tax_rate))),
            default_shipping_fee=float(
                os.getenv("DEFAULT_SHIPPING_FEE", str(cls.default_shipping_fee))
            ),
            cors_origins=os.getenv("CORS_ORIGINS", cls.cors_origins),
            mongodb_uri=os.getenv("MONGODB_URI", cls.mongodb_uri),
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            enable_external_services=os.getenv("ENABLE_EXTERNAL_SERVICES", "false").lower()
            in {"1", "true", "yes"},
            rate_limit_anonymous_per_minute=int(
                os.getenv(
                    "RATE_LIMIT_ANONYMOUS_PER_MINUTE",
                    str(cls.rate_limit_anonymous_per_minute),
                )
            ),
            rate_limit_authenticated_per_minute=int(
                os.getenv(
                    "RATE_LIMIT_AUTHENTICATED_PER_MINUTE",
                    str(cls.rate_limit_authenticated_per_minute),
                )
            ),
            rate_limit_admin_per_minute=int(
                os.getenv("RATE_LIMIT_ADMIN_PER_MINUTE", str(cls.rate_limit_admin_per_minute))
            ),
            request_max_body_bytes=int(
                os.getenv("REQUEST_MAX_BODY_BYTES", str(cls.request_max_body_bytes))
            ),
            session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "true").lower()
            in {"1", "true", "yes"},
            session_cookie_samesite=os.getenv("SESSION_COOKIE_SAMESITE", cls.session_cookie_samesite),
            enforce_json_content_type=os.getenv("ENFORCE_JSON_CONTENT_TYPE", "true").lower()
            in {"1", "true", "yes"},
            reject_duplicate_critical_headers=os.getenv(
                "REJECT_DUPLICATE_CRITICAL_HEADERS", "true"
            ).lower()
            in {"1", "true", "yes"},
            admin_mfa_required=os.getenv("ADMIN_MFA_REQUIRED", "false").lower() in {"1", "true", "yes"},
            admin_mfa_static_code=os.getenv("ADMIN_MFA_STATIC_CODE", cls.admin_mfa_static_code),
            llm_enabled=os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes"},
            llm_provider=os.getenv("LLM_PROVIDER", cls.llm_provider),
            llm_model=os.getenv("LLM_MODEL", cls.llm_model),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", str(cls.llm_timeout_seconds))),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", str(cls.llm_max_tokens))),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", str(cls.llm_temperature))),
            llm_circuit_breaker_failure_threshold=int(
                os.getenv(
                    "LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
                    str(cls.llm_circuit_breaker_failure_threshold),
                )
            ),
            llm_circuit_breaker_timeout_seconds=float(
                os.getenv(
                    "LLM_CIRCUIT_BREAKER_TIMEOUT_SECONDS",
                    str(cls.llm_circuit_breaker_timeout_seconds),
                )
            ),
            llm_intent_classifier_enabled=os.getenv(
                "LLM_INTENT_CLASSIFIER_ENABLED", str(cls.llm_intent_classifier_enabled)
            ).lower()
            in {"1", "true", "yes"},
            llm_planner_enabled=os.getenv(
                "LLM_PLANNER_ENABLED", str(cls.llm_planner_enabled)
            ).lower()
            in {"1", "true", "yes"},
            llm_decision_policy=str(
                os.getenv("LLM_DECISION_POLICY", cls.llm_decision_policy)
            )
            .strip()
            .lower()
            or cls.llm_decision_policy,
            planner_feature_enabled=os.getenv(
                "PLANNER_FEATURE_ENABLED", str(cls.planner_feature_enabled)
            ).lower()
            in {"1", "true", "yes"},
            planner_canary_percent=max(
                0,
                min(
                    100,
                    int(
                        os.getenv(
                            "PLANNER_CANARY_PERCENT",
                            str(cls.planner_canary_percent),
                        )
                    ),
                ),
            ),
            llm_planner_max_actions=max(
                1,
                min(
                    10,
                    int(
                        os.getenv(
                            "LLM_PLANNER_MAX_ACTIONS",
                            str(cls.llm_planner_max_actions),
                        )
                    ),
                ),
            ),
            llm_planner_min_confidence=max(
                0.0,
                min(
                    1.0,
                    float(
                        os.getenv(
                            "LLM_PLANNER_MIN_CONFIDENCE",
                            str(cls.llm_planner_min_confidence),
                        )
                    ),
                ),
            ),
            llm_planner_execution_mode=str(
                os.getenv(
                    "LLM_PLANNER_EXECUTION_MODE",
                    cls.llm_planner_execution_mode,
                )
            )
            .strip()
            .lower()
            or cls.llm_planner_execution_mode,
            orchestrator_max_actions_per_request=max(
                1,
                min(
                    10,
                    int(
                        os.getenv(
                            "ORCHESTRATOR_MAX_ACTIONS_PER_REQUEST",
                            str(cls.orchestrator_max_actions_per_request),
                        )
                    ),
                ),
            ),
            ws_heartbeat_interval_seconds=float(
                os.getenv(
                    "WS_HEARTBEAT_INTERVAL_SECONDS",
                    str(cls.ws_heartbeat_interval_seconds),
                )
            ),
            ws_heartbeat_timeout_seconds=float(
                os.getenv(
                    "WS_HEARTBEAT_TIMEOUT_SECONDS",
                    str(cls.ws_heartbeat_timeout_seconds),
                )
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY", cls.openai_api_key),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", cls.anthropic_api_key),
            superu_enabled=os.getenv("SUPERU_ENABLED", "false").lower() in {"1", "true", "yes"},
            superu_api_url=os.getenv("SUPERU_API_URL", cls.superu_api_url),
            superu_api_key=os.getenv("SUPERU_API_KEY", cls.superu_api_key),
            superu_assistant_id=os.getenv("SUPERU_ASSISTANT_ID", cls.superu_assistant_id),
            superu_from_phone_number=os.getenv("SUPERU_FROM_PHONE_NUMBER", cls.superu_from_phone_number),
            superu_webhook_secret=os.getenv("SUPERU_WEBHOOK_SECRET", cls.superu_webhook_secret),
            superu_webhook_tolerance_seconds=int(
                os.getenv(
                    "SUPERU_WEBHOOK_TOLERANCE_SECONDS",
                    str(cls.superu_webhook_tolerance_seconds),
                )
            ),
            voice_recovery_scheduler_enabled=os.getenv("VOICE_RECOVERY_SCHEDULER_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            voice_recovery_scan_interval_seconds=float(
                os.getenv(
                    "VOICE_RECOVERY_SCAN_INTERVAL_SECONDS",
                    str(cls.voice_recovery_scan_interval_seconds),
                )
            ),
            voice_abandonment_minutes=int(
                os.getenv("VOICE_ABANDONMENT_MINUTES", str(cls.voice_abandonment_minutes))
            ),
            voice_max_attempts_per_cart=int(
                os.getenv("VOICE_MAX_ATTEMPTS_PER_CART", str(cls.voice_max_attempts_per_cart))
            ),
            voice_max_calls_per_user_per_day=int(
                os.getenv(
                    "VOICE_MAX_CALLS_PER_USER_PER_DAY",
                    str(cls.voice_max_calls_per_user_per_day),
                )
            ),
            voice_max_calls_per_day=int(
                os.getenv("VOICE_MAX_CALLS_PER_DAY", str(cls.voice_max_calls_per_day))
            ),
            voice_daily_budget_usd=float(
                os.getenv("VOICE_DAILY_BUDGET_USD", str(cls.voice_daily_budget_usd))
            ),
            voice_estimated_cost_per_call_usd=float(
                os.getenv(
                    "VOICE_ESTIMATED_COST_PER_CALL_USD",
                    str(cls.voice_estimated_cost_per_call_usd),
                )
            ),
            voice_quiet_hours_start=int(
                os.getenv("VOICE_QUIET_HOURS_START", str(cls.voice_quiet_hours_start))
            ),
            voice_quiet_hours_end=int(
                os.getenv("VOICE_QUIET_HOURS_END", str(cls.voice_quiet_hours_end))
            ),
            voice_retry_backoff_seconds_csv=os.getenv(
                "VOICE_RETRY_BACKOFF_SECONDS_CSV",
                cls.voice_retry_backoff_seconds_csv,
            ),
            voice_script_version=os.getenv("VOICE_SCRIPT_VERSION", cls.voice_script_version),
            voice_script_template=os.getenv("VOICE_SCRIPT_TEMPLATE", cls.voice_script_template),
            voice_global_kill_switch=os.getenv("VOICE_GLOBAL_KILL_SWITCH", "false").lower()
            in {"1", "true", "yes"},
            voice_default_timezone=os.getenv("VOICE_DEFAULT_TIMEZONE", cls.voice_default_timezone),
            voice_alert_backlog_threshold=int(
                os.getenv("VOICE_ALERT_BACKLOG_THRESHOLD", str(cls.voice_alert_backlog_threshold))
            ),
            voice_alert_failure_ratio_threshold=float(
                os.getenv(
                    "VOICE_ALERT_FAILURE_RATIO_THRESHOLD",
                    str(cls.voice_alert_failure_ratio_threshold),
                )
            ),
        )

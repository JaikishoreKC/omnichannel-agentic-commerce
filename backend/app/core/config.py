from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Omnichannel Agentic Commerce API"
    api_prefix: str = "/v1"
    token_secret: str = "dev-insecure-secret-change-me"
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
    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 8.0
    llm_max_tokens: int = 200
    llm_temperature: float = 0.0
    llm_circuit_breaker_failure_threshold: int = 5
    llm_circuit_breaker_timeout_seconds: float = 60.0
    ws_heartbeat_interval_seconds: float = 25.0
    ws_heartbeat_timeout_seconds: float = 70.0
    openai_api_key: str = ""
    anthropic_api_key: str = ""

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
        )

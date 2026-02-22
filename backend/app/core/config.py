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
        )

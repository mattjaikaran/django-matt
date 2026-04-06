from __future__ import annotations

from datetime import timedelta
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from django_matt.config.validators import validate_duration

_cache: dict[str, ConfigNamespace] = {}


class ConfigNamespace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    _settings_key: ClassVar[str] = ""

    @classmethod
    def from_settings(cls, key: str | None = None) -> "ConfigNamespace":
        settings_key = key or cls._settings_key
        if not settings_key:
            raise ValueError(
                f"{cls.__name__} has no _settings_key and none was provided"
            )

        if settings_key in _cache:
            return _cache[settings_key]

        from django.conf import settings

        matt_settings: dict[str, Any] = getattr(settings, "DJANGO_MATT", {})
        section = matt_settings.get(settings_key, {})
        instance = cls.model_validate(section)
        _cache[settings_key] = instance
        return instance

    @classmethod
    def reset(cls) -> None:
        key = cls._settings_key
        if key and key in _cache:
            del _cache[key]

    @classmethod
    def reset_all(cls) -> None:
        _cache.clear()


class AuthConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "AUTH"

    secret: SecretStr = SecretStr("change-me")
    algorithm: str = "HS256"
    expiry: timedelta = timedelta(minutes=60)
    refresh_expiry: timedelta = timedelta(days=7)
    issuer: str = "django-matt"

    @field_validator("expiry", "refresh_expiry", mode="before")
    @classmethod
    def _parse_duration(cls, v: Any) -> timedelta:
        return validate_duration(v)


class CacheConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "CACHE"

    backend: str = "django.core.cache.backends.locmem.LocMemCache"
    ttl: int = 300
    prefix: str = "matt"
    serializer: Literal["json", "pickle", "msgpack"] = "json"


class DatabaseConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "DATABASE"

    pool_min_size: int = 2
    pool_max_size: int = 10
    connection_timeout: int = 5
    statement_timeout: int = 30


class SecurityConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "SECURITY"

    cors_origins: list[str] = []
    csp_directives: dict[str, str] = {}
    rate_limit: str = "100/hour"
    allowed_hosts: list[str] = ["*"]


class APIConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "API"

    page_size: int = 25
    max_page_size: int = 100
    throttle_rate: str = "1000/hour"
    versioning_scheme: Literal["url", "header", "query"] = "url"


class BillingConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "BILLING"

    provider: Literal["stripe", "paypal", "polar"] = "stripe"
    api_key: SecretStr = SecretStr("")
    webhook_secret: SecretStr = SecretStr("")


class ObservabilityConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "OBSERVABILITY"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    tracing_enabled: bool = False
    metrics_backend: Literal["prometheus", "statsd", "none"] = "none"

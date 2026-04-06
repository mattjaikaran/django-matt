from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import SecretStr, ValidationError

from django_matt.config.namespaces import (
    APIConfig,
    AuthConfig,
    BillingConfig,
    CacheConfig,
    ConfigNamespace,
    DatabaseConfig,
    ObservabilityConfig,
    SecurityConfig,
    _cache,
)
from django_matt.config.startup import (
    register_namespace,
    reset_startup,
    skip_validation,
    validate_config,
)
from django_matt.config.validators import validate_duration, validate_size, validate_url


@pytest.fixture(autouse=True)
def _clear_caches():
    ConfigNamespace.reset_all()
    reset_startup()
    yield
    ConfigNamespace.reset_all()
    reset_startup()


# ── validators ──────────────────────────────────────────────────────


class TestValidateUrl:
    def test_valid_http(self):
        assert validate_url("http://example.com") == "http://example.com"

    def test_valid_https(self):
        assert validate_url("https://example.com/path?q=1") == "https://example.com/path?q=1"

    def test_invalid_no_scheme(self):
        with pytest.raises(ValueError, match="invalid URL"):
            validate_url("example.com")

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="expected string"):
            validate_url(123)


class TestValidateDuration:
    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            ("30s", timedelta(seconds=30)),
            ("5m", timedelta(minutes=5)),
            ("1h", timedelta(hours=1)),
            ("7d", timedelta(days=7)),
            ("2w", timedelta(weeks=2)),
            ("500ms", timedelta(milliseconds=500)),
            (60, timedelta(seconds=60)),
            (timedelta(seconds=10), timedelta(seconds=10)),
        ],
    )
    def test_valid(self, input_val, expected):
        assert validate_duration(input_val) == expected

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="invalid duration"):
            validate_duration("abc")

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="expected string or number"):
            validate_duration([1, 2])


class TestValidateSize:
    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            ("10MB", 10 * 1024**2),
            ("1GB", 1024**3),
            ("512KB", 512 * 1024),
            ("100B", 100),
            ("2TB", 2 * 1024**4),
            (4096, 4096),
        ],
    )
    def test_valid(self, input_val, expected):
        assert validate_size(input_val) == expected

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="invalid size"):
            validate_size("10XB")

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="expected string or int"):
            validate_size(3.14)


# ── namespaces ──────────────────────────────────────────────────────


class TestConfigNamespace:
    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            AuthConfig(typo_field="oops")

    def test_defaults_load(self):
        cfg = AuthConfig()
        assert cfg.algorithm == "HS256"
        assert cfg.expiry == timedelta(minutes=60)

    def test_override_fields(self):
        cfg = AuthConfig(
            secret=SecretStr("my-secret"),
            algorithm="RS256",
            expiry=timedelta(hours=2),
        )
        assert cfg.secret.get_secret_value() == "my-secret"
        assert cfg.algorithm == "RS256"
        assert cfg.expiry == timedelta(hours=2)


class TestAuthConfig:
    def test_duration_string_parsing(self):
        cfg = AuthConfig(expiry="30m", refresh_expiry="14d")
        assert cfg.expiry == timedelta(minutes=30)
        assert cfg.refresh_expiry == timedelta(days=14)


class TestCacheConfig:
    def test_defaults(self):
        cfg = CacheConfig()
        assert cfg.ttl == 300
        assert cfg.serializer == "json"

    def test_invalid_serializer(self):
        with pytest.raises(ValidationError):
            CacheConfig(serializer="xml")


class TestDatabaseConfig:
    def test_defaults(self):
        cfg = DatabaseConfig()
        assert cfg.pool_min_size == 2
        assert cfg.pool_max_size == 10


class TestSecurityConfig:
    def test_defaults(self):
        cfg = SecurityConfig()
        assert cfg.allowed_hosts == ["*"]
        assert cfg.cors_origins == []


class TestAPIConfig:
    def test_defaults(self):
        cfg = APIConfig()
        assert cfg.page_size == 25
        assert cfg.versioning_scheme == "url"

    def test_invalid_versioning(self):
        with pytest.raises(ValidationError):
            APIConfig(versioning_scheme="magic")


class TestBillingConfig:
    def test_secret_str_fields(self):
        cfg = BillingConfig(api_key="sk_test_123", webhook_secret="whsec_abc")
        assert cfg.api_key.get_secret_value() == "sk_test_123"
        assert cfg.webhook_secret.get_secret_value() == "whsec_abc"


class TestObservabilityConfig:
    def test_defaults(self):
        cfg = ObservabilityConfig()
        assert cfg.log_level == "INFO"
        assert cfg.tracing_enabled is False


# ── from_settings ───────────────────────────────────────────────────


class TestFromSettings:
    def test_loads_from_django_settings(self, settings):
        settings.DJANGO_MATT = {
            "CACHE": {"ttl": 600, "prefix": "myapp"},
        }
        cfg = CacheConfig.from_settings()
        assert cfg.ttl == 600
        assert cfg.prefix == "myapp"

    def test_caches_result(self, settings):
        settings.DJANGO_MATT = {"CACHE": {"ttl": 999}}
        first = CacheConfig.from_settings()
        settings.DJANGO_MATT = {"CACHE": {"ttl": 111}}
        second = CacheConfig.from_settings()
        assert first is second
        assert second.ttl == 999

    def test_reset_clears_cache(self, settings):
        settings.DJANGO_MATT = {"CACHE": {"ttl": 999}}
        CacheConfig.from_settings()
        assert "CACHE" in _cache
        CacheConfig.reset()
        assert "CACHE" not in _cache

    def test_extra_key_caught(self, settings):
        settings.DJANGO_MATT = {"CACHE": {"ttl": 300, "typo_key": True}}
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            CacheConfig.from_settings()


# ── startup validation ──────────────────────────────────────────────


class TestStartupValidation:
    def test_validate_registered_namespaces(self, settings):
        settings.DJANGO_MATT = {
            "CACHE": {"ttl": 300},
            "API": {"page_size": 50},
        }
        register_namespace("CACHE", CacheConfig)
        register_namespace("API", APIConfig)
        results = validate_config()
        assert "CACHE" in results
        assert results["API"].page_size == 50

    def test_validation_error_has_field_path(self, settings):
        settings.DJANGO_MATT = {
            "API": {"versioning_scheme": "magic"},
        }
        register_namespace("API", APIConfig)
        with pytest.raises(ValueError, match="DJANGO_MATT.API.versioning_scheme"):
            validate_config()

    def test_skip_validation(self, settings):
        settings.DJANGO_MATT = {
            "API": {"versioning_scheme": "magic"},
        }
        register_namespace("API", APIConfig)
        skip_validation("API")
        results = validate_config()
        assert "API" not in results

    def test_register_non_namespace_raises(self):
        with pytest.raises(TypeError, match="must be a ConfigNamespace subclass"):
            register_namespace("BAD", dict)  # type: ignore[arg-type]

    def test_multiple_errors_collected(self, settings):
        settings.DJANGO_MATT = {
            "CACHE": {"serializer": "xml"},
            "API": {"versioning_scheme": "magic"},
        }
        register_namespace("CACHE", CacheConfig)
        register_namespace("API", APIConfig)
        with pytest.raises(ValueError, match="configuration errors") as exc_info:
            validate_config()
        msg = str(exc_info.value)
        assert "DJANGO_MATT.CACHE" in msg
        assert "DJANGO_MATT.API" in msg

    def test_missing_section_uses_defaults(self, settings):
        settings.DJANGO_MATT = {}
        register_namespace("CACHE", CacheConfig)
        results = validate_config()
        assert results["CACHE"].ttl == 300


# ── custom namespace ────────────────────────────────────────────────


class TestCustomNamespace:
    def test_user_defined_namespace(self, settings):
        class MyAppConfig(ConfigNamespace):
            feature_x_enabled: bool = False
            max_retries: int = 3

        settings.DJANGO_MATT = {
            "MY_APP": {"feature_x_enabled": True, "max_retries": 5},
        }
        register_namespace("MY_APP", MyAppConfig)
        results = validate_config()
        assert results["MY_APP"].feature_x_enabled is True
        assert results["MY_APP"].max_retries == 5

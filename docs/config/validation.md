# Configuration Validation

Django Matt validates configuration at startup using Pydantic-based `ConfigNamespace` classes. This catches misconfigured settings early with clear error messages instead of runtime failures.

## ConfigNamespace

All configuration sections extend `ConfigNamespace`, a Pydantic `BaseModel` with `extra="forbid"` (typos in setting names raise errors).

```python
from django_matt.config.namespaces import ConfigNamespace

class MyConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "MY_FEATURE"

    enabled: bool = True
    max_retries: int = 3
    timeout: str = "30s"
```

### Loading from Settings

```python
# settings.py
DJANGO_MATT = {
    "MY_FEATURE": {
        "enabled": True,
        "max_retries": 5,
    },
}
```

```python
# In your code
config = MyConfig.from_settings()  # reads DJANGO_MATT["MY_FEATURE"]
config.enabled    # True
config.max_retries  # 5
config.timeout    # "30s" (default)
```

Results are cached. Call `MyConfig.reset()` to clear the cache for a single namespace, or `ConfigNamespace.reset_all()` to clear all.

## Built-in Namespaces

| Namespace | Settings Key | Fields |
|-----------|-------------|--------|
| `AuthConfig` | `AUTH` | `secret`, `algorithm`, `expiry`, `refresh_expiry`, `issuer` |
| `CacheConfig` | `CACHE` | `backend`, `ttl`, `prefix`, `serializer` |
| `DatabaseConfig` | `DATABASE` | `pool_min_size`, `pool_max_size`, `connection_timeout`, `statement_timeout` |
| `SecurityConfig` | `SECURITY` | `cors_origins`, `csp_directives`, `rate_limit`, `allowed_hosts` |
| `APIConfig` | `API` | `page_size`, `max_page_size`, `throttle_rate`, `versioning_scheme` |
| `BillingConfig` | `BILLING` | `provider`, `api_key`, `webhook_secret` |
| `ObservabilityConfig` | `OBSERVABILITY` | `log_level`, `tracing_enabled`, `metrics_backend` |

### Example

```python
# settings.py
DJANGO_MATT = {
    "AUTH": {
        "secret": "my-jwt-secret",
        "algorithm": "HS256",
        "expiry": "1h",           # parsed as timedelta
        "refresh_expiry": "7d",
    },
    "DATABASE": {
        "pool_min_size": 5,
        "pool_max_size": 20,
    },
    "API": {
        "page_size": 50,
        "versioning_scheme": "header",
    },
}
```

## Built-in Validators

The `django_matt.config.validators` module provides reusable validation functions:

### validate_duration()

Parses human-readable durations into `timedelta`:

```python
from django_matt.config.validators import validate_duration

validate_duration("30s")    # timedelta(seconds=30)
validate_duration("5m")     # timedelta(minutes=5)
validate_duration("1h")     # timedelta(hours=1)
validate_duration("7d")     # timedelta(days=7)
validate_duration("2w")     # timedelta(weeks=2)
validate_duration("500ms")  # timedelta(milliseconds=500)
validate_duration(60)       # timedelta(seconds=60)
```

Supported units: `ms`, `s`, `m`, `h`, `d`, `w`.

### validate_size()

Parses human-readable byte sizes into `int`:

```python
from django_matt.config.validators import validate_size

validate_size("10MB")   # 10485760
validate_size("1GB")    # 1073741824
validate_size("512KB")  # 524288
validate_size(1024)     # 1024 (passthrough)
```

Supported units: `B`, `KB`, `MB`, `GB`, `TB`.

### validate_url()

Validates HTTP/HTTPS URLs:

```python
from django_matt.config.validators import validate_url

validate_url("https://example.com/api")  # returns the string
validate_url("not-a-url")                # raises ValueError
```

## Startup Validation

Register namespaces for batch validation at startup:

```python
from django_matt.config.startup import register_namespace, validate_config

# Register namespaces (typically in AppConfig.ready())
register_namespace("AUTH", AuthConfig)
register_namespace("DATABASE", DatabaseConfig)

# Validate all registered namespaces at once
results = validate_config()
# {"AUTH": AuthConfig(...), "DATABASE": DatabaseConfig(...)}
```

If any namespace has invalid values, `validate_config()` raises a `ValueError` with all errors collected:

```
django-matt configuration errors:
  DJANGO_MATT.AUTH.algorithm: Input should be 'HS256', 'HS384', 'HS512', ...
  DJANGO_MATT.DATABASE.pool_max_size: Input should be a valid integer
```

### Skipping Validation

```python
from django_matt.config.startup import skip_validation

# Skip validation for a specific namespace (e.g., during testing)
skip_validation("BILLING")
```

## Creating Custom Namespaces

```python
from typing import ClassVar, Literal
from pydantic import SecretStr, field_validator
from django_matt.config.namespaces import ConfigNamespace
from django_matt.config.validators import validate_duration

class EmailConfig(ConfigNamespace):
    _settings_key: ClassVar[str] = "EMAIL"

    provider: Literal["sendgrid", "ses", "mailgun", "smtp"] = "smtp"
    api_key: SecretStr = SecretStr("")
    from_address: str = "noreply@example.com"
    retry_delay: timedelta = timedelta(seconds=30)

    @field_validator("retry_delay", mode="before")
    @classmethod
    def _parse_duration(cls, v):
        return validate_duration(v)
```

```python
# settings.py
DJANGO_MATT = {
    "EMAIL": {
        "provider": "sendgrid",
        "api_key": "SG.xxxx",
        "retry_delay": "1m",
    },
}
```

Setting `extra="forbid"` (inherited from `ConfigNamespace`) means any unknown keys in the settings dict raise a validation error, catching typos early.

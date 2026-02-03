# Feature Flag Backends

django-matt supports multiple storage backends for feature flags.

## Overview

| Backend | Best For | Requirements |
|---------|----------|--------------|
| **Database** | Getting started, small-medium scale | None (uses Django ORM) |
| **Redis** | High-performance, distributed systems | `redis` package |
| **LaunchDarkly** | Enterprise, advanced targeting | `launchdarkly-server-sdk` |
| **Unleash** | Self-hosted, GitLab Feature Flags | `UnleashClient` |
| **Memory** | Testing | None |

## Configuration

```python
# settings.py

# Select backend
FEATURE_FLAG_BACKEND = "database"  # default

# Backend-specific settings
FEATURE_FLAG_BACKEND_SETTINGS = {
    "database": {
        "cache_timeout": 60,
        "use_cache": True,
    },
    "redis": {
        "redis_url": "redis://localhost:6379/0",
        "cache_timeout": 300,
    },
    "launchdarkly": {
        "sdk_key": "sdk-xxx-yyy",
    },
    "unleash": {
        "url": "https://unleash.example.com/api",
        "app_name": "my-app",
    },
}
```

---

## Database Backend

The default backend using Django ORM with optional caching.

### Configuration

```python
FEATURE_FLAG_BACKEND = "database"

FEATURE_FLAG_BACKEND_SETTINGS = {
    "database": {
        "cache_timeout": 60,      # Cache TTL in seconds
        "cache_prefix": "flags:", # Cache key prefix
        "use_cache": True,        # Enable/disable caching
    },
}
```

### Usage

```python
from django_matt.flags.backends import DatabaseBackend, get_backend

# Get default backend
backend = get_backend()

# Or explicitly
backend = DatabaseBackend(
    cache_timeout=60,
    use_cache=True,
)

# Check flag
enabled = backend.is_enabled("my_flag", user=user)

# Get variant
variant = backend.get_variant("experiment", user=user)

# Get all flags
all_flags = backend.get_all_flags(user=user)

# Invalidate cache
backend.invalidate_cache("my_flag")
backend.invalidate_cache()  # All flags
```

### Pros and Cons

**Pros:**

- No additional dependencies
- Full Django ORM features
- Easy to debug (query database directly)
- Automatic migrations

**Cons:**

- Database queries for each check (mitigated by caching)
- Not suitable for extremely high-throughput scenarios

---

## Redis Backend

High-performance backend optimized for distributed systems.

### Installation

```bash
pip install redis
```

### Configuration

```python
FEATURE_FLAG_BACKEND = "redis"

FEATURE_FLAG_BACKEND_SETTINGS = {
    "redis": {
        "redis_url": "redis://localhost:6379/0",
        "cache_timeout": 300,       # TTL in seconds
        "key_prefix": "feature_flags:",
    },
}
```

### Usage

```python
from django_matt.flags.backends import RedisBackend

backend = RedisBackend(
    redis_url="redis://localhost:6379/0",
    cache_timeout=300,
)

# Standard operations
enabled = backend.is_enabled("my_flag", user=user)
variant = backend.get_variant("experiment", user=user)

# Redis-specific operations
backend.invalidate("my_flag")          # Invalidate single flag
backend.invalidate_all()               # Invalidate all flags
backend.sync_from_database()           # Sync all flags from DB to Redis

# Close connection
backend.close()
```

### How It Works

1. Flags are stored in database (source of truth)
2. On first access, flag is cached in Redis
3. Subsequent checks read from Redis
4. Changes trigger cache invalidation

### Redis Data Structure

```
feature_flags:my_flag -> JSON blob with flag config and overrides
```

### Pros and Cons

**Pros:**

- Very fast lookups
- Shared cache across application instances
- Reduced database load

**Cons:**

- Requires Redis infrastructure
- Cache invalidation complexity
- Stale data possible (within TTL)

---

## LaunchDarkly Backend

Integration with [LaunchDarkly](https://launchdarkly.com/), a feature management platform.

### Installation

```bash
pip install launchdarkly-server-sdk
```

### Configuration

```python
FEATURE_FLAG_BACKEND = "launchdarkly"

FEATURE_FLAG_BACKEND_SETTINGS = {
    "launchdarkly": {
        "sdk_key": "sdk-xxx-yyy",  # From LaunchDarkly dashboard
    },
}

# Or via environment variable
LAUNCHDARKLY_SDK_KEY = "sdk-xxx-yyy"
```

### Usage

```python
from django_matt.flags.backends import LaunchDarklyBackend

backend = LaunchDarklyBackend(sdk_key="sdk-xxx-yyy")

# Standard operations
enabled = backend.is_enabled("my_flag", user=user)
variant = backend.get_variant("experiment", user=user)

# Get all flags
all_flags = backend.get_all_flags(user=user)

# Close (important for cleanup)
backend.close()
```

### Context Mapping

django-matt automatically maps user data to LaunchDarkly context:

```python
# User attributes automatically included:
# - key (user.pk)
# - email (user.email)
# - username (user.username)
# - firstName (user.first_name)
# - lastName (user.last_name)
# - isStaff (user.is_staff)

# Custom attributes passed through:
enabled = backend.is_enabled(
    "flag",
    user=user,
    attributes={
        "plan": "premium",
        "country": "US",
    }
)
```

### Pros and Cons

**Pros:**

- Powerful targeting and segmentation
- Real-time flag updates
- Built-in analytics and experimentation
- Enterprise features (audit logs, approvals)

**Cons:**

- Paid service
- External dependency
- Flags managed in LaunchDarkly UI (not Django admin)

---

## Unleash Backend

Integration with [Unleash](https://www.getunleash.io/), an open-source feature management platform.

### Installation

```bash
pip install UnleashClient
```

### Configuration

```python
FEATURE_FLAG_BACKEND = "unleash"

FEATURE_FLAG_BACKEND_SETTINGS = {
    "unleash": {
        "url": "https://unleash.example.com/api",
        "app_name": "my-django-app",
        "instance_id": "production-1",  # Optional
        "custom_headers": {              # Optional, for auth
            "Authorization": "api-key-xxx",
        },
    },
}
```

### Usage

```python
from django_matt.flags.backends import UnleashBackend

backend = UnleashBackend(
    url="https://unleash.example.com/api",
    app_name="my-app",
)

# Standard operations
enabled = backend.is_enabled("my_flag", user=user)
variant = backend.get_variant("experiment", user=user)

# Note: get_all_flags has limited support with Unleash
all_flags = backend.get_all_flags(user=user)  # May be empty

# Close
backend.close()
```

### GitLab Feature Flags

Unleash backend works with [GitLab Feature Flags](https://docs.gitlab.com/ee/operations/feature_flags.html):

```python
FEATURE_FLAG_BACKEND_SETTINGS = {
    "unleash": {
        "url": "https://gitlab.com/api/v4/feature_flags/unleash/12345",
        "app_name": "my-app",
        "custom_headers": {
            "UNLEASH-INSTANCEID": "my-instance",
            "UNLEASH-APPNAME": "my-app",
        },
    },
}
```

### Pros and Cons

**Pros:**

- Open source (self-hosted option)
- GitLab integration
- Activation strategies

**Cons:**

- Requires Unleash server
- Limited `get_all_flags` support
- Flags managed in Unleash UI

---

## Memory Backend

In-memory backend for testing.

### Usage

```python
from django_matt.flags.backends import MemoryBackend

backend = MemoryBackend()

# Set flags
backend.set_flag("my_flag", enabled=True)
backend.set_flag(
    "percentage_flag",
    flag_type="percentage",
    rollout_percentage=50,
)
backend.set_flag(
    "variant_flag",
    flag_type="variant",
    variants=["control", "treatment_a", "treatment_b"],
)

# Set overrides
backend.set_override("my_flag", user_id="123", enabled=False)
backend.set_override("variant_flag", user_id="456", variant="treatment_a")

# Check flags
enabled = backend.is_enabled("my_flag", user=user)
variant = backend.get_variant("variant_flag", user=user)

# Clear all
backend.clear()
```

### Testing Example

```python
# tests/test_features.py
import pytest
from django_matt.flags.backends import MemoryBackend, get_backend

@pytest.fixture
def flag_backend():
    backend = MemoryBackend()
    backend.set_flag("test_feature", enabled=True)
    return backend

def test_feature_enabled(flag_backend, mocker):
    mocker.patch(
        "django_matt.flags.backends.get_backend",
        return_value=flag_backend
    )

    from django_matt.flags import feature_enabled
    assert feature_enabled("test_feature") is True

def test_feature_disabled(flag_backend, mocker):
    flag_backend.set_flag("test_feature", enabled=False)
    mocker.patch(
        "django_matt.flags.backends.get_backend",
        return_value=flag_backend
    )

    from django_matt.flags import feature_enabled
    assert feature_enabled("test_feature") is False
```

---

## Custom Backends

Create custom backends by extending `FlagBackend`:

```python
from django_matt.flags.backends import FlagBackend, register_backend

class MyCustomBackend(FlagBackend):
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    def is_enabled(
        self,
        key: str,
        user=None,
        organization=None,
        attributes=None,
        default=False,
    ) -> bool:
        # Custom logic
        response = requests.get(
            f"{self.api_url}/flags/{key}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            params={"user_id": str(user.pk) if user else None},
        )
        if response.ok:
            return response.json().get("enabled", default)
        return default

    def get_variant(
        self,
        key: str,
        user=None,
        organization=None,
        attributes=None,
        default=None,
    ) -> str | None:
        # Custom logic
        ...

    def get_all_flags(
        self,
        user=None,
        organization=None,
        attributes=None,
    ) -> dict[str, bool]:
        # Custom logic
        ...

    def close(self):
        # Cleanup
        ...

# Register the backend
register_backend("custom", MyCustomBackend)

# Use it
FEATURE_FLAG_BACKEND = "custom"
FEATURE_FLAG_BACKEND_SETTINGS = {
    "custom": {
        "api_url": "https://flags.example.com",
        "api_key": "xxx",
    },
}
```

---

## Backend Selection Guide

```
Starting out?
└── Use Database backend

Need high performance?
├── In-memory caching sufficient → Database with use_cache=True
└── Distributed caching needed → Redis backend

Enterprise requirements?
├── Advanced targeting/analytics → LaunchDarkly
└── Self-hosted preferred → Unleash

Testing?
└── Memory backend
```

## See Also

- [Quickstart](quickstart.md) - Getting started
- [API](api.md) - REST API for flags
- [Best Practices](best-practices.md) - Performance tips

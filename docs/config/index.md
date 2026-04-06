# Configuration System

Django Matt provides a modern, flexible configuration system that organizes Django settings into modular components with environment-specific overrides.

## Overview

The configuration system is designed around three key principles:

1. **Modularity**: Settings are organized into logical components (database, cache, security, performance)
2. **Environment Awareness**: Separate settings for development, staging, and production
3. **Flexibility**: Multiple ways to configure your application based on your preferences

## Quick Start

=== "Simple Import"

    ```python
    # settings.py
    from django_matt.config.settings import configure

    # Merge common + environment settings
    locals().update(configure("dev"))  # or "staging", "prod"

    # Add your project-specific settings
    ROOT_URLCONF = "myproject.urls"
    WSGI_APPLICATION = "myproject.wsgi.application"
    ```

=== "ConfigurationManager"

    ```python
    # settings.py
    from django_matt.config import configure

    configure(
        environment="development",
        components=["database", "cache", "security"],
        extra_settings={
            "ROOT_URLCONF": "myproject.urls",
            "WSGI_APPLICATION": "myproject.wsgi.application",
        },
    )
    ```

=== "Traditional Import"

    ```python
    # settings.py
    from django_matt.config.settings.common import *
    from django_matt.config.settings.dev import *  # or staging, prod

    ROOT_URLCONF = "myproject.urls"
    WSGI_APPLICATION = "myproject.wsgi.application"
    ```

## Configuration Architecture

```
django_matt/config/
├── __init__.py           # ConfigurationManager class
├── utils.py              # Utility functions (get_env_bool, deep_merge, etc.)
├── base/                 # Base settings (common to all environments)
│   └── __init__.py
├── settings/             # Modern settings modules
│   ├── __init__.py       # configure() function
│   ├── common.py         # Shared settings
│   ├── dev.py            # Development settings
│   ├── staging.py        # Staging settings
│   └── prod.py           # Production settings
├── environments/         # Alternative environment modules
│   ├── development.py
│   ├── staging.py
│   └── production.py
└── components/           # Feature-specific settings
    ├── database.py       # Database configuration
    ├── cache.py          # Cache configuration
    ├── security.py       # Security settings
    └── performance.py    # Performance tuning
```

## ConfigurationManager

The `ConfigurationManager` class provides a programmatic way to build your configuration:

```python
from django_matt.config import ConfigurationManager

config = ConfigurationManager()

# Load base settings
config.load_base()

# Load environment-specific settings
config.load_environment("production")

# Load specific components
config.load_components(["database", "cache", "security"])

# Apply to Django settings
config.apply_to_django_settings()

# Get the final settings dictionary
settings = config.get_settings()
```

### Methods

| Method | Description |
|--------|-------------|
| `load_base()` | Load base settings common to all configurations |
| `load_environment(name)` | Load environment-specific settings (development, staging, production) |
| `load_component(name)` | Load a single component's settings |
| `load_components(names)` | Load multiple components' settings |
| `get_settings()` | Get the current settings dictionary |
| `apply_to_django_settings()` | Apply loaded settings to Django's settings module |
| `configure(...)` | All-in-one method to configure the application |

## Utility Functions

The `django_matt.config.utils` module provides helpful functions for working with environment variables:

```python
from django_matt.config.utils import (
    get_env_bool,
    get_env_int,
    get_env_float,
    get_env_list,
    get_env_dict,
    deep_merge,
)

# Boolean from environment
DEBUG = get_env_bool("DEBUG", default=False)

# Integer from environment
PORT = get_env_int("PORT", default=8000)

# Float from environment
TIMEOUT = get_env_float("TIMEOUT", default=30.0)

# List from comma-separated string
ALLOWED_HOSTS = get_env_list("ALLOWED_HOSTS", default=["localhost"])
# ALLOWED_HOSTS=localhost,example.com -> ["localhost", "example.com"]

# Dictionary from key=value pairs
CUSTOM_OPTIONS = get_env_dict("OPTIONS", default={})
# OPTIONS=key1=value1,key2=value2 -> {"key1": "value1", "key2": "value2"}

# Deep merge dictionaries
merged = deep_merge(base_settings, override_settings)
```

## Environment Detection

Django Matt supports Django version detection for conditional settings:

```python
from django_matt.config.settings.common import (
    DJANGO_VERSION,
    DJANGO_5_2_PLUS,
    DJANGO_6_0_PLUS,
)

# Use features available in Django 5.2+
if DJANGO_5_2_PLUS:
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
```

## Related Documentation

- [All Settings Reference](settings.md) - Complete list of all `DJANGO_MATT_*` settings
- [Validation & Namespaces](validation.md) - `ConfigNamespace`, built-in validators, startup validation
- [Environment Configuration](environments.md) - Dev, staging, and production setups
- [Database Configuration](database.md) - PostgreSQL, MySQL, SQLite, pgvector
- [Cache Configuration](cache.md) - Redis, Memcached, distributed caching
- [Security Configuration](security.md) - CORS, CSRF, SSL, rate limiting
- [Performance Configuration](performance.md) - Optimization and tuning

## Best Practices

### 1. Use Environment Variables for Secrets

```python
# Good: Never commit secrets
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# Bad: Hardcoded secrets
SECRET_KEY = "my-secret-key"  # Never do this!
```

### 2. Validate Production Settings

```python
from django_matt.config.settings.prod import validate_production_settings

# Call during startup to ensure required vars are set
validate_production_settings()
```

### 3. Use Components for Feature Flags

```python
# Only load what you need
configure(
    environment="production",
    components=["database", "cache"],  # Skip "security" if handled externally
)
```

### 4. Layer Your Configuration

```python
# 1. Start with common settings
from django_matt.config.settings.common import *

# 2. Apply environment settings
from django_matt.config.settings.prod import *

# 3. Add project-specific overrides
INSTALLED_APPS += ["myapp"]
MIDDLEWARE += ["myapp.middleware.CustomMiddleware"]
```

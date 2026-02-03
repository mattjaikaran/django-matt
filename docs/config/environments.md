# Environment Configuration

Django Matt provides pre-configured settings for development, staging, and production environments. Each environment is optimized for its specific use case.

## Quick Setup

=== "Development"

    ```python
    # settings.py
    from django_matt.config.settings import configure
    locals().update(configure("dev"))
    ```

=== "Staging"

    ```python
    # settings.py
    from django_matt.config.settings import configure
    locals().update(configure("staging"))
    ```

=== "Production"

    ```python
    # settings.py
    from django_matt.config.settings import configure
    locals().update(configure("prod"))
    ```

## Development Environment

The development configuration prioritizes debugging, fast iteration, and detailed logging.

### Key Features

- Debug mode enabled
- Auto-generated secret key
- Console email backend
- Local memory cache
- Verbose logging
- Password validation disabled
- Django Debug Toolbar ready

### Complete Development Settings

```python
# django_matt/config/settings/dev.py

settings = {
    # Debug enabled for development
    "DEBUG": True,

    # Auto-generated secret key (safe for dev only)
    "SECRET_KEY": secrets.token_hex(32),

    # Allow common development hosts
    "ALLOWED_HOSTS": ["localhost", "127.0.0.1", "[::1]", "0.0.0.0"],

    # Email to console for easy debugging
    "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",

    # Debug toolbar support
    "INTERNAL_IPS": ["127.0.0.1", "localhost"],

    # PostgreSQL with short connection timeout
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "django_matt_dev"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,  # Django 5.2+
        }
    },

    # Local memory cache for development
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "django-matt-dev",
        }
    },

    # No password validation in dev
    "AUTH_PASSWORD_VALIDATORS": [],

    # Verbose logging
    "LOGGING": {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "[{levelname}] {asctime} {module} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
        },
        "loggers": {
            "django": {"handlers": ["console"], "level": "INFO"},
            "django.db.backends": {
                "handlers": ["console"],
                "level": os.environ.get("SQL_LOG_LEVEL", "WARNING"),
            },
            "django_matt": {"handlers": ["console"], "level": "DEBUG"},
        },
    },

    # Django Matt settings for development
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": True,
        "CACHE_ENABLED": True,
        "CACHE_TIMEOUT": 60,
        "N1_DETECTION_ENABLED": True,
        "QUERY_OPTIMIZATION_ENABLED": True,
    },
}
```

### Development Tips

**Enable SQL Logging**

```bash
export SQL_LOG_LEVEL=DEBUG
python manage.py runserver
```

**Add Debug Toolbar**

```python
# After importing dev settings
INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
```

## Staging Environment

The staging configuration mirrors production while keeping debugging aids for QA testing.

### Key Features

- Debug mode disabled
- Security settings enabled (but relaxed SSL)
- Redis cache (if available)
- SMTP email (or console fallback)
- More verbose logging than production
- Full password validation

### Complete Staging Settings

```python
# django_matt/config/settings/staging.py

settings = {
    "DEBUG": False,

    # Required: Set via environment
    "SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY"),
    "ALLOWED_HOSTS": os.environ.get("ALLOWED_HOSTS", "").split(","),

    # Security settings (less strict than production)
    "SECURE_HSTS_SECONDS": 3600,  # 1 hour (vs 1 year in prod)
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": False,  # Don't preload in staging
    "SECURE_SSL_REDIRECT": os.environ.get("SECURE_SSL_REDIRECT", "True").lower() == "true",
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_BROWSER_XSS_FILTER": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "X_FRAME_OPTIONS": "DENY",

    # SMTP email with fallback to console
    "EMAIL_BACKEND": os.environ.get(
        "EMAIL_BACKEND",
        "django.core.mail.backends.smtp.EmailBackend"
    ),
    "EMAIL_HOST": os.environ.get("EMAIL_HOST", ""),
    "EMAIL_PORT": int(os.environ.get("EMAIL_PORT", 587)),
    "EMAIL_HOST_USER": os.environ.get("EMAIL_HOST_USER", ""),
    "EMAIL_HOST_PASSWORD": os.environ.get("EMAIL_HOST_PASSWORD", ""),
    "EMAIL_USE_TLS": True,

    # PostgreSQL with connection pooling
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "django_matt_staging"),
            "USER": os.environ.get("DB_USER", "django_matt"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 300,
            "CONN_HEALTH_CHECKS": True,
        }
    },

    # Redis cache if available, otherwise local memory
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            "KEY_PREFIX": "staging",
        }
    } if os.environ.get("REDIS_URL") else {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "django-matt-staging",
        }
    },

    # More verbose logging than production
    "LOGGING": {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
            },
        },
        "loggers": {
            "django": {"handlers": ["console"], "level": "INFO"},
            "django.request": {"handlers": ["console"], "level": "DEBUG"},
            "django_matt": {"handlers": ["console"], "level": "DEBUG"},
        },
    },

    # Django Matt settings for staging
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": True,  # Keep for performance testing
        "CACHE_ENABLED": True,
        "CACHE_TIMEOUT": 600,
        "N1_DETECTION_ENABLED": True,
        "QUERY_OPTIMIZATION_ENABLED": True,
    },

    # Full password validation
    "AUTH_PASSWORD_VALIDATORS": [
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ],
}
```

## Production Environment

The production configuration emphasizes security, performance, and reliability.

### Key Features

- Debug mode disabled (enforced)
- Full security hardening
- Required environment variables validation
- Redis cache required
- Persistent database connections
- Connection pooling ready (Django 5.2+)
- Minimal logging overhead

### Complete Production Settings

```python
# django_matt/config/settings/prod.py

settings = {
    # NEVER enable debug in production
    "DEBUG": False,

    # REQUIRED: Must be set via environment
    "SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY"),
    "ALLOWED_HOSTS": [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()],

    # Full security hardening
    "SECURE_HSTS_SECONDS": 31536000,  # 1 year
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": True,
    "SECURE_SSL_REDIRECT": True,
    "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
    "SESSION_COOKIE_SECURE": True,
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SAMESITE": "Lax",
    "CSRF_COOKIE_SECURE": True,
    "CSRF_COOKIE_HTTPONLY": True,
    "CSRF_COOKIE_SAMESITE": "Lax",
    "SECURE_BROWSER_XSS_FILTER": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "X_FRAME_OPTIONS": "DENY",

    # SMTP email configuration
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST": os.environ.get("EMAIL_HOST", ""),
    "EMAIL_PORT": int(os.environ.get("EMAIL_PORT", 587)),
    "EMAIL_HOST_USER": os.environ.get("EMAIL_HOST_USER", ""),
    "EMAIL_HOST_PASSWORD": os.environ.get("EMAIL_HOST_PASSWORD", ""),
    "EMAIL_USE_TLS": True,

    # PostgreSQL with persistent connections and optional pooling
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "django_matt"),
            "USER": os.environ.get("DB_USER", "django_matt"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": None,  # Persistent connections
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                # psycopg3 pool (Django 5.2+ with DB_POOL_ENABLED=true)
                "pool": {
                    "min_size": int(os.environ.get("DB_POOL_MIN_SIZE", 5)),
                    "max_size": int(os.environ.get("DB_POOL_MAX_SIZE", 20)),
                    "max_idle": int(os.environ.get("DB_POOL_MAX_IDLE", 300)),
                    "max_lifetime": int(os.environ.get("DB_POOL_MAX_LIFETIME", 3600)),
                }
            } if os.environ.get("DB_POOL_ENABLED", "").lower() == "true" else {},
        }
    },

    # Redis cache (required for production)
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            "KEY_PREFIX": os.environ.get("CACHE_KEY_PREFIX", "prod"),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {
                    "max_connections": int(os.environ.get("REDIS_MAX_CONNECTIONS", 50)),
                },
            },
        }
    },

    # Redis-backed sessions
    "SESSION_ENGINE": "django.contrib.sessions.backends.cache",
    "SESSION_CACHE_ALIAS": "default",

    # Structured production logging
    "LOGGING": {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
            },
            "mail_admins": {
                "level": "ERROR",
                "filters": ["require_debug_false"],
                "class": "django.utils.log.AdminEmailHandler",
            },
        },
        "loggers": {
            "django": {"handlers": ["console"], "level": "INFO"},
            "django.request": {"handlers": ["console", "mail_admins"], "level": "ERROR"},
            "django.security": {"handlers": ["console", "mail_admins"], "level": "WARNING"},
            "django_matt": {"handlers": ["console"], "level": "INFO"},
        },
    },

    # Django Matt settings optimized for production
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": False,  # Disable for performance
        "CACHE_ENABLED": True,
        "CACHE_TIMEOUT": 3600,
        "N1_DETECTION_ENABLED": False,  # Disable for performance
        "QUERY_OPTIMIZATION_ENABLED": True,
    },

    # Strict password validation
    "AUTH_PASSWORD_VALIDATORS": [
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ],

    # Admin notifications
    "ADMINS": [
        tuple(admin.split(":")) for admin in os.environ.get("ADMINS", "").split(",")
        if ":" in admin
    ],
}
```

### Production Validation

Django Matt validates required environment variables in production:

```python
from django_matt.config.settings.prod import validate_production_settings

# Called automatically when DJANGO_ENV=production
# Can also be called manually
validate_production_settings()

# Warns if missing:
# - DJANGO_SECRET_KEY
# - ALLOWED_HOSTS
# - DB_PASSWORD
```

## Environment Selection

### Using DJANGO_ENV

The recommended approach is to set the `DJANGO_ENV` environment variable:

```python
# settings.py
import os
from django_matt.config.settings import configure

env = os.environ.get("DJANGO_ENV", "development")

# Map environment names
env_map = {
    "development": "dev",
    "staging": "staging",
    "production": "prod",
}

locals().update(configure(env_map.get(env, "dev")))
```

### Shell Commands

```bash
# Development
export DJANGO_ENV=development
python manage.py runserver

# Staging
export DJANGO_ENV=staging
gunicorn myproject.wsgi

# Production
export DJANGO_ENV=production
gunicorn myproject.wsgi
```

### Docker Setup

```dockerfile
# Development
FROM python:3.12
ENV DJANGO_ENV=development
# ...

# Production
FROM python:3.12-slim
ENV DJANGO_ENV=production
ENV DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
ENV ALLOWED_HOSTS=${ALLOWED_HOSTS}
# ...
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  web:
    environment:
      - DJANGO_ENV=development
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0

# docker-compose.prod.yml
services:
  web:
    environment:
      - DJANGO_ENV=production
      - DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
      - DB_PASSWORD=${DB_PASSWORD}
```

## Complete Example Settings Files

### settings/base.py

```python
"""Base settings shared by all configurations."""
import os
from pathlib import Path
from django_matt.config.settings import configure

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment-specific settings
env = os.environ.get("DJANGO_ENV", "development")
env_map = {"development": "dev", "staging": "staging", "production": "prod"}
settings = configure(env_map.get(env, "dev"))

# Apply to module
globals().update(settings)

# Project-specific settings
ROOT_URLCONF = "myproject.urls"
WSGI_APPLICATION = "myproject.wsgi.application"
ASGI_APPLICATION = "myproject.asgi.application"

# Add project apps
INSTALLED_APPS += [
    "django_matt",
    "myproject.core",
    "myproject.api",
]

# Templates
TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]

# Static files
STATICFILES_DIRS = [BASE_DIR / "static"]
```

### Using Multiple Settings Files

Alternatively, use separate files for each environment:

```
myproject/
├── settings/
│   ├── __init__.py
│   ├── base.py      # Common settings
│   ├── dev.py       # from .base import * + dev overrides
│   ├── staging.py   # from .base import * + staging overrides
│   └── prod.py      # from .base import * + prod overrides
```

```python
# settings/dev.py
from .base import *
from django_matt.config.settings.dev import *

DEBUG = True
# Additional dev overrides...
```

```bash
# Run with specific settings
python manage.py runserver --settings=myproject.settings.dev
```

"""
Staging environment settings for Django Matt applications.

These settings are suitable for a staging/QA environment.
Similar to production but with some debugging enabled.

Usage:
    # Option 1: Import and extend
    from django_matt.config.settings.common import *
    from django_matt.config.settings.staging import *

    # Option 2: Use configure
    from django_matt.config.settings import configure
    locals().update(configure("staging"))
"""

from __future__ import annotations

import os
from typing import Any

from django_matt.config.settings.common import DJANGO_5_2_PLUS

# Staging-specific settings
settings: dict[str, Any] = {
    # ==========================================================================
    # Debug Mode (off, but with better error pages)
    # ==========================================================================
    "DEBUG": False,
    # ==========================================================================
    # Security
    # ==========================================================================
    "SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY"),  # Required
    "ALLOWED_HOSTS": os.environ.get("ALLOWED_HOSTS", "").split(","),
    # Security settings (similar to prod but can be relaxed if needed)
    "SECURE_HSTS_SECONDS": 3600,  # Shorter than prod for testing
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": False,  # Don't preload in staging
    "SECURE_SSL_REDIRECT": os.environ.get("SECURE_SSL_REDIRECT", "True").lower() == "true",
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_BROWSER_XSS_FILTER": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "X_FRAME_OPTIONS": "DENY",
    # ==========================================================================
    # Email
    # ==========================================================================
    "EMAIL_BACKEND": os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"),
    "EMAIL_HOST": os.environ.get("EMAIL_HOST", ""),
    "EMAIL_PORT": int(os.environ.get("EMAIL_PORT", 587)),
    "EMAIL_HOST_USER": os.environ.get("EMAIL_HOST_USER", ""),
    "EMAIL_HOST_PASSWORD": os.environ.get("EMAIL_HOST_PASSWORD", ""),
    "EMAIL_USE_TLS": os.environ.get("EMAIL_USE_TLS", "True").lower() == "true",
    "DEFAULT_FROM_EMAIL": os.environ.get("DEFAULT_FROM_EMAIL", "noreply@staging.example.com"),
    # ==========================================================================
    # Database (PostgreSQL with connection pooling)
    # ==========================================================================
    "DATABASES": {
        "default": {
            "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": os.environ.get("DB_NAME", "django_matt_staging"),
            "USER": os.environ.get("DB_USER", "django_matt"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            # Connection pooling for staging
            "CONN_MAX_AGE": 300,  # 5 minutes
            **({"CONN_HEALTH_CHECKS": True} if DJANGO_5_2_PLUS else {}),
            "OPTIONS": {},
        }
    },
    # ==========================================================================
    # Cache (Redis recommended for staging)
    # ==========================================================================
    "CACHES": {
        "default": {
            "BACKEND": os.environ.get(
                "CACHE_BACKEND", "django.core.cache.backends.redis.RedisCache"
            ),
            "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            "KEY_PREFIX": "staging",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
    if os.environ.get("REDIS_URL")
    else {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "django-matt-staging",
        }
    },
    # ==========================================================================
    # Logging (more verbose than prod for debugging)
    # ==========================================================================
    "LOGGING": {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                "style": "{",
            },
            "json": {
                "()": "django.utils.log.ServerFormatter",
                "format": "{levelname} {asctime} {module} {message}",
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
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": True,
            },
            "django.request": {
                "handlers": ["console"],
                "level": "DEBUG",  # More verbose for staging
                "propagate": False,
            },
            "django_matt": {
                "handlers": ["console"],
                "level": "DEBUG",  # Debug level for staging
                "propagate": True,
            },
        },
    },
    # ==========================================================================
    # Django Matt Settings for Staging
    # ==========================================================================
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": True,  # Keep timing enabled for perf testing
        "CACHE_ENABLED": True,
        "CACHE_TIMEOUT": 600,  # 10 minutes
        "N1_DETECTION_ENABLED": True,  # Keep N+1 detection on
        "QUERY_OPTIMIZATION_ENABLED": True,
    },
    # ==========================================================================
    # Password Validation (same as prod)
    # ==========================================================================
    "AUTH_PASSWORD_VALIDATORS": [
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {"min_length": 8},
        },
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ],
}


# ==========================================================================
# Export individual settings
# ==========================================================================
DEBUG = settings["DEBUG"]
SECRET_KEY = settings["SECRET_KEY"]
ALLOWED_HOSTS = settings["ALLOWED_HOSTS"]
DATABASES = settings["DATABASES"]
CACHES = settings["CACHES"]
LOGGING = settings["LOGGING"]
DJANGO_MATT = settings["DJANGO_MATT"]
AUTH_PASSWORD_VALIDATORS = settings["AUTH_PASSWORD_VALIDATORS"]


__all__ = [
    "settings",
    "DEBUG",
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "DATABASES",
    "CACHES",
    "LOGGING",
    "DJANGO_MATT",
    "AUTH_PASSWORD_VALIDATORS",
]

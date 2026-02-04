"""
Development environment settings for Django Matt applications.

These settings are suitable for local development.
Extends common.py with development-specific overrides.

Usage:
    # Option 1: Import and extend
    from django_matt.config.settings.common import *
    from django_matt.config.settings.dev import *

    # Option 2: Use configure
    from django_matt.config.settings import configure
    locals().update(configure("dev"))
"""

from __future__ import annotations

import os
import secrets
from typing import Any

from django_matt.config.settings.common import DJANGO_5_2_PLUS

# Development-specific settings
settings: dict[str, Any] = {
    # ==========================================================================
    # Debug Mode
    # ==========================================================================
    "DEBUG": True,
    # ==========================================================================
    # Security (relaxed for development)
    # ==========================================================================
    "SECRET_KEY": os.environ.get(
        "DJANGO_SECRET_KEY",
        secrets.token_hex(32),  # Auto-generate for dev if not set
    ),
    "ALLOWED_HOSTS": ["localhost", "127.0.0.1", "[::1]", "0.0.0.0"],
    # ==========================================================================
    # Email (console backend for development)
    # ==========================================================================
    "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
    # ==========================================================================
    # Additional Apps for Development
    # ==========================================================================
    "INSTALLED_APPS": [
        # Uncomment if using django-debug-toolbar
        # "debug_toolbar",
    ],
    # ==========================================================================
    # Additional Middleware for Development
    # ==========================================================================
    "MIDDLEWARE": [
        # Uncomment if using django-debug-toolbar
        # "debug_toolbar.middleware.DebugToolbarMiddleware",
    ],
    # ==========================================================================
    # Debug Toolbar Settings
    # ==========================================================================
    "INTERNAL_IPS": ["127.0.0.1", "localhost"],
    # ==========================================================================
    # Database (PostgreSQL for dev, using env vars or defaults)
    # ==========================================================================
    "DATABASES": {
        "default": {
            "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": os.environ.get("DB_NAME", "django_matt_dev"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            # Connection settings for development
            "CONN_MAX_AGE": 60,  # Shorter for dev to catch connection issues
            **({"CONN_HEALTH_CHECKS": True} if DJANGO_5_2_PLUS else {}),
            "OPTIONS": {},
        }
    },
    # ==========================================================================
    # Cache (local memory for development)
    # ==========================================================================
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "django-matt-dev",
        }
    },
    # ==========================================================================
    # Password Validation (disabled for dev convenience)
    # ==========================================================================
    "AUTH_PASSWORD_VALIDATORS": [],
    # ==========================================================================
    # Logging (verbose for development)
    # ==========================================================================
    "LOGGING": {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "[{levelname}] {asctime} {module} {message}",
                "style": "{",
            },
            "simple": {
                "format": "[{levelname}] {message}",
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
            "django.db.backends": {
                "handlers": ["console"],
                "level": os.environ.get("SQL_LOG_LEVEL", "WARNING"),  # Set to DEBUG to see SQL
                "propagate": False,
            },
            "django_matt": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": True,
            },
        },
    },
    # ==========================================================================
    # Django Matt Settings for Development
    # ==========================================================================
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": True,  # Enable timing in dev
        "CACHE_ENABLED": True,
        "CACHE_TIMEOUT": 60,  # Short timeout for dev
        "N1_DETECTION_ENABLED": True,  # Warn about N+1 queries
        "QUERY_OPTIMIZATION_ENABLED": True,
    },
}


# ==========================================================================
# Export individual settings for `from dev import *` usage
# ==========================================================================
DEBUG = settings["DEBUG"]
SECRET_KEY = settings["SECRET_KEY"]
ALLOWED_HOSTS = settings["ALLOWED_HOSTS"]
EMAIL_BACKEND = settings["EMAIL_BACKEND"]
INTERNAL_IPS = settings["INTERNAL_IPS"]
DATABASES = settings["DATABASES"]
CACHES = settings["CACHES"]
AUTH_PASSWORD_VALIDATORS = settings["AUTH_PASSWORD_VALIDATORS"]
LOGGING = settings["LOGGING"]
DJANGO_MATT = settings["DJANGO_MATT"]


__all__ = [
    "settings",
    "DEBUG",
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "EMAIL_BACKEND",
    "INTERNAL_IPS",
    "DATABASES",
    "CACHES",
    "AUTH_PASSWORD_VALIDATORS",
    "LOGGING",
    "DJANGO_MATT",
]

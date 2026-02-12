"""
Production environment settings for Django Matt applications.

These settings are suitable for production deployment.
Emphasizes security, performance, and reliability.

Usage:
    # Option 1: Import and extend
    from django_matt.config.settings.common import *
    from django_matt.config.settings.prod import *

    # Option 2: Use configure
    from django_matt.config.settings import configure
    locals().update(configure("prod"))
"""

from __future__ import annotations

import os
from typing import Any

from django_matt.config.settings.common import DJANGO_5_2_PLUS


def _get_bool_env(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


# Production-specific settings
settings: dict[str, Any] = {
    # ==========================================================================
    # Debug Mode (NEVER enable in production)
    # ==========================================================================
    "DEBUG": False,
    # ==========================================================================
    # Security (strict settings for production)
    # ==========================================================================
    "SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY"),  # REQUIRED
    "ALLOWED_HOSTS": [
        h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
    ],
    # HSTS - HTTP Strict Transport Security
    "SECURE_HSTS_SECONDS": 31536000,  # 1 year
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": True,
    # SSL/TLS
    "SECURE_SSL_REDIRECT": _get_bool_env("SECURE_SSL_REDIRECT", True),
    "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
    # Cookies
    "SESSION_COOKIE_SECURE": True,
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SAMESITE": "Lax",
    "CSRF_COOKIE_SECURE": True,
    "CSRF_COOKIE_HTTPONLY": True,
    "CSRF_COOKIE_SAMESITE": "Lax",
    # Security headers
    "SECURE_BROWSER_XSS_FILTER": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "X_FRAME_OPTIONS": "DENY",
    # Content Security Policy (configure based on your needs)
    # "CSP_DEFAULT_SRC": ("'self'",),
    # ==========================================================================
    # Email
    # ==========================================================================
    "EMAIL_BACKEND": os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"),
    "EMAIL_HOST": os.environ.get("EMAIL_HOST", ""),
    "EMAIL_PORT": int(os.environ.get("EMAIL_PORT", 587)),
    "EMAIL_HOST_USER": os.environ.get("EMAIL_HOST_USER", ""),
    "EMAIL_HOST_PASSWORD": os.environ.get("EMAIL_HOST_PASSWORD", ""),
    "EMAIL_USE_TLS": _get_bool_env("EMAIL_USE_TLS", True),
    "EMAIL_USE_SSL": _get_bool_env("EMAIL_USE_SSL", False),
    "DEFAULT_FROM_EMAIL": os.environ.get("DEFAULT_FROM_EMAIL", "noreply@example.com"),
    "SERVER_EMAIL": os.environ.get("SERVER_EMAIL", os.environ.get("DEFAULT_FROM_EMAIL", "")),
    # ==========================================================================
    # Database (PostgreSQL with connection pooling)
    # ==========================================================================
    "DATABASES": {
        "default": {
            "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": os.environ.get("DB_NAME", "django_matt"),
            "USER": os.environ.get("DB_USER", "django_matt"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            # Persistent connections for production
            "CONN_MAX_AGE": None,  # Keep connections open
            **({"CONN_HEALTH_CHECKS": True} if DJANGO_5_2_PLUS else {}),
            "OPTIONS": {
                # Add psycopg3 pool options if using Django 5.2+
                **(
                    {
                        "pool": {
                            "min_size": int(os.environ.get("DB_POOL_MIN_SIZE", 5)),
                            "max_size": int(os.environ.get("DB_POOL_MAX_SIZE", 20)),
                            "max_idle": int(os.environ.get("DB_POOL_MAX_IDLE", 300)),
                            "max_lifetime": int(os.environ.get("DB_POOL_MAX_LIFETIME", 3600)),
                        }
                    }
                    if DJANGO_5_2_PLUS and _get_bool_env("DB_POOL_ENABLED", True)
                    else {}
                ),
            },
        }
    },
    # ==========================================================================
    # Cache (Redis required for production)
    # ==========================================================================
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
    # ==========================================================================
    # Sessions (Redis-backed for scalability)
    # ==========================================================================
    "SESSION_ENGINE": "django.contrib.sessions.backends.cache",
    "SESSION_CACHE_ALIAS": "default",
    "SESSION_COOKIE_AGE": int(os.environ.get("SESSION_COOKIE_AGE", 1209600)),  # 2 weeks
    # ==========================================================================
    # Logging (structured logging for production)
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
        "filters": {
            "require_debug_false": {
                "()": "django.utils.log.RequireDebugFalse",
            },
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
            "mail_admins": {
                "level": "ERROR",
                "filters": ["require_debug_false"],
                "class": "django.utils.log.AdminEmailHandler",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": True,
            },
            "django.request": {
                "handlers": ["console", "mail_admins"],
                "level": "ERROR",
                "propagate": False,
            },
            "django.security": {
                "handlers": ["console", "mail_admins"],
                "level": "WARNING",
                "propagate": False,
            },
            "django_matt": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": True,
            },
        },
    },
    # ==========================================================================
    # Static & Media Files (typically served by CDN/S3 in production)
    # ==========================================================================
    "STATIC_URL": os.environ.get("STATIC_URL", "/static/"),
    "STATIC_ROOT": os.environ.get("STATIC_ROOT", "/var/www/static"),
    "MEDIA_URL": os.environ.get("MEDIA_URL", "/media/"),
    "MEDIA_ROOT": os.environ.get("MEDIA_ROOT", "/var/www/media"),
    # Optional: S3/CloudFront storage
    # "STORAGES": {
    #     "default": {
    #         "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    #     },
    #     "staticfiles": {
    #         "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
    #     },
    # },
    # ==========================================================================
    # Django Matt Settings for Production
    # ==========================================================================
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": False,  # Disable timing overhead in prod
        "CACHE_ENABLED": True,
        "CACHE_TIMEOUT": 3600,  # 1 hour
        "N1_DETECTION_ENABLED": False,  # Disable in prod for performance
        "QUERY_OPTIMIZATION_ENABLED": True,
    },
    # ==========================================================================
    # Password Validation (strict for production)
    # ==========================================================================
    "AUTH_PASSWORD_VALIDATORS": [
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {"min_length": 10},
        },
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ],
    # ==========================================================================
    # Admin Configuration
    # ==========================================================================
    "ADMINS": [
        tuple(admin.split(":")) for admin in os.environ.get("ADMINS", "").split(",") if ":" in admin
    ],
    "MANAGERS": [
        tuple(manager.split(":"))
        for manager in os.environ.get("MANAGERS", "").split(",")
        if ":" in manager
    ],
}


# ==========================================================================
# Validate required environment variables
# ==========================================================================
def validate_production_settings():
    """Validate that required production settings are configured."""
    required_vars = [
        "DJANGO_SECRET_KEY",
        "ALLOWED_HOSTS",
        "DB_PASSWORD",
    ]
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        import warnings

        warnings.warn(
            f"Missing required environment variables for production: {', '.join(missing)}",
            RuntimeWarning,
        )


# Only validate if this module is imported directly (not in tests)
if os.environ.get("DJANGO_ENV") == "production":
    validate_production_settings()


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
    "validate_production_settings",
]

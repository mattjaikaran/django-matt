"""
Staging environment settings for Django Matt applications.

These settings are suitable for staging/testing environments.
"""

import os

# Staging-specific settings
settings = {
    "DEBUG": False,
    "SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY"),  # Must be set in environment variables
    "ALLOWED_HOSTS": os.environ.get("ALLOWED_HOSTS", "").split(","),
    # Security settings (less strict than production)
    "SECURE_SSL_REDIRECT": False,
    "SESSION_COOKIE_SECURE": False,
    "CSRF_COOKIE_SECURE": False,
    # Email backend for staging
    "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
    # Logging configuration
    "LOGGING": {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
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
            "django_matt": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": True,
            },
        },
    },
    # Django Matt specific settings for staging
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": True,
        "CACHE_ENABLED": True,
        "CACHE_TIMEOUT": 300,  # 5 minutes
        "DB_TYPE": "postgres",  # Default to PostgreSQL
    },
    # Database settings for staging
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "django_matt_staging"),
            "USER": os.environ.get("DB_USER", "django_matt"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", 600)),
            "OPTIONS": {},
        }
    },
    # Password validation (same as production)
    "AUTH_PASSWORD_VALIDATORS": [
        {
            "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {
                "min_length": 10,
            },
        },
        {
            "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
        },
    ],
}

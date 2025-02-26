"""
Production environment settings for Django Matt applications.

These settings are suitable for production deployment.
"""

import os

# Production-specific settings
settings = {
    "DEBUG": False,
    "SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY"),  # Must be set in environment variables
    "ALLOWED_HOSTS": os.environ.get("ALLOWED_HOSTS", "").split(","),
    # Security settings
    "SECURE_HSTS_SECONDS": 31536000,  # 1 year
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": True,
    "SECURE_SSL_REDIRECT": True,
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_BROWSER_XSS_FILTER": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "X_FRAME_OPTIONS": "DENY",
    # Email backend for production
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST": os.environ.get("EMAIL_HOST"),
    "EMAIL_PORT": int(os.environ.get("EMAIL_PORT", 587)),
    "EMAIL_HOST_USER": os.environ.get("EMAIL_HOST_USER"),
    "EMAIL_HOST_PASSWORD": os.environ.get("EMAIL_HOST_PASSWORD"),
    "EMAIL_USE_TLS": True,
    "DEFAULT_FROM_EMAIL": os.environ.get("DEFAULT_FROM_EMAIL"),
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
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
            "file": {
                "level": "INFO",
                "class": "logging.FileHandler",
                "filename": "/var/log/django/django_matt.log",
                "formatter": "verbose",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": True,
            },
            "django_matt": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": True,
            },
        },
    },
    # Django Matt specific settings for production
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": False,
        "CACHE_ENABLED": True,
        "CACHE_TIMEOUT": 3600,  # 1 hour
        "DB_TYPE": "postgres",  # Default to PostgreSQL
    },
    # Database settings for production
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "django_matt"),
            "USER": os.environ.get("DB_USER", "django_matt"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", 600)),
            "OPTIONS": {},
        }
    },
    # Password validation
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

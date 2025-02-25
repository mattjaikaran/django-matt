"""
Development environment settings for Django Matt applications.

These settings are suitable for local development.
"""

import secrets

# Development-specific settings
settings = {
    "DEBUG": True,
    "SECRET_KEY": secrets.token_hex(32),  # Generate a random secret key for development
    "ALLOWED_HOSTS": ["localhost", "127.0.0.1", "[::1]"],
    # Email backend for development
    "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
    # Django Debug Toolbar settings
    "INSTALLED_APPS": [
        "debug_toolbar",
    ],
    "MIDDLEWARE": [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ],
    "INTERNAL_IPS": [
        "127.0.0.1",
    ],
    # Django Matt specific settings for development
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": True,
        "CACHE_ENABLED": True,
    },
    # Disable password validation in development
    "AUTH_PASSWORD_VALIDATORS": [],
}

"""
Cache settings for Django Matt applications.

This module contains settings for configuring the cache backend.
"""

import os

# Cache settings
settings = {
    "CACHES": {
        "default": {
            "BACKEND": os.environ.get(
                "CACHE_BACKEND", "django.core.cache.backends.locmem.LocMemCache"
            ),
            "LOCATION": os.environ.get("CACHE_LOCATION", "django_matt"),
            "TIMEOUT": int(os.environ.get("CACHE_TIMEOUT", 300)),
            "OPTIONS": {},
            "KEY_PREFIX": os.environ.get("CACHE_KEY_PREFIX", "django_matt"),
        }
    },
    # Redis cache settings (if using Redis)
    "REDIS_URL": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    # Cache middleware settings
    "CACHE_MIDDLEWARE_ALIAS": "default",
    "CACHE_MIDDLEWARE_SECONDS": int(os.environ.get("CACHE_MIDDLEWARE_SECONDS", 600)),
    "CACHE_MIDDLEWARE_KEY_PREFIX": os.environ.get(
        "CACHE_MIDDLEWARE_KEY_PREFIX", "django_matt"
    ),
    # Django Matt cache settings
    "DJANGO_MATT": {
        "CACHE_ENABLED": os.environ.get("DJANGO_MATT_CACHE_ENABLED", "True").lower()
        == "true",
        "CACHE_TIMEOUT": int(os.environ.get("DJANGO_MATT_CACHE_TIMEOUT", 300)),
        "CACHE_KEY_PREFIX": os.environ.get(
            "DJANGO_MATT_CACHE_KEY_PREFIX", "django_matt:"
        ),
    },
}

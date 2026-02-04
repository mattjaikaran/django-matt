"""
Cache settings for Django Matt applications.

This module contains settings for configuring the cache backend,
with first-class support for Redis.

Supports multiple cache backends:
- Redis (recommended for production)
- Memcached
- Local memory (for development)
- File-based
- Database

Usage:
    # Option 1: Environment variables
    export CACHE_BACKEND=redis
    export REDIS_URL=redis://localhost:6379/0

    # Option 2: Programmatic configuration
    from django_matt.config.components.cache import configure_cache

    CACHES = {
        "default": configure_cache(
            backend="redis",
            url="redis://localhost:6379/0",
            key_prefix="myapp",
        )
    }
"""

from __future__ import annotations

import os
from typing import Any


def _get_bool_env(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


def get_redis_cache_config(
    url: str | None = None,
    key_prefix: str = "django_matt",
    timeout: int = 300,
    max_connections: int = 50,
    socket_timeout: int = 5,
    socket_connect_timeout: int = 5,
    retry_on_timeout: bool = True,
    **extra_options: Any,
) -> dict[str, Any]:
    """
    Get Redis cache configuration.

    Args:
        url: Redis URL (e.g., "redis://localhost:6379/0")
        key_prefix: Prefix for all cache keys
        timeout: Default cache timeout in seconds
        max_connections: Maximum connections in the pool
        socket_timeout: Socket timeout in seconds
        socket_connect_timeout: Socket connection timeout in seconds
        retry_on_timeout: Whether to retry on timeout
        **extra_options: Additional options to pass to the cache backend

    Returns:
        Cache configuration dictionary for Django's CACHES setting

    Example:
        CACHES = {
            "default": get_redis_cache_config(
                url="redis://localhost:6379/0",
                key_prefix="myapp",
                max_connections=100,
            )
        }
    """
    redis_url = url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    config: dict[str, Any] = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": redis_url,
        "KEY_PREFIX": key_prefix,
        "TIMEOUT": timeout,
        "OPTIONS": {
            "CLIENT_CLASS": extra_options.pop("client_class", "django_redis.client.DefaultClient"),
            "CONNECTION_POOL_KWARGS": {
                "max_connections": max_connections,
                "socket_timeout": socket_timeout,
                "socket_connect_timeout": socket_connect_timeout,
                "retry_on_timeout": retry_on_timeout,
            },
            **extra_options,
        },
    }

    return config


def get_redis_sentinel_config(
    sentinels: list[tuple[str, int]],
    master_name: str = "mymaster",
    key_prefix: str = "django_matt",
    timeout: int = 300,
    password: str | None = None,
    **extra_options: Any,
) -> dict[str, Any]:
    """
    Get Redis Sentinel cache configuration for high availability.

    Args:
        sentinels: List of (host, port) tuples for Sentinel nodes
        master_name: Name of the Redis master
        key_prefix: Prefix for all cache keys
        timeout: Default cache timeout in seconds
        password: Redis password (optional)
        **extra_options: Additional options

    Returns:
        Cache configuration dictionary

    Example:
        CACHES = {
            "default": get_redis_sentinel_config(
                sentinels=[("sentinel1", 26379), ("sentinel2", 26379)],
                master_name="mymaster",
            )
        }
    """
    config: dict[str, Any] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{master_name}/0",
        "KEY_PREFIX": key_prefix,
        "TIMEOUT": timeout,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.SentinelClient",
            "SENTINELS": sentinels,
            "SENTINEL_KWARGS": {},
            **extra_options,
        },
    }

    if password:
        config["OPTIONS"]["PASSWORD"] = password

    return config


def get_redis_cluster_config(
    startup_nodes: list[dict[str, Any]],
    key_prefix: str = "django_matt",
    timeout: int = 300,
    skip_full_coverage_check: bool = True,
    **extra_options: Any,
) -> dict[str, Any]:
    """
    Get Redis Cluster cache configuration for horizontal scaling.

    Args:
        startup_nodes: List of {"host": "...", "port": ...} dicts
        key_prefix: Prefix for all cache keys
        timeout: Default cache timeout in seconds
        skip_full_coverage_check: Skip full coverage check on startup
        **extra_options: Additional options

    Returns:
        Cache configuration dictionary

    Example:
        CACHES = {
            "default": get_redis_cluster_config(
                startup_nodes=[
                    {"host": "node1", "port": 6379},
                    {"host": "node2", "port": 6379},
                ],
            )
        }
    """
    return {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://cluster",
        "KEY_PREFIX": key_prefix,
        "TIMEOUT": timeout,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "REDIS_CLIENT_CLASS": "redis.cluster.RedisCluster",
            "REDIS_CLIENT_KWARGS": {
                "startup_nodes": startup_nodes,
                "skip_full_coverage_check": skip_full_coverage_check,
            },
            **extra_options,
        },
    }


def get_memcached_config(
    location: str | list[str] | None = None,
    key_prefix: str = "django_matt",
    timeout: int = 300,
    **extra_options: Any,
) -> dict[str, Any]:
    """
    Get Memcached cache configuration.

    Args:
        location: Memcached server(s) location
        key_prefix: Prefix for all cache keys
        timeout: Default cache timeout in seconds
        **extra_options: Additional options

    Returns:
        Cache configuration dictionary

    Example:
        CACHES = {
            "default": get_memcached_config(
                location=["memcached1:11211", "memcached2:11211"],
            )
        }
    """
    loc = location or os.environ.get("MEMCACHED_LOCATION", "127.0.0.1:11211")
    if isinstance(loc, str) and "," in loc:
        loc = [s.strip() for s in loc.split(",")]

    return {
        "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
        "LOCATION": loc,
        "KEY_PREFIX": key_prefix,
        "TIMEOUT": timeout,
        "OPTIONS": extra_options,
    }


def get_locmem_config(
    name: str = "django_matt",
    key_prefix: str = "django_matt",
    timeout: int = 300,
    max_entries: int = 1000,
) -> dict[str, Any]:
    """
    Get local memory cache configuration (for development).

    Args:
        name: Unique name for the cache
        key_prefix: Prefix for all cache keys
        timeout: Default cache timeout in seconds
        max_entries: Maximum number of entries

    Returns:
        Cache configuration dictionary
    """
    return {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": name,
        "KEY_PREFIX": key_prefix,
        "TIMEOUT": timeout,
        "OPTIONS": {
            "MAX_ENTRIES": max_entries,
        },
    }


def get_file_cache_config(
    location: str = "/tmp/django_cache",
    key_prefix: str = "django_matt",
    timeout: int = 300,
    max_entries: int = 10000,
) -> dict[str, Any]:
    """
    Get file-based cache configuration.

    Args:
        location: Directory for cache files
        key_prefix: Prefix for all cache keys
        timeout: Default cache timeout in seconds
        max_entries: Maximum number of entries

    Returns:
        Cache configuration dictionary
    """
    return {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": location,
        "KEY_PREFIX": key_prefix,
        "TIMEOUT": timeout,
        "OPTIONS": {
            "MAX_ENTRIES": max_entries,
        },
    }


def configure_cache(
    backend: str = "auto",
    url: str | None = None,
    key_prefix: str = "django_matt",
    timeout: int = 300,
    **extra_options: Any,
) -> dict[str, Any]:
    """
    Configure cache with automatic backend detection.

    Args:
        backend: Cache backend ("redis", "memcached", "locmem", "file", or "auto")
        url: Connection URL (for redis/memcached)
        key_prefix: Prefix for all cache keys
        timeout: Default cache timeout in seconds
        **extra_options: Backend-specific options

    Returns:
        Cache configuration dictionary

    Example:
        CACHES = {
            "default": configure_cache(
                backend="auto",  # Auto-detect from environment
                key_prefix="myapp",
                timeout=600,
            )
        }
    """
    # Auto-detect backend from environment
    if backend == "auto":
        if os.environ.get("REDIS_URL"):
            backend = "redis"
        elif os.environ.get("MEMCACHED_LOCATION"):
            backend = "memcached"
        else:
            # Default to locmem for development
            backend = "locmem"

    # Get configuration based on backend
    if backend == "redis":
        return get_redis_cache_config(
            url=url or os.environ.get("REDIS_URL"),
            key_prefix=key_prefix,
            timeout=timeout,
            **extra_options,
        )
    if backend == "memcached":
        return get_memcached_config(
            location=url or os.environ.get("MEMCACHED_LOCATION"),
            key_prefix=key_prefix,
            timeout=timeout,
            **extra_options,
        )
    if backend == "file":
        return get_file_cache_config(
            location=url or extra_options.pop("location", "/tmp/django_cache"),
            key_prefix=key_prefix,
            timeout=timeout,
            **extra_options,
        )
    # locmem
    return get_locmem_config(
        name=url or "django_matt",
        key_prefix=key_prefix,
        timeout=timeout,
        **extra_options,
    )


# ==========================================================================
# Default settings based on environment variables
# ==========================================================================

# Detect cache backend from environment
CACHE_BACKEND = os.environ.get("CACHE_BACKEND", "auto").lower()
CACHE_TIMEOUT = int(os.environ.get("CACHE_TIMEOUT", 300))
CACHE_KEY_PREFIX = os.environ.get("CACHE_KEY_PREFIX", "django_matt")

# Build default cache configuration
default_cache_config = configure_cache(
    backend=CACHE_BACKEND,
    key_prefix=CACHE_KEY_PREFIX,
    timeout=CACHE_TIMEOUT,
)

# Cache settings to export
settings: dict[str, Any] = {
    "CACHES": {
        "default": default_cache_config,
    },
    # Redis cache settings (if using Redis)
    "REDIS_URL": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    # Cache middleware settings
    "CACHE_MIDDLEWARE_ALIAS": "default",
    "CACHE_MIDDLEWARE_SECONDS": int(os.environ.get("CACHE_MIDDLEWARE_SECONDS", 600)),
    "CACHE_MIDDLEWARE_KEY_PREFIX": CACHE_KEY_PREFIX,
    # Django Matt cache settings
    "DJANGO_MATT": {
        "CACHE_ENABLED": _get_bool_env("DJANGO_MATT_CACHE_ENABLED", True),
        "CACHE_TIMEOUT": CACHE_TIMEOUT,
        "CACHE_KEY_PREFIX": f"{CACHE_KEY_PREFIX}:",
    },
}


__all__ = [
    "settings",
    "configure_cache",
    "get_redis_cache_config",
    "get_redis_sentinel_config",
    "get_redis_cluster_config",
    "get_memcached_config",
    "get_locmem_config",
    "get_file_cache_config",
]

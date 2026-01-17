"""
Storage backends for throttle data.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Any


class BaseBackend(ABC):
    """
    Abstract base class for throttle storage backends.

    Backends must implement get, set, and delete methods for
    storing and retrieving throttle history data.
    """

    @abstractmethod
    def get(self, key: str) -> list[float] | None:
        """
        Get the throttle history for a key.

        Args:
            key: The cache key

        Returns:
            List of timestamps or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: list[float], ttl: int | None = None) -> None:
        """
        Store throttle history for a key.

        Args:
            key: The cache key
            value: List of timestamps
            ttl: Time to live in seconds (optional)
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Delete throttle history for a key.

        Args:
            key: The cache key
        """
        raise NotImplementedError

    def clear(self) -> None:
        """
        Clear all throttle data.

        Optional method - not all backends may support this.
        """
        pass


class InMemoryBackend(BaseBackend):
    """
    In-memory storage backend for development and testing.

    Stores throttle data in a thread-safe dictionary.
    Not suitable for production with multiple processes.

    Example:
        from django_matt.throttling import InMemoryBackend

        backend = InMemoryBackend()
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[list[float], float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> list[float] | None:
        """
        Get throttle history from memory.

        Args:
            key: The cache key

        Returns:
            List of timestamps or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                return None

            value, expires_at = self._cache[key]

            # Check if expired
            if expires_at and time.time() > expires_at:
                del self._cache[key]
                return None

            return value

    def set(self, key: str, value: list[float], ttl: int | None = None) -> None:
        """
        Store throttle history in memory.

        Args:
            key: The cache key
            value: List of timestamps
            ttl: Time to live in seconds
        """
        with self._lock:
            expires_at = time.time() + ttl if ttl else None
            self._cache[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        """
        Delete throttle history from memory.

        Args:
            key: The cache key
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all throttle data from memory."""
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        now = time.time()
        with self._lock:
            expired_keys = [
                key for key, (_, expires_at) in self._cache.items()
                if expires_at and now > expires_at
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        return removed


class RedisBackend(BaseBackend):
    """
    Redis storage backend for production use.

    Supports distributed throttling across multiple processes/servers.

    Example:
        from django_matt.throttling import RedisBackend
        import redis

        # Using redis-py client
        client = redis.Redis(host='localhost', port=6379, db=0)
        backend = RedisBackend(client)

        # Or from Django cache
        backend = RedisBackend.from_django_cache('default')
    """

    def __init__(self, client: Any = None, prefix: str = "django_matt:throttle:") -> None:
        """
        Initialize Redis backend.

        Args:
            client: Redis client instance (redis-py or compatible)
            prefix: Key prefix for namespacing
        """
        self.client = client
        self.prefix = prefix

    @classmethod
    def from_django_cache(cls, cache_name: str = "default") -> "RedisBackend":
        """
        Create backend from Django cache configuration.

        Args:
            cache_name: Name of the Django cache to use

        Returns:
            RedisBackend instance
        """
        from django.core.cache import caches

        cache = caches[cache_name]

        # Try to get the underlying Redis client
        if hasattr(cache, "_cache"):
            # django-redis
            client = cache._cache.get_client()
        elif hasattr(cache, "client"):
            client = cache.client
        else:
            raise ValueError(
                f"Cache '{cache_name}' does not appear to be a Redis cache. "
                "Please configure a Redis cache or provide a redis client directly."
            )

        return cls(client=client)

    def _make_key(self, key: str) -> str:
        """Create full Redis key with prefix."""
        return f"{self.prefix}{key}"

    def get(self, key: str) -> list[float] | None:
        """
        Get throttle history from Redis.

        Args:
            key: The cache key

        Returns:
            List of timestamps or None if not found
        """
        if self.client is None:
            return None

        import json

        full_key = self._make_key(key)
        data = self.client.get(full_key)

        if data is None:
            return None

        try:
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            return json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def set(self, key: str, value: list[float], ttl: int | None = None) -> None:
        """
        Store throttle history in Redis.

        Args:
            key: The cache key
            value: List of timestamps
            ttl: Time to live in seconds
        """
        if self.client is None:
            return

        import json

        full_key = self._make_key(key)
        data = json.dumps(value)

        if ttl:
            self.client.setex(full_key, ttl, data)
        else:
            self.client.set(full_key, data)

    def delete(self, key: str) -> None:
        """
        Delete throttle history from Redis.

        Args:
            key: The cache key
        """
        if self.client is None:
            return

        full_key = self._make_key(key)
        self.client.delete(full_key)

    def clear(self) -> None:
        """
        Clear all throttle data from Redis.

        Uses SCAN to find all keys with the prefix.
        """
        if self.client is None:
            return

        pattern = f"{self.prefix}*"
        cursor = 0

        while True:
            cursor, keys = self.client.scan(cursor, match=pattern, count=100)
            if keys:
                self.client.delete(*keys)
            if cursor == 0:
                break


class DjangoCacheBackend(BaseBackend):
    """
    Backend using Django's cache framework.

    Works with any Django cache backend (Redis, Memcached, etc).

    Example:
        from django_matt.throttling import DjangoCacheBackend

        # Use default cache
        backend = DjangoCacheBackend()

        # Use specific cache
        backend = DjangoCacheBackend(cache_name='throttle')
    """

    def __init__(self, cache_name: str = "default", prefix: str = "throttle:") -> None:
        """
        Initialize Django cache backend.

        Args:
            cache_name: Name of the Django cache to use
            prefix: Key prefix for namespacing
        """
        self.cache_name = cache_name
        self.prefix = prefix

    @property
    def cache(self) -> Any:
        """Get the Django cache instance."""
        from django.core.cache import caches
        return caches[self.cache_name]

    def _make_key(self, key: str) -> str:
        """Create full cache key with prefix."""
        return f"{self.prefix}{key}"

    def get(self, key: str) -> list[float] | None:
        """
        Get throttle history from Django cache.

        Args:
            key: The cache key

        Returns:
            List of timestamps or None if not found
        """
        full_key = self._make_key(key)
        return self.cache.get(full_key)

    def set(self, key: str, value: list[float], ttl: int | None = None) -> None:
        """
        Store throttle history in Django cache.

        Args:
            key: The cache key
            value: List of timestamps
            ttl: Time to live in seconds
        """
        full_key = self._make_key(key)
        self.cache.set(full_key, value, timeout=ttl)

    def delete(self, key: str) -> None:
        """
        Delete throttle history from Django cache.

        Args:
            key: The cache key
        """
        full_key = self._make_key(key)
        self.cache.delete(full_key)


# Default backend (can be overridden in settings)
_default_backend: BaseBackend | None = None


def get_default_backend() -> BaseBackend:
    """
    Get the default throttle backend.

    Checks Django settings for THROTTLE_BACKEND configuration,
    falls back to InMemoryBackend.

    Returns:
        Configured or default backend instance
    """
    global _default_backend

    if _default_backend is not None:
        return _default_backend

    try:
        from django.conf import settings

        backend_config = getattr(settings, "THROTTLE_BACKEND", None)

        if backend_config is None:
            _default_backend = InMemoryBackend()
        elif isinstance(backend_config, str):
            if backend_config == "memory":
                _default_backend = InMemoryBackend()
            elif backend_config == "redis":
                _default_backend = RedisBackend.from_django_cache()
            elif backend_config == "cache":
                _default_backend = DjangoCacheBackend()
            else:
                raise ValueError(f"Unknown throttle backend: {backend_config}")
        elif isinstance(backend_config, dict):
            backend_type = backend_config.get("type", "memory")
            if backend_type == "memory":
                _default_backend = InMemoryBackend()
            elif backend_type == "redis":
                cache_name = backend_config.get("cache", "default")
                _default_backend = RedisBackend.from_django_cache(cache_name)
            elif backend_type == "cache":
                cache_name = backend_config.get("cache", "default")
                prefix = backend_config.get("prefix", "throttle:")
                _default_backend = DjangoCacheBackend(cache_name, prefix)
            else:
                raise ValueError(f"Unknown throttle backend type: {backend_type}")
        elif isinstance(backend_config, BaseBackend):
            _default_backend = backend_config
        else:
            _default_backend = InMemoryBackend()

    except Exception:
        _default_backend = InMemoryBackend()

    return _default_backend


def set_default_backend(backend: BaseBackend) -> None:
    """
    Set the default throttle backend.

    Args:
        backend: Backend instance to use as default
    """
    global _default_backend
    _default_backend = backend

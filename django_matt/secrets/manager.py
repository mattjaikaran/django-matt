from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from django_matt.secrets.backends import EnvBackend, SecretsBackend

logger = logging.getLogger("django_matt.secrets")

_manager_instance: SecretsManager | None = None
_manager_lock = asyncio.Lock()


class SecretReference:
    """Reference to a secret by URI.

    Supports formats:
        env://VAR_NAME
        vault://path/to/secret
        aws://secret-name
        gcp://secret-name
        file://path/to/encrypted.json#key
        plain://literal-value (for testing)
    """

    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._scheme, _, self._path = uri.partition("://")
        if not self._path:
            raise ValueError(f"invalid secret reference: {uri}")

    @property
    def scheme(self) -> str:
        return self._scheme

    @property
    def path(self) -> str:
        return self._path

    @property
    def uri(self) -> str:
        return self._uri

    def __repr__(self) -> str:
        return f"SecretReference('{self._scheme}://***')"

    def __str__(self) -> str:
        return f"{self._scheme}://***"


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: str, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl


class SecretsManager:
    """Central secrets manager with caching and multi-backend support."""

    def __init__(
        self,
        backend: SecretsBackend | None = None,
        backends: dict[str, SecretsBackend] | None = None,
        cache_ttl: float = 300.0,
    ) -> None:
        self._default_backend = backend or EnvBackend()
        self._backends: dict[str, SecretsBackend] = backends or {}
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_ttl = cache_ttl
        self._rotation_hooks: dict[str, list[Any]] = {}

    def register_backend(self, scheme: str, backend: SecretsBackend) -> None:
        self._backends[scheme] = backend

    def _get_backend(self, scheme: str | None = None) -> SecretsBackend:
        if scheme and scheme in self._backends:
            return self._backends[scheme]
        return self._default_backend

    def _check_cache(self, key: str) -> str | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            return None
        return entry.value

    def _set_cache(self, key: str, value: str) -> None:
        self._cache[key] = _CacheEntry(value, self._cache_ttl)

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        self._cache.clear()

    async def get(self, key: str, default: str | None = None) -> str | None:
        cached = self._check_cache(key)
        if cached is not None:
            return cached

        backend = self._get_backend()
        value = await backend.get(key)
        if value is None:
            return default
        self._set_cache(key, value)
        return value

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        uncached: list[str] = []

        for key in keys:
            cached = self._check_cache(key)
            if cached is not None:
                result[key] = cached
            else:
                uncached.append(key)

        if uncached:
            backend = self._get_backend()
            fetched = await backend.get_many(uncached)
            for key, value in fetched.items():
                if value is not None:
                    self._set_cache(key, value)
                result[key] = value

        return result

    async def set(self, key: str, value: str) -> None:
        backend = self._get_backend()
        await backend.set(key, value)
        self._set_cache(key, value)
        logger.info("secret stored: %s", key)

    async def delete(self, key: str) -> None:
        backend = self._get_backend()
        await backend.delete(key)
        self.invalidate(key)
        logger.info("secret deleted: %s", key)

    async def resolve_ref(self, ref: SecretReference) -> str | None:
        if ref.scheme == "plain":
            return ref.path

        cache_key = ref.uri
        cached = self._check_cache(cache_key)
        if cached is not None:
            return cached

        backend = self._get_backend(ref.scheme)
        value = await backend.get(ref.path)
        if value is not None:
            self._set_cache(cache_key, value)
        return value

    async def rotate(self, key: str) -> None:
        self.invalidate(key)
        logger.info("secret rotated: %s", key)
        hooks = self._rotation_hooks.get(key, [])
        for hook in hooks:
            if asyncio.iscoroutinefunction(hook):
                await hook(key)
            else:
                hook(key)

    def on_rotation(self, key: str, callback: Any) -> None:
        self._rotation_hooks.setdefault(key, []).append(callback)

    async def list_keys(self) -> list[str]:
        backend = self._get_backend()
        return await backend.list_keys()


def get_secrets_manager(**kwargs: Any) -> SecretsManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SecretsManager(**kwargs)
    return _manager_instance


def reset_secrets_manager() -> None:
    global _manager_instance
    _manager_instance = None

"""Public API for token blacklisting."""

from __future__ import annotations

import time
from datetime import datetime

_backend = None


def _get_backend():
    """Lazily load the configured blacklist backend."""
    global _backend
    if _backend is None:
        from .config import blacklist_config

        if blacklist_config.backend == "cache":
            from .backends import CacheBlacklistBackend

            _backend = CacheBlacklistBackend()
        elif blacklist_config.backend == "database":
            from .backends import DatabaseBlacklistBackend

            _backend = DatabaseBlacklistBackend()
        else:
            from .backends import NullBlacklistBackend

            _backend = NullBlacklistBackend()
    return _backend


def reset_backend() -> None:
    """Reset the cached backend instance. Useful for testing."""
    global _backend
    _backend = None


def blacklist_token(jti: str, expires_at: datetime) -> None:
    """Add a token to the blacklist (sync)."""
    _get_backend().add(jti, expires_at)


async def ablacklist_token(jti: str, expires_at: datetime) -> None:
    """Add a token to the blacklist (async)."""
    await _get_backend().aadd(jti, expires_at)


def is_token_blacklisted(jti: str) -> bool:
    """Check if a token is blacklisted (sync)."""
    return _get_backend().check(jti)


async def ais_token_blacklisted(jti: str) -> bool:
    """Check if a token is blacklisted (async)."""
    return await _get_backend().acheck(jti)


def prune_expired_tokens() -> int:
    """Remove expired blacklist entries (sync). Returns count removed."""
    return _get_backend().prune()


async def aprune_expired_tokens() -> int:
    """Remove expired blacklist entries (async). Returns count removed."""
    return await _get_backend().aprune()


def _user_revocation_key(user_id: int | str) -> str:
    """Return the cache key for a per-user revocation sentinel."""
    from .config import blacklist_config

    return f"{blacklist_config.cache_prefix}user_revoked:{user_id}"


def bulk_revoke_tokens_for_user(user_id: int | str) -> None:
    """Revoke all tokens for a user (sync).

    Stores a per-user sentinel in cache with TTL = refresh_token_lifetime.
    Any access token with iat < sentinel timestamp is rejected.
    No-op when blacklist backend is 'null'.
    """
    from .config import blacklist_config

    if not blacklist_config.enabled:
        return

    from django.core.cache import cache

    from django_matt.auth.jwt import jwt_config

    ttl = int(jwt_config.refresh_token_lifetime.total_seconds())
    key = _user_revocation_key(user_id)
    cache.set(key, time.time(), timeout=ttl)


async def abulk_revoke_tokens_for_user(user_id: int | str) -> None:
    """Revoke all tokens for a user (async).

    Stores a per-user sentinel in cache with TTL = refresh_token_lifetime.
    Any access token with iat < sentinel timestamp is rejected.
    No-op when blacklist backend is 'null'.
    """
    from asgiref.sync import sync_to_async

    await sync_to_async(bulk_revoke_tokens_for_user)(user_id)


def is_user_tokens_revoked(user_id: int | str, iat: float) -> bool:
    """Check if a user's tokens have been bulk-revoked (sync).

    Returns True if iat < sentinel timestamp (token was issued before revocation).
    Returns False if no sentinel exists or backend is 'null'.
    """
    from .config import blacklist_config

    if not blacklist_config.enabled:
        return False

    from django.core.cache import cache

    key = _user_revocation_key(user_id)
    sentinel_ts = cache.get(key)
    if sentinel_ts is None:
        return False
    return iat < sentinel_ts


async def ais_user_tokens_revoked(user_id: int | str, iat: float) -> bool:
    """Check if a user's tokens have been bulk-revoked (async).

    Returns True if iat < sentinel timestamp (token was issued before revocation).
    Returns False if no sentinel exists or backend is 'null'.
    """
    from asgiref.sync import sync_to_async

    return await sync_to_async(is_user_tokens_revoked)(user_id, iat)

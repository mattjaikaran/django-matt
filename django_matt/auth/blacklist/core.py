"""Public API for token blacklisting."""

from __future__ import annotations

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

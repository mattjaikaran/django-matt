"""
Centralized settings accessors for django_matt internals.

Single source of truth for reading DJANGO_MATT settings keys.
Prevents duplicate cache globals scattered across controller.py, router.py, etc.
"""

from __future__ import annotations

from typing import Any

_cache: dict[str, Any] = {}


def get_matt_setting(key: str, default: Any = None) -> Any:
    """Read a value from settings.DJANGO_MATT[key], cached after first access."""
    if key not in _cache:
        from django.conf import settings

        matt_config = getattr(settings, "DJANGO_MATT", {})
        _cache[key] = matt_config.get(key, default)
    return _cache[key]


def get_error_config() -> dict[str, Any]:
    """Get error handling configuration from settings (cached)."""
    if "_error_config" not in _cache:
        from django.conf import settings

        config = getattr(settings, "DJANGO_MATT_ERRORS", {})
        _cache["_error_config"] = {
            "debug": config.get("DEBUG", getattr(settings, "DEBUG", False)),
            "include_traceback": config.get("INCLUDE_TRACEBACK", getattr(settings, "DEBUG", False)),
            "include_snippet": config.get("INCLUDE_SNIPPET", getattr(settings, "DEBUG", False)),
        }
    return _cache["_error_config"]


def reset_cache() -> None:
    """Reset all cached settings. Used in tests."""
    _cache.clear()


__all__ = [
    "get_error_config",
    "get_matt_setting",
    "get_pool_warmup",
    "reset_cache",
]


def get_pool_warmup() -> int:
    """Get configured connection pool pre-warming size (0 = disabled).

    Reads ``MATT_DB_POOL_WARMUP`` from the ``DJANGO_MATT`` settings dict
    or as a module-level Django setting.  Defaults to 0 (disabled).
    """
    n = get_matt_setting("MATT_DB_POOL_WARMUP", 0)
    try:
        return max(0, int(n))
    except (TypeError, ValueError):
        return 0

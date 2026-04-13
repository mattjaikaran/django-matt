"""
Default rate limiting presets for django-matt.

Provides zero-config rate limiting that works out of the box.

Usage:
    # In settings.py
    MATT_THROTTLE = "standard"  # or "strict" or "relaxed" or a dict

    # In MIDDLEWARE
    MIDDLEWARE = [
        ...
        "django_matt.throttling.middleware.ThrottleMiddleware",
        ...
    ]
"""

from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "standard": {
        "anon_rate": "100/minute",
        "user_rate": "1000/minute",
        "login_rate": "10/minute",
        "register_rate": "5/minute",
        "password_reset_rate": "5/minute",
        "exclude_paths": ["/health/", "/ready/", "/api/docs/", "/api/redoc/"],
        "exclude_methods": ["OPTIONS"],
        "burst_multiplier": 2.0,
        "backend": "memory",
    },
    "strict": {
        "anon_rate": "30/minute",
        "user_rate": "300/minute",
        "login_rate": "5/minute",
        "register_rate": "3/minute",
        "password_reset_rate": "3/minute",
        "exclude_paths": ["/health/", "/ready/"],
        "exclude_methods": ["OPTIONS"],
        "burst_multiplier": 1.0,
        "backend": "memory",
    },
    "relaxed": {
        "anon_rate": "500/minute",
        "user_rate": "5000/minute",
        "login_rate": "30/minute",
        "register_rate": "20/minute",
        "password_reset_rate": "10/minute",
        "exclude_paths": ["/health/", "/ready/", "/api/docs/", "/api/redoc/"],
        "exclude_methods": ["OPTIONS"],
        "burst_multiplier": 3.0,
        "backend": "memory",
    },
    "api": {
        "anon_rate": "60/minute",
        "user_rate": "600/minute",
        "login_rate": "10/minute",
        "register_rate": "5/minute",
        "password_reset_rate": "5/minute",
        "exclude_paths": ["/health/", "/ready/"],
        "exclude_methods": ["OPTIONS"],
        "burst_multiplier": 1.5,
        "backend": "memory",
    },
}

# Scope-to-path patterns for auto-applying scoped rates
SCOPE_PATTERNS: dict[str, list[str]] = {
    "login": ["/auth/login", "/auth/token", "/login"],
    "register": ["/auth/register", "/auth/signup", "/register"],
    "password_reset": ["/auth/password-reset", "/auth/forgot-password", "/password-reset"],
}


def resolve_throttle_config(setting: str | dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Resolve throttle configuration from a preset name or custom dict.

    Args:
        setting: Preset name ("standard", "strict", "relaxed", "api"),
                 a custom config dict, or None for no defaults.

    Returns:
        Resolved configuration dict.

    Raises:
        ValueError: If preset name is unknown.
    """
    if setting is None:
        return {}

    if isinstance(setting, dict):
        # Merge with standard defaults for any missing keys
        base = PRESETS["standard"].copy()
        base.update(setting)
        return base

    if isinstance(setting, str):
        if setting not in PRESETS:
            valid = ", ".join(sorted(PRESETS.keys()))
            raise ValueError(
                f"Unknown throttle preset '{setting}'. Valid presets: {valid}"
            )
        return PRESETS[setting].copy()

    raise TypeError(f"MATT_THROTTLE must be a str or dict, got {type(setting).__name__}")


def get_throttle_defaults() -> dict[str, Any]:
    """
    Read MATT_THROTTLE from Django settings and resolve to a config dict.

    Returns:
        Resolved throttle configuration. Empty dict if not configured.
    """
    try:
        from django.conf import settings

        raw = getattr(settings, "MATT_THROTTLE", None)
    except Exception:
        return {}

    return resolve_throttle_config(raw)


def get_rate_for_scope(scope: str) -> str | None:
    """
    Get the rate limit for a named scope from the resolved config.

    Args:
        scope: Scope name (e.g., "anon", "user", "login", "register")

    Returns:
        Rate string (e.g., "100/minute") or None if not configured.
    """
    config = get_throttle_defaults()
    rate_key = f"{scope}_rate"
    return config.get(rate_key)


def get_scope_for_path(path: str) -> str | None:
    """
    Auto-detect rate limit scope based on URL path.

    Args:
        path: Request path

    Returns:
        Scope name if path matches a known pattern, None otherwise.
    """
    path_lower = path.rstrip("/").lower()
    for scope, patterns in SCOPE_PATTERNS.items():
        for pattern in patterns:
            if path_lower.endswith(pattern.rstrip("/")):
                return scope
    return None

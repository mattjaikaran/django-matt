"""Validators for configuration values such as durations, sizes, and URLs."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(ms|s|m|h|d|w)$", re.IGNORECASE)
_SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(b|kb|mb|gb|tb)$", re.IGNORECASE)

_DURATION_MULTIPLIERS: dict[str, float] = {
    "ms": 0.001,
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}

_SIZE_MULTIPLIERS: dict[str, int] = {
    "b": 1,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    "tb": 1024**4,
}


def validate_url(v: Any) -> str:
    """Validate that a value is an HTTP or HTTPS URL string."""
    if not isinstance(v, str):
        raise ValueError(f"expected string, got {type(v).__name__}")
    if not re.match(r"^https?://\S+$", v):
        raise ValueError(f"invalid URL: {v!r}")
    return v


def validate_duration(v: Any) -> timedelta:
    """Parse a duration value (timedelta, number of seconds, or string like '30s', '5m') into a timedelta."""
    if isinstance(v, timedelta):
        return v
    if isinstance(v, (int, float)):
        return timedelta(seconds=v)
    if not isinstance(v, str):
        raise ValueError(f"expected string or number, got {type(v).__name__}")
    match = _DURATION_RE.match(v.strip())
    if not match:
        raise ValueError(
            f"invalid duration: {v!r} — use format like '30s', '5m', '1h', '7d'"
        )
    value = float(match.group(1))
    unit = match.group(2).lower()
    return timedelta(seconds=value * _DURATION_MULTIPLIERS[unit])


def validate_size(v: Any) -> int:
    """Parse a size value (int bytes or string like '10MB', '1GB') into bytes."""
    if isinstance(v, int):
        return v
    if not isinstance(v, str):
        raise ValueError(f"expected string or int, got {type(v).__name__}")
    match = _SIZE_RE.match(v.strip())
    if not match:
        raise ValueError(
            f"invalid size: {v!r} — use format like '10MB', '1GB', '512KB'"
        )
    value = float(match.group(1))
    unit = match.group(2).lower()
    return int(value * _SIZE_MULTIPLIERS[unit])

"""
Unpoly configuration.

Provides configuration management for the Unpoly middleware and utilities.
"""

from __future__ import annotations

from django.conf import settings

from pydantic import BaseModel


class UnpolyConfig(BaseModel):
    """Configuration for Unpoly integration."""

    enabled: bool = True
    safe_methods: list[str] = ["GET", "HEAD", "OPTIONS"]
    version: str | None = None

    model_config = {"frozen": True}


_config: UnpolyConfig | None = None


def get_unpoly_config() -> UnpolyConfig:
    """Get Unpoly configuration from Django settings."""
    global _config
    if _config is not None:
        return _config

    raw = getattr(settings, "UNPOLY", {})
    _config = UnpolyConfig(**raw)
    return _config


__all__ = [
    "UnpolyConfig",
    "get_unpoly_config",
]

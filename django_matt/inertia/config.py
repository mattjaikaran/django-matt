"""
Inertia.js configuration.

Provides configuration model and accessor for Inertia settings.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class InertiaConfig(BaseModel):
    """Configuration for the Inertia.js adapter."""

    root_template: str = Field(
        default="base.html",
        description="Template containing the {% inertia %} tag",
    )
    version: str | Callable[[], str] | None = Field(
        default=None,
        description="Asset version for cache busting (string or callable)",
    )
    ssr_enabled: bool = Field(
        default=False,
        description="Enable server-side rendering via Node.js",
    )
    ssr_url: str = Field(
        default="http://localhost:13714",
        description="URL of the Inertia SSR server",
    )
    json_encoder: str = Field(
        default="orjson",
        description="JSON encoder to use (orjson or json)",
    )

    model_config = {"arbitrary_types_allowed": True}


_config: InertiaConfig | None = None


def get_inertia_config() -> InertiaConfig:
    """Get the Inertia configuration from Django settings.

    Reads ``INERTIA`` dict from ``django.conf.settings`` and returns a
    validated :class:`InertiaConfig` instance.  The result is cached for
    the lifetime of the process.
    """
    global _config
    if _config is not None:
        return _config

    from django.conf import settings

    raw: dict[str, Any] = getattr(settings, "INERTIA", {})
    _config = InertiaConfig(**raw)
    return _config


def _reset_config() -> None:
    """Reset cached config (for testing)."""
    global _config
    _config = None


__all__ = [
    "InertiaConfig",
    "get_inertia_config",
]

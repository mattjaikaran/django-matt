"""Startup-time configuration validation and namespace registration."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from django_matt.config.namespaces import ConfigNamespace

logger = logging.getLogger("django_matt.config")

_registry: dict[str, type[ConfigNamespace]] = {}
_skipped: set[str] = set()


def register_namespace(key: str, cls: type[ConfigNamespace]) -> None:
    """Register a ConfigNamespace subclass for startup validation."""
    if not issubclass(cls, ConfigNamespace):
        raise TypeError(f"{cls!r} must be a ConfigNamespace subclass")
    _registry[key] = cls


def skip_validation(key: str) -> None:
    """Exclude a namespace key from startup validation."""
    _skipped.add(key)


def validate_config() -> dict[str, ConfigNamespace]:
    """Validate all registered namespaces against current Django settings."""
    from django.conf import settings

    matt_settings: dict[str, Any] = getattr(settings, "DJANGO_MATT", {})
    results: dict[str, ConfigNamespace] = {}
    errors: list[str] = []

    for key, cls in _registry.items():
        if key in _skipped:
            continue
        section = matt_settings.get(key, {})
        try:
            instance = cls.model_validate(section)
            results[key] = instance
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"])
                field_path = f"DJANGO_MATT.{key}.{loc}" if loc else f"DJANGO_MATT.{key}"
                errors.append(f"  {field_path}: {err['msg']}")

    if errors:
        detail = "\n".join(errors)
        raise ValueError(
            f"django-matt configuration errors:\n{detail}"
        )

    return results


def reset_startup() -> None:
    """Clear all registered namespaces and skip flags (for testing)."""
    _registry.clear()
    _skipped.clear()

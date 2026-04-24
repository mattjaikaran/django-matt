"""Pydantic field constructors for group-based serialization visibility."""

from __future__ import annotations

from typing import Any

from pydantic import Field


def Grouped(*groups: str, **field_kwargs: Any) -> Any:
    """Create a Pydantic field visible only to the specified serialization groups."""
    json_schema_extra = field_kwargs.pop("json_schema_extra", {}) or {}
    json_schema_extra["groups"] = list(groups)
    return Field(json_schema_extra=json_schema_extra, **field_kwargs)


def Secret(**field_kwargs: Any) -> Any:
    """Create a field visible only to admin and internal groups."""
    return Grouped("admin", "internal", **field_kwargs)


def Public(**field_kwargs: Any) -> Any:
    """Create a field visible to all groups (no group restriction)."""
    return Field(**field_kwargs)

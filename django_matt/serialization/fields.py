from __future__ import annotations

from typing import Any

from pydantic import Field


def Grouped(*groups: str, **field_kwargs: Any) -> Any:
    json_schema_extra = field_kwargs.pop("json_schema_extra", {}) or {}
    json_schema_extra["groups"] = list(groups)
    return Field(json_schema_extra=json_schema_extra, **field_kwargs)


def Secret(**field_kwargs: Any) -> Any:
    return Grouped("admin", "internal", **field_kwargs)


def Public(**field_kwargs: Any) -> Any:
    return Field(**field_kwargs)

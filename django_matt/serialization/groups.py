from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, create_model


@dataclass(frozen=True, slots=True)
class SerializationContext:
    groups: frozenset[str] = field(default_factory=frozenset)
    include_fields: frozenset[str] | None = None
    exclude_fields: frozenset[str] | None = None

    @classmethod
    def from_groups(cls, *groups: str) -> SerializationContext:
        return cls(groups=frozenset(groups))


def _get_field_groups(model_class: type[BaseModel], field_name: str) -> list[str] | None:
    field_info = model_class.model_fields.get(field_name)
    if field_info is None:
        return None
    extra = field_info.json_schema_extra
    if isinstance(extra, dict):
        return extra.get("groups")
    return None


def _is_field_visible(
    model_class: type[BaseModel],
    field_name: str,
    context: SerializationContext,
) -> bool:
    if context.exclude_fields and field_name in context.exclude_fields:
        return False
    if context.include_fields is not None:
        return field_name in context.include_fields

    groups = _get_field_groups(model_class, field_name)
    if not groups:
        return True
    return bool(context.groups & frozenset(groups))


def filter_schema(instance: BaseModel, context: SerializationContext) -> dict[str, Any]:
    model_class = type(instance)
    return {
        name: getattr(instance, name)
        for name in model_class.model_fields
        if _is_field_visible(model_class, name, context)
    }


_schema_cache: dict[tuple[type[BaseModel], frozenset[str]], type[BaseModel]] = {}


def schema_for_groups(
    base_schema: type[BaseModel],
    *groups: str,
) -> type[BaseModel]:
    group_set = frozenset(groups)
    cache_key = (base_schema, group_set)
    if cache_key in _schema_cache:
        return _schema_cache[cache_key]

    visible_fields: dict[str, Any] = {}
    context = SerializationContext(groups=group_set)
    for name, field_info in base_schema.model_fields.items():
        if _is_field_visible(base_schema, name, context):
            visible_fields[name] = (field_info.annotation, field_info)

    dynamic = create_model(
        f"{base_schema.__name__}_{'-'.join(sorted(groups))}",
        __base__=BaseModel,
        **visible_fields,
    )
    _schema_cache[cache_key] = dynamic
    return dynamic


def clear_schema_cache() -> None:
    _schema_cache.clear()

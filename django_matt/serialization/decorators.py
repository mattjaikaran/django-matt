"""@serialize_for decorator for group-based response filtering on views."""

from __future__ import annotations

import functools
from typing import Any, Callable

from pydantic import BaseModel

from django_matt.serialization.groups import SerializationContext, filter_schema


def _resolve_groups_from_request(request: Any, path: str) -> list[str]:
    parts = path.split(".")
    obj = request
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            return []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, (list, tuple, set, frozenset)):
        return list(obj)
    return [str(obj)]


def _filter_response(data: Any, context: SerializationContext) -> Any:
    if isinstance(data, BaseModel):
        return filter_schema(data, context)
    if isinstance(data, list):
        return [_filter_response(item, context) for item in data]
    if isinstance(data, dict):
        return data
    return data


def serialize_for(
    groups: list[str] | None = None,
    groups_from: str | None = None,
    include_fields: set[str] | None = None,
    exclude_fields: set[str] | None = None,
) -> Callable:
    """Decorator that filters the view's response through group-based serialization."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            ctx = _build_context(args, kwargs, groups, groups_from, include_fields, exclude_fields)
            return _filter_response(result, ctx)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            ctx = _build_context(args, kwargs, groups, groups_from, include_fields, exclude_fields)
            return _filter_response(result, ctx)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _build_context(
    args: tuple,
    kwargs: dict,
    groups: list[str] | None,
    groups_from: str | None,
    include_fields: set[str] | None,
    exclude_fields: set[str] | None,
) -> SerializationContext:
    resolved_groups: list[str] = list(groups) if groups else []

    if groups_from:
        request = kwargs.get("request") or (args[0] if args else None)
        if hasattr(request, "META"):
            resolved_groups.extend(_resolve_groups_from_request(request, groups_from))
        elif len(args) > 1 and hasattr(args[1], "META"):
            resolved_groups.extend(_resolve_groups_from_request(args[1], groups_from))

    return SerializationContext(
        groups=frozenset(resolved_groups),
        include_fields=frozenset(include_fields) if include_fields else None,
        exclude_fields=frozenset(exclude_fields) if exclude_fields else None,
    )

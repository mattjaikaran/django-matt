from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from .commands import Command, CommandBus, get_command_bus
from .queries import Query, QueryBus, get_query_bus


def command(
    command_type: type[Command],
    *,
    bus: CommandBus | None = None,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: Any, request: Any, data: Any = None, **kwargs: Any) -> Any:
            target_bus = bus or get_command_bus()
            if data is not None:
                if hasattr(data, "model_dump"):
                    cmd = command_type(**data.model_dump())
                else:
                    cmd = command_type(**data) if isinstance(data, dict) else data
            else:
                import orjson

                body = request.body
                if isinstance(body, memoryview):
                    body = bytes(body)
                payload = orjson.loads(body) if body else {}
                cmd = command_type(**payload)

            return await target_bus.dispatch(cmd)

        wrapper._cqrs_command_type = command_type
        return wrapper

    return decorator


def query(
    query_type: type[Query],
    *,
    bus: QueryBus | None = None,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: Any, request: Any, **kwargs: Any) -> Any:
            target_bus = bus or get_query_bus()
            params = dict(request.GET.items()) if hasattr(request, "GET") else {}
            params.update(kwargs)
            q = query_type(**params)
            return await target_bus.dispatch(q)

        wrapper._cqrs_query_type = query_type
        return wrapper

    return decorator

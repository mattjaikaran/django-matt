from __future__ import annotations

import functools
from typing import Any, Callable

from django_matt.streaming.response import stream_response
from django_matt.streaming.sse import sse_response


def sse_endpoint(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        generator = fn(*args, **kwargs)
        return sse_response(generator)

    wrapper._is_sse_endpoint = True  # type: ignore[attr-defined]
    return wrapper


def streaming(
    content_type: str = "application/octet-stream",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            generator = fn(*args, **kwargs)
            return stream_response(generator, content_type=content_type)

        wrapper._is_streaming_endpoint = True  # type: ignore[attr-defined]
        return wrapper

    return decorator

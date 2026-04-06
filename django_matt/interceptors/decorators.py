from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django_matt.interceptors.base import Interceptor
from django_matt.interceptors.chain import InterceptorChain


def intercept(*interceptors: Interceptor) -> Callable:
    """Apply interceptors to a single view/method."""

    def decorator(fn: Callable) -> Callable:
        chain = InterceptorChain(list(interceptors))

        @wraps(fn)
        async def wrapper(request: Any, *args: Any, **kwargs: Any) -> Any:
            return await chain.execute(request, fn, *args, **kwargs)

        wrapper._interceptors = chain  # type: ignore[attr-defined]
        return wrapper

    return decorator


def intercept_controller(
    *interceptors: Interceptor,
) -> Callable[[type], type]:
    """Class decorator: attach interceptors to a controller."""

    def decorator(cls: type) -> type:
        existing: list[Interceptor] = list(getattr(cls, "interceptors", []))
        cls.interceptors = existing + list(interceptors)  # type: ignore[attr-defined]
        return cls

    return decorator

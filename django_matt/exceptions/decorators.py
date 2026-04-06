from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse

from django_matt.exceptions.filters import ExceptionFilter, FunctionExceptionFilter
from django_matt.exceptions.registry import default_registry


def exception_filter(
    *exception_types: type[Exception],
    order: int = 0,
) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        if not hasattr(cls, "catch"):
            raise TypeError(f"{cls.__name__} must define an async 'catch' method")
        cls.exception_types = exception_types or cls.__dict__.get("exception_types", ())
        cls.order = order
        return cls

    return decorator


def catch(
    *exception_types: type[Exception],
    handler: Callable[..., HttpResponse] | None = None,
    order: int = 0,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        if handler is not None:
            filter_ = FunctionExceptionFilter(
                exception_types=exception_types or (Exception,),
                handler=handler,
                order=order,
            )
            if not hasattr(func, "_exception_filters"):
                func._exception_filters = []
            func._exception_filters.append(filter_)
            return func

        # no handler provided — wrap the function to catch inline
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            except exception_types as exc:
                raise
            except Exception:
                raise

        wrapper._exception_filters = getattr(func, "_exception_filters", [])
        return wrapper

    return decorator


def catch_all(
    handler: Callable[..., HttpResponse],
    order: int = 0,
) -> Callable:
    return catch(Exception, handler=handler, order=order)


def register_global_filter(filter_: ExceptionFilter) -> ExceptionFilter:
    default_registry.register_global_filter(filter_)
    return filter_

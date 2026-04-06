from __future__ import annotations

import functools
import logging
from typing import Any, TypeVar

from django_matt.modules.base import MattModule

logger = logging.getLogger("django_matt.modules")

F = TypeVar("F")


def module(
    name: str,
    version: str = "0.1.0",
    depends: list[str] | None = None,
    config_namespace: str | None = None,
) -> Any:
    def decorator(cls: type) -> type[MattModule]:
        if not issubclass(cls, MattModule):
            bases = (cls, MattModule)
            cls = type(cls.__name__, bases, dict(cls.__dict__))

        cls.name = name
        cls.version = version
        cls.dependencies = depends or []
        if config_namespace is not None:
            cls.config_namespace = config_namespace
        return cls

    return decorator


def requires_module(module_name: str) -> Any:
    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from django_matt.modules.registry import get_registry

            registry = get_registry()
            if not registry.is_loaded(module_name):
                raise RuntimeError(
                    f"Module {module_name!r} is required but not loaded. "
                    f"Add it to your DJANGO_MATT['MODULES'] or install the package."
                )
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            from django_matt.modules.registry import get_registry

            registry = get_registry()
            if not registry.is_loaded(module_name):
                raise RuntimeError(
                    f"Module {module_name!r} is required but not loaded. "
                    f"Add it to your DJANGO_MATT['MODULES'] or install the package."
                )
            return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


def optional_module(module_name: str, default: Any = None) -> Any:
    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from django_matt.modules.registry import get_registry

            registry = get_registry()
            if not registry.is_loaded(module_name):
                logger.debug(
                    "Optional module %s not loaded, returning default", module_name
                )
                return default
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            from django_matt.modules.registry import get_registry

            registry = get_registry()
            if not registry.is_loaded(module_name):
                logger.debug(
                    "Optional module %s not loaded, returning default", module_name
                )
                return default
            return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator

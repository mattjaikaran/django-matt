"""Lifecycle hook decorators for module load events."""

from __future__ import annotations

import functools
from typing import Any


def on_module_loaded(module_name: str) -> Any:
    """Register a callback to run after a specific module finishes loading."""

    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._matt_hook_type = "on_module_loaded"
        wrapper._matt_hook_target = module_name

        from django_matt.modules.registry import get_registry

        registry = get_registry()
        registry.add_on_loaded_hook(module_name, func)

        return wrapper

    return decorator


def on_all_loaded(func: Any) -> Any:
    """Register a callback to run after all modules have been loaded."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    wrapper._matt_hook_type = "on_all_loaded"

    from django_matt.modules.registry import get_registry

    registry = get_registry()
    registry.add_all_loaded_hook(func)

    return wrapper


def before_module_load(module_name: str) -> Any:
    """Register a callback to run before a specific module starts loading."""

    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._matt_hook_type = "before_module_load"
        wrapper._matt_hook_target = module_name

        from django_matt.modules.registry import get_registry

        registry = get_registry()
        registry.add_before_load_hook(module_name, func)

        return wrapper

    return decorator

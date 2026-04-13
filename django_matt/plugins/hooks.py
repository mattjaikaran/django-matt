from __future__ import annotations

import functools
import inspect
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger("django_matt.plugins")

# Global hook registry
_hooks: dict[str, list[tuple[int, Any]]] = defaultdict(list)


def hook(event: str, *, priority: int = 100) -> Any:
    """Register a function as a hook handler for a given event.

    Args:
        event: Hook event name (e.g. "before_request", "after_response").
        priority: Lower numbers execute first. Default 100.
    """

    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._matt_hook_event = event
        wrapper._matt_hook_priority = priority
        wrapper._matt_hook_func = func
        _hooks[event].append((priority, func))
        _hooks[event].sort(key=lambda x: x[0])
        return wrapper

    return decorator


def get_hooks(event: str) -> list[Any]:
    """Return all registered hook functions for an event, sorted by priority."""
    return [func for _, func in _hooks.get(event, [])]


async def fire_hook(event: str, **kwargs: Any) -> list[Any]:
    """Fire a hook event and collect all results.

    Supports both sync and async hook handlers.
    """
    results: list[Any] = []
    for func in get_hooks(event):
        if inspect.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = func(**kwargs)
        results.append(result)
    return results


def fire_hook_sync(event: str, **kwargs: Any) -> list[Any]:
    """Fire a hook event synchronously. Async hooks are skipped with a warning."""
    results: list[Any] = []
    for func in get_hooks(event):
        if inspect.iscoroutinefunction(func):
            logger.warning(
                "Skipping async hook %s for event %s in sync context",
                func.__name__,
                event,
            )
            continue
        result = func(**kwargs)
        results.append(result)
    return results


def clear_hooks(event: str | None = None) -> None:
    """Clear hooks for a specific event, or all hooks if event is None."""
    if event is None:
        _hooks.clear()
    else:
        _hooks.pop(event, None)


def list_hook_events() -> list[str]:
    """Return all registered hook event names."""
    return sorted(_hooks.keys())


# Standard hook event names
BEFORE_REQUEST = "before_request"
AFTER_RESPONSE = "after_response"
ON_ERROR = "on_error"
MODEL_REGISTERED = "model_registered"
CONTROLLER_REGISTERED = "controller_registered"
SCHEMA_VALIDATED = "schema_validated"
AUTH_SUCCESS = "auth_success"
AUTH_FAILURE = "auth_failure"
PLUGIN_LOADED = "plugin_loaded"
PLUGIN_UNLOADED = "plugin_unloaded"

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from fnmatch import fnmatch
from typing import Any

logger = logging.getLogger("django_matt.plugins.stripe")

# Handler registry: event_type_pattern -> list of async callables
_handlers: dict[str, list[Callable[..., Coroutine[Any, Any, None]]]] = (
    defaultdict(list)
)


def on_stripe_event(
    event_type: str,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, None]]],
    Callable[..., Coroutine[Any, Any, None]],
]:
    """Register an async handler for a Stripe webhook event type.

    Supports exact matches ("checkout.session.completed") and
    wildcard patterns ("customer.*").

    Args:
        event_type: Stripe event type string or glob pattern.
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, None]],
    ) -> Callable[..., Coroutine[Any, Any, None]]:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(
                f"Stripe event handler {func.__name__} must be async"
            )
        _handlers[event_type].append(func)
        func._stripe_event_type = event_type  # type: ignore[attr-defined]
        return func

    return decorator


def get_handlers_for(event_type: str) -> list[Callable[..., Coroutine[Any, Any, None]]]:
    """Return all handlers matching the given event type."""
    matched: list[Callable[..., Coroutine[Any, Any, None]]] = []
    for pattern, handlers in _handlers.items():
        if pattern == event_type or fnmatch(event_type, pattern):
            matched.extend(handlers)
    return matched


async def dispatch_event(event_type: str, event_data: dict[str, Any]) -> int:
    """Dispatch a Stripe event to all matching handlers.

    Returns the number of handlers invoked.
    """
    handlers = get_handlers_for(event_type)
    if not handlers:
        logger.debug("No handlers registered for Stripe event: %s", event_type)
        return 0

    errors: list[Exception] = []
    for handler in handlers:
        try:
            await handler(event_data)
        except Exception as exc:
            logger.error(
                "Stripe handler %s failed for %s: %s",
                handler.__name__,
                event_type,
                exc,
            )
            errors.append(exc)

    if errors:
        logger.warning(
            "%d/%d handlers failed for %s",
            len(errors),
            len(handlers),
            event_type,
        )

    return len(handlers)


def clear_handlers() -> None:
    """Clear all registered handlers. Useful for testing."""
    _handlers.clear()


def list_registered_events() -> list[str]:
    """Return all registered event type patterns."""
    return sorted(_handlers.keys())

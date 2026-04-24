"""Decorator-based event subscription and autodiscovery for app event modules."""

from __future__ import annotations

import importlib
import logging
from typing import Callable

from django_matt.events.bus import Event, get_event_bus

logger = logging.getLogger("django_matt.events")

_pending_subscriptions: list[tuple[str, Callable]] = []


def on(event_type: str | type[Event]) -> Callable:
    """Subscribe the decorated function to the given event type."""
    def decorator(func: Callable) -> Callable:
        if isinstance(event_type, str):
            key = event_type
        else:
            key = getattr(event_type, "__event_type__", event_type.__name__)

        _pending_subscriptions.append((key, func))

        bus = get_event_bus()
        bus.subscribe(key, func)

        func._event_subscription = key
        return func

    return decorator


def autodiscover(app_labels: list[str] | None = None) -> int:
    """Import `events` modules from installed apps to register @on handlers."""
    from django.apps import apps

    count = 0
    labels = app_labels or [cfg.label for cfg in apps.get_app_configs()]
    for label in labels:
        cfg = apps.get_app_config(label)
        module_name = f"{cfg.name}.events"
        try:
            importlib.import_module(module_name)
            count += 1
        except ImportError:
            pass
    return count

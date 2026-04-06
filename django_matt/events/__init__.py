from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def __getattr__(name: str):
    if name == "Event":
        from django_matt.events.bus import Event

        return Event
    if name == "EventBus":
        from django_matt.events.bus import EventBus

        return EventBus
    if name == "get_event_bus":
        from django_matt.events.bus import get_event_bus

        return get_event_bus
    if name == "reset_event_bus":
        from django_matt.events.bus import reset_event_bus

        return reset_event_bus
    if name == "BackendProtocol":
        from django_matt.events.bus import BackendProtocol

        return BackendProtocol
    if name == "on":
        from django_matt.events.decorators import on

        return on
    if name == "autodiscover":
        from django_matt.events.decorators import autodiscover

        return autodiscover
    if name == "EventMiddleware":
        from django_matt.events.middleware import EventMiddleware

        return EventMiddleware
    if name == "collect_event":
        from django_matt.events.middleware import collect_event

        return collect_event
    if name == "InMemoryBackend":
        from django_matt.events.backends import InMemoryBackend

        return InMemoryBackend
    if name == "RedisBackend":
        from django_matt.events.backends import RedisBackend

        return RedisBackend
    if name in (
        "UserCreatedEvent",
        "UserUpdatedEvent",
        "UserDeletedEvent",
        "ModelCreatedEvent",
        "ModelUpdatedEvent",
        "ModelDeletedEvent",
        "RequestEvent",
    ):
        import django_matt.events.types as types_mod

        return getattr(types_mod, name)

    raise AttributeError(f"module 'django_matt.events' has no attribute {name!r}")


__all__ = [
    "Event",
    "EventBus",
    "get_event_bus",
    "reset_event_bus",
    "BackendProtocol",
    "on",
    "autodiscover",
    "EventMiddleware",
    "collect_event",
    "InMemoryBackend",
    "RedisBackend",
    "UserCreatedEvent",
    "UserUpdatedEvent",
    "UserDeletedEvent",
    "ModelCreatedEvent",
    "ModelUpdatedEvent",
    "ModelDeletedEvent",
    "RequestEvent",
]

"""Core event bus, Event base model, and backend protocol definition."""

from __future__ import annotations

import asyncio
import logging
import time
from fnmatch import fnmatch
from typing import Any, Callable

import orjson
from pydantic import BaseModel, Field

logger = logging.getLogger("django_matt.events")


class Event(BaseModel):
    """Base event model with automatic type detection and serialization."""

    event_type: str = ""
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.event_type:
            cls = type(self)
            self.event_type = getattr(cls, "__event_type__", cls.__name__)

    def serialize(self) -> bytes:
        """Serialize this event to JSON bytes."""
        return orjson.dumps(self.model_dump())

    @classmethod
    def deserialize(cls, data: bytes) -> Event:
        """Deserialize JSON bytes into an Event instance."""
        return cls.model_validate(orjson.loads(data))


class EventBus:
    """Central event bus that dispatches events to subscribed handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}
        self._backend: BackendProtocol | None = None

    @property
    def backend(self) -> BackendProtocol | None:
        return self._backend

    @backend.setter
    def backend(self, value: BackendProtocol) -> None:
        self._backend = value

    def subscribe(self, event_type: str | type[Event], handler: Callable) -> None:
        """Register a handler for the given event type or pattern."""
        key = self._resolve_key(event_type)
        if key not in self._handlers:
            self._handlers[key] = []
        if handler not in self._handlers[key]:
            self._handlers[key].append(handler)

    def unsubscribe(self, event_type: str | type[Event], handler: Callable) -> None:
        """Remove a previously registered handler."""
        key = self._resolve_key(event_type)
        if key in self._handlers:
            try:
                self._handlers[key].remove(handler)
            except ValueError:
                pass

    async def emit(self, event: Event) -> list[Exception | None]:
        """Emit an event to all matching handlers, returning any exceptions."""
        handlers = self._collect_handlers(event.event_type)
        if not handlers:
            return []

        results: list[Exception | None] = []
        tasks = [self._safe_call(h, event) for h in handlers]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                logger.error(f"Event handler failed for {event.event_type}: {outcome}")
                results.append(outcome)
            else:
                results.append(outcome)
        return results

    async def emit_many(self, events: list[Event]) -> list[list[Exception | None]]:
        """Emit multiple events sequentially."""
        return [await self.emit(e) for e in events]

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()

    def handlers_for(self, event_type: str | type[Event]) -> list[Callable]:
        """Return a copy of handlers registered for the given event type."""
        key = self._resolve_key(event_type)
        return list(self._handlers.get(key, []))

    def _collect_handlers(self, event_type: str) -> list[Callable]:
        matched: list[Callable] = []
        for pattern, handlers in self._handlers.items():
            if pattern == event_type or fnmatch(event_type, pattern):
                matched.extend(handlers)
        return matched

    @staticmethod
    async def _safe_call(handler: Callable, event: Event) -> None:
        if asyncio.iscoroutinefunction(handler):
            await handler(event)
        else:
            handler(event)

    @staticmethod
    def _resolve_key(event_type: str | type[Event]) -> str:
        if isinstance(event_type, str):
            return event_type
        return getattr(event_type, "__event_type__", event_type.__name__)


class BackendProtocol:
    """Protocol defining the interface for event bus backends."""

    async def publish(self, event: Event) -> None:
        raise NotImplementedError

    async def subscribe(self, pattern: str, handler: Callable) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        pass


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the global EventBus singleton, creating it if necessary."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    """Reset the global EventBus singleton (useful in tests)."""
    global _bus
    _bus = None

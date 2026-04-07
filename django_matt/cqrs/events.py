from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: float = Field(default_factory=time.time)


def emits(*event_types: type[DomainEvent]) -> Callable:
    def decorator(cls: type) -> type:
        cls._emitted_events = tuple(event_types)
        return cls

    return decorator


class EventCollector:
    def __init__(self) -> None:
        self._events: list[DomainEvent] = []
        self._handlers: dict[type[DomainEvent], list[Callable]] = {}

    def collect(self, event: DomainEvent) -> None:
        self._events.append(event)

    def on(self, event_type: type[DomainEvent], handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self) -> None:
        for event in self._events:
            handlers = self._handlers.get(type(event), [])
            for handler in handlers:
                await handler(event)
        self._events.clear()

    @property
    def events(self) -> list[DomainEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()

"""
GraphQL subscriptions for Django Matt.

Provides WebSocket subscription support for real-time updates.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Generic, TypeVar

from django.db import models
from django.db.models.signals import post_delete, post_save

try:
    import strawberry
    from strawberry.types import Info

    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    Info = Any


T = TypeVar("T")


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for GraphQL subscriptions. "
            "Install it with: uv add \"strawberry-graphql[django]\""
        )


class SubscriptionEvent(str, Enum):
    """Types of subscription events."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


@dataclass
class SubscriptionMessage(Generic[T]):
    """Message sent through subscriptions."""

    event: SubscriptionEvent
    data: T
    model_name: str
    timestamp: float = field(default_factory=lambda: __import__("time").time())


class SubscriptionManager:
    """
    Manages subscriptions for Django models.

    Usage:
        manager = SubscriptionManager()
        manager.subscribe(User, UserType)

        # In your Subscription class
        @subscription
        async def user_updates(self) -> AsyncGenerator[UserType, None]:
            async for message in manager.subscribe_to("User"):
                yield message.data
    """

    _instance: SubscriptionManager | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Map of model name to list of queues
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

        # Map of model to type class
        self._type_map: dict[type[models.Model], type] = {}

        # Connected signal handlers
        self._signal_connected: set[type[models.Model]] = set()

    def register(
        self,
        model: type[models.Model],
        type_class: type,
        events: list[SubscriptionEvent] | None = None,
    ) -> None:
        """
        Register a model for subscriptions.

        Args:
            model: Django model class
            type_class: Strawberry type class
            events: List of events to subscribe to (default: all)
        """
        _require_strawberry()

        self._type_map[model] = type_class
        events = events or list(SubscriptionEvent)

        if model not in self._signal_connected:
            # Connect signals
            if SubscriptionEvent.CREATED in events or SubscriptionEvent.UPDATED in events:
                post_save.connect(self._handle_save, sender=model)

            if SubscriptionEvent.DELETED in events:
                post_delete.connect(self._handle_delete, sender=model)

            self._signal_connected.add(model)

    def _handle_save(self, sender, instance, created, **kwargs):
        """Handle post_save signal."""
        event = SubscriptionEvent.CREATED if created else SubscriptionEvent.UPDATED
        self._broadcast(sender, instance, event)

    def _handle_delete(self, sender, instance, **kwargs):
        """Handle post_delete signal."""
        self._broadcast(sender, instance, SubscriptionEvent.DELETED)

    def _broadcast(
        self,
        model: type[models.Model],
        instance: models.Model,
        event: SubscriptionEvent,
    ) -> None:
        """Broadcast an event to all subscribers."""
        model_name = model.__name__
        type_class = self._type_map.get(model)

        if type_class and hasattr(type_class, "from_orm"):
            data = type_class.from_orm(instance)
        else:
            data = instance

        message = SubscriptionMessage(
            event=event,
            data=data,
            model_name=model_name,
        )

        # Put message in all subscriber queues
        for queue in self._subscribers[model_name]:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass  # Skip if queue is full

    async def subscribe_to(
        self,
        model_name: str,
        events: list[SubscriptionEvent] | None = None,
    ) -> AsyncGenerator[SubscriptionMessage, None]:
        """
        Subscribe to events for a model.

        Args:
            model_name: Name of the model to subscribe to
            events: Filter to specific events (None = all)

        Yields:
            SubscriptionMessage objects
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[model_name].append(queue)

        try:
            while True:
                message = await queue.get()
                if events is None or message.event in events:
                    yield message
        finally:
            self._subscribers[model_name].remove(queue)

    async def subscribe_to_model(
        self,
        model: type[models.Model],
        events: list[SubscriptionEvent] | None = None,
    ) -> AsyncGenerator[SubscriptionMessage, None]:
        """
        Subscribe to events for a model by class.

        Args:
            model: Django model class
            events: Filter to specific events

        Yields:
            SubscriptionMessage objects
        """
        async for message in self.subscribe_to(model.__name__, events):
            yield message


# Global instance
_subscription_manager: SubscriptionManager | None = None


def get_subscription_manager() -> SubscriptionManager:
    """Get the global subscription manager."""
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager()
    return _subscription_manager


class SubscriptionGenerator:
    """
    Generate GraphQL subscriptions for a Django model.

    Usage:
        generator = SubscriptionGenerator(User, UserType)

        @strawberry.type
        class Subscription:
            user_created = generator.created_subscription()
            user_updated = generator.updated_subscription()
            user_deleted = generator.deleted_subscription()
            user_changes = generator.all_events_subscription()
    """

    def __init__(
        self,
        model: type[models.Model],
        type_class: type,
        manager: SubscriptionManager | None = None,
    ):
        """
        Initialize the subscription generator.

        Args:
            model: Django model class
            type_class: Strawberry type class
            manager: Optional custom subscription manager
        """
        _require_strawberry()
        self.model = model
        self.type_class = type_class
        self.manager = manager or get_subscription_manager()

        # Register model with manager
        self.manager.register(model, type_class)

    def created_subscription(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> strawberry.subscription:
        """
        Generate a subscription for created events.
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class
        manager = self.manager

        async def resolver(info: Info) -> AsyncGenerator[type_class, None]:
            async for message in manager.subscribe_to(
                model.__name__,
                events=[SubscriptionEvent.CREATED],
            ):
                yield message.data

        return strawberry.subscription(
            resolver,
            name=name or f"{model.__name__.lower()}_created",
            description=description or f"Subscribe to new {model.__name__} objects",
        )

    def updated_subscription(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> strawberry.subscription:
        """
        Generate a subscription for updated events.
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class
        manager = self.manager

        async def resolver(info: Info) -> AsyncGenerator[type_class, None]:
            async for message in manager.subscribe_to(
                model.__name__,
                events=[SubscriptionEvent.UPDATED],
            ):
                yield message.data

        return strawberry.subscription(
            resolver,
            name=name or f"{model.__name__.lower()}_updated",
            description=description or f"Subscribe to {model.__name__} updates",
        )

    def deleted_subscription(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> strawberry.subscription:
        """
        Generate a subscription for deleted events.
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class
        manager = self.manager

        # For deleted events, we return the ID since the object is gone
        @strawberry.type
        class DeletedEvent:
            id: strawberry.ID
            model_name: str

        async def resolver(info: Info) -> AsyncGenerator[DeletedEvent, None]:
            async for message in manager.subscribe_to(
                model.__name__,
                events=[SubscriptionEvent.DELETED],
            ):
                yield DeletedEvent(
                    id=strawberry.ID(
                        str(message.data.id if hasattr(message.data, "id") else message.data)
                    ),
                    model_name=message.model_name,
                )

        return strawberry.subscription(
            resolver,
            name=name or f"{model.__name__.lower()}_deleted",
            description=description or f"Subscribe to {model.__name__} deletions",
        )

    def all_events_subscription(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> strawberry.subscription:
        """
        Generate a subscription for all events (create, update, delete).
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class
        manager = self.manager

        @strawberry.type
        class ModelEvent:
            event: str
            data: type_class | None
            timestamp: float

        async def resolver(info: Info) -> AsyncGenerator[ModelEvent, None]:
            async for message in manager.subscribe_to(model.__name__):
                yield ModelEvent(
                    event=message.event.value,
                    data=message.data if message.event != SubscriptionEvent.DELETED else None,
                    timestamp=message.timestamp,
                )

        return strawberry.subscription(
            resolver,
            name=name or f"{model.__name__.lower()}_events",
            description=description or f"Subscribe to all {model.__name__} events",
        )


def generate_subscription(
    model: type[models.Model],
    type_class: type,
    events: list[SubscriptionEvent] | None = None,
    name: str | None = None,
    description: str | None = None,
) -> strawberry.subscription:
    """
    Convenience function to generate a subscription.

    Args:
        model: Django model class
        type_class: Strawberry type class
        events: Events to subscribe to (default: all)
        name: Subscription name
        description: Subscription description

    Returns:
        Strawberry subscription descriptor
    """
    _require_strawberry()
    generator = SubscriptionGenerator(model, type_class)

    if events is None or len(events) > 1:
        return generator.all_events_subscription(name=name, description=description)
    if events[0] == SubscriptionEvent.CREATED:
        return generator.created_subscription(name=name, description=description)
    if events[0] == SubscriptionEvent.UPDATED:
        return generator.updated_subscription(name=name, description=description)
    if events[0] == SubscriptionEvent.DELETED:
        return generator.deleted_subscription(name=name, description=description)

    return generator.all_events_subscription(name=name, description=description)


def subscribe_to_model(
    model: type[models.Model],
    type_class: type,
    events: list[SubscriptionEvent] | None = None,
) -> Callable:
    """
    Decorator to create a subscription for a model.

    Usage:
        @strawberry.type
        class Subscription:
            @subscribe_to_model(User, UserType)
            async def user_updates(self) -> AsyncGenerator[UserType, None]:
                pass  # Implementation is provided by decorator
    """
    _require_strawberry()

    def decorator(func: Callable) -> strawberry.subscription:
        manager = get_subscription_manager()
        manager.register(model, type_class)

        async def resolver(info: Info) -> AsyncGenerator:
            async for message in manager.subscribe_to(model.__name__, events):
                yield message.data

        return strawberry.subscription(
            resolver,
            name=func.__name__,
            description=func.__doc__,
        )

    return decorator


__all__ = [
    "SubscriptionEvent",
    "SubscriptionMessage",
    "SubscriptionManager",
    "SubscriptionGenerator",
    "get_subscription_manager",
    "generate_subscription",
    "subscribe_to_model",
]

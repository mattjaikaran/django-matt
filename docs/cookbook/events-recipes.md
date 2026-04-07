# Event Bus Recipes

Async event bus for decoupled pub/sub communication within your application.

## User Lifecycle Events (Created, Updated, Deleted)

```python
from django_matt.events import (
    UserCreatedEvent,
    UserDeletedEvent,
    UserUpdatedEvent,
    get_event_bus,
    on,
)


# Subscribe to events with the @on decorator
@on(UserCreatedEvent)
async def send_welcome_email(event: UserCreatedEvent):
    await email_service.send_welcome(event.email, event.user_id)


@on(UserUpdatedEvent)
async def sync_profile_to_crm(event: UserUpdatedEvent):
    await crm_client.update_contact(event.user_id, event.changes)


@on(UserDeletedEvent)
async def cleanup_user_data(event: UserDeletedEvent):
    await storage_service.delete_user_files(event.user_id)
    await cache.delete(f"user:{event.user_id}")


# Emit events from your service layer
async def create_user(data: dict) -> User:
    user = await User.objects.acreate(**data)
    bus = get_event_bus()
    await bus.emit(UserCreatedEvent(user_id=user.pk, email=user.email))
    return user
```

## Order Processing Pipeline

```python
from typing import Any

from pydantic import Field

from django_matt.events import Event, get_event_bus, on


class OrderPlacedEvent(Event):
    __event_type__ = "order.placed"
    event_type: str = "order.placed"
    order_id: int = 0
    total: float = 0.0
    items: list[dict[str, Any]] = Field(default_factory=list)


class OrderPaidEvent(Event):
    __event_type__ = "order.paid"
    event_type: str = "order.paid"
    order_id: int = 0
    payment_id: str = ""


class OrderShippedEvent(Event):
    __event_type__ = "order.shipped"
    event_type: str = "order.shipped"
    order_id: int = 0
    tracking_number: str = ""


@on(OrderPlacedEvent)
async def reserve_inventory(event: OrderPlacedEvent):
    for item in event.items:
        await inventory_service.reserve(item["sku"], item["qty"])


@on(OrderPaidEvent)
async def fulfill_order(event: OrderPaidEvent):
    await fulfillment_service.start(event.order_id)


@on(OrderShippedEvent)
async def notify_customer(event: OrderShippedEvent):
    order = await Order.objects.aget(pk=event.order_id)
    await email_service.send_shipping_notification(
        order.customer_email, event.tracking_number
    )
```

## Audit Logging via Events

```python
import logging

from django_matt.events import Event, get_event_bus, on

audit_logger = logging.getLogger("audit")


class AuditEvent(Event):
    __event_type__ = "audit"
    event_type: str = "audit"
    actor_id: int | str | None = None
    action: str = ""
    resource_type: str = ""
    resource_id: int | str | None = None
    details: dict = {}


@on("audit")
async def write_audit_log(event: AuditEvent):
    audit_logger.info(
        "audit_trail",
        extra={
            "actor": event.actor_id,
            "action": event.action,
            "resource": f"{event.resource_type}:{event.resource_id}",
            "details": event.details,
            "timestamp": event.timestamp,
        },
    )


@on("audit")
async def persist_audit_record(event: AuditEvent):
    await AuditLog.objects.acreate(
        actor_id=event.actor_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=str(event.resource_id),
        details=event.details,
    )


# Usage in a controller
async def delete_product(request, product_id: int):
    product = await Product.objects.aget(pk=product_id)
    await product.adelete()

    bus = get_event_bus()
    await bus.emit(AuditEvent(
        actor_id=request.user.pk,
        action="delete",
        resource_type="Product",
        resource_id=product_id,
    ))
```

## Email Notifications on Events

```python
from django_matt.events import on


@on("user.created")
async def send_welcome(event):
    await email_service.send(
        to=event.email,
        template="welcome",
        context={"user_id": event.user_id},
    )


@on("order.placed")
async def send_order_confirmation(event):
    order = await Order.objects.select_related("customer").aget(pk=event.order_id)
    await email_service.send(
        to=order.customer.email,
        template="order_confirmation",
        context={"order_id": event.order_id, "total": event.total},
    )


@on("user.deleted")
async def send_farewell(event):
    user = await User.objects.aget(pk=event.user_id)
    await email_service.send(
        to=user.email,
        template="account_deleted",
        context={"user_id": event.user_id},
    )
```

## Wildcard Event Subscriptions

```python
from django_matt.events import get_event_bus, on


# Match all order events using fnmatch glob patterns
@on("order.*")
async def log_all_order_events(event):
    print(f"Order event: {event.event_type} at {event.timestamp}")


# Match all model lifecycle events
@on("model.*")
async def track_model_changes(event):
    await analytics.track("model_change", {
        "type": event.event_type,
        "model": getattr(event, "model_name", "unknown"),
    })


# Match everything
@on("*")
async def global_event_monitor(event):
    metrics.increment("events_total", tags={"type": event.event_type})
```

## Cross-Service Communication with Redis Backend

```python
from django_matt.events import EventBus, RedisBackend, get_event_bus

# In your AppConfig.ready() or startup script
bus = get_event_bus()
redis_backend = RedisBackend(redis_url="redis://localhost:6379/0")
bus.backend = redis_backend

# Subscribe via the Redis backend for cross-process delivery
await redis_backend.subscribe("order.*", handle_order_event)


# Publishing — events go to both local handlers and Redis pub/sub
async def place_order(data: dict):
    order = await Order.objects.acreate(**data)
    event = OrderPlacedEvent(order_id=order.pk, total=order.total)

    # Local handlers
    await bus.emit(event)

    # Cross-service via Redis
    await redis_backend.publish(event)


# Cleanup on shutdown
async def shutdown():
    await redis_backend.close()
```

## Event Replay Patterns

```python
from django_matt.events import Event, get_event_bus


async def replay_events(
    since_timestamp: float,
    event_types: list[str] | None = None,
) -> int:
    """Replay persisted events through the bus for reprocessing."""
    bus = get_event_bus()
    query = EventLog.objects.filter(timestamp__gte=since_timestamp).order_by("timestamp")

    if event_types:
        query = query.filter(event_type__in=event_types)

    count = 0
    async for record in query.aiterator(chunk_size=100):
        event = Event(
            event_type=record.event_type,
            timestamp=record.timestamp,
            metadata={**record.metadata, "replayed": True},
        )
        await bus.emit(event)
        count += 1

    return count


# Usage: replay all order events from the last hour
import time

replayed = await replay_events(
    since_timestamp=time.time() - 3600,
    event_types=["order.placed", "order.paid"],
)
```

## EventMiddleware Setup

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.events.EventMiddleware",
]

# In your views — collect events during the request cycle
from django_matt.events import collect_event

async def update_product(request, product_id: int):
    product = await Product.objects.aget(pk=product_id)
    product.name = request.data["name"]
    await product.asave()

    # Events are collected and emitted after the response
    collect_event(request, ModelUpdatedEvent(
        model_name="Product",
        instance_id=product_id,
        changes={"name": request.data["name"]},
    ))

    return JsonResponse({"id": product_id})
```

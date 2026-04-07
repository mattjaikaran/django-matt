"""Order domain event handlers."""

import logging

from django_matt.events import on

logger = logging.getLogger(__name__)


@on("order.created")
async def on_order_created(event):
    """Handle order created event — send confirmation, update analytics."""
    logger.info(f"Order created: {event.data['order_id']} for ${event.data['total']}")


@on("order.cancelled")
async def on_order_cancelled(event):
    """Handle order cancelled event — notify store owner."""
    logger.info(f"Order cancelled: {event.data['order_id']}")


@on("order.*")
async def on_any_order_event(event):
    """Audit log for all order events."""
    logger.info(f"Order event: {event.name} — {event.data}")

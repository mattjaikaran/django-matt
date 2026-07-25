"""
Event handlers for chat domain events.

Uses django-matt's event bus to react to messages asynchronously.
"""

import logging

from django_matt.events.decorators import on

logger = logging.getLogger(__name__)


@on("chat.message.sent")
async def log_message_sent(*, conversation_id: str, message_id: str, role: str, **kwargs):
    """Log every message for analytics."""
    logger.info(
        "Message sent: conversation=%s message=%s role=%s", conversation_id, message_id, role
    )


@on("chat.stream.complete")
async def update_conversation_title(*, conversation_id: str, **kwargs):
    """Auto-generate a title after the first assistant response."""
    from chat.models import Conversation

    conversation = await Conversation.objects.aget(id=conversation_id)
    if not conversation.title:
        first_msg = await conversation.messages.filter(role="user").afirst()
        if first_msg:
            conversation.title = first_msg.content[:100]
            await conversation.asave(update_fields=["title", "updated_at"])
            logger.info("Auto-titled conversation %s: %s", conversation_id, conversation.title)

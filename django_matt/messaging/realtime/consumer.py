"""
Messaging WebSocket consumer.

Handles real-time messaging over WebSocket connections.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from django_matt.messaging.realtime.events import (
    EventType,
    create_message_event,
    create_read_receipt_event,
    create_typing_event,
)
from django_matt.websockets.consumers import AuthenticatedConsumer

logger = logging.getLogger(__name__)


class MessagingConsumer(AuthenticatedConsumer):
    """
    WebSocket consumer for messaging.

    Provides real-time features:
    - Message delivery
    - Typing indicators
    - Read receipts
    - Presence updates
    - Conversation subscription

    Usage:
        # In routing.py
        from django_matt.messaging.realtime import MessagingConsumer

        websocket_urlpatterns = [
            path("ws/messaging/", MessagingConsumer.as_asgi()),
        ]

    Client messages:
        # Subscribe to conversations
        {"type": "subscribe", "conversation_ids": [1, 2, 3]}

        # Unsubscribe from conversations
        {"type": "unsubscribe", "conversation_ids": [1]}

        # Send typing indicator
        {"type": "typing", "conversation_id": 1, "is_typing": true}

        # Send message (via WebSocket)
        {"type": "send_message", "conversation_id": 1, "content": "Hello!"}

        # Mark as read
        {"type": "mark_read", "conversation_id": 1, "message_id": 123}
    """

    # Prefix for conversation groups
    CONVERSATION_GROUP_PREFIX = "conversation_"

    def __init__(self, scope: dict, receive: Callable, send: Callable):
        super().__init__(scope, receive, send)
        self._subscribed_conversations: set[int] = set()

    async def on_connect(self) -> None:
        """Accept connection and register user presence."""
        await super().on_connect()

        if self.is_authenticated:
            # Update user presence
            from django_matt.messaging.services import PresenceService

            PresenceService.set_online(self.user.id)

            # Join user-specific channel for direct notifications
            await self.join_group(f"user_{self.user.id}")

    async def on_disconnect(self, code: int) -> None:
        """Handle disconnect and cleanup."""
        if self.is_authenticated:
            # Update presence to offline
            from django_matt.messaging.services import PresenceService

            PresenceService.set_offline(self.user.id)

            # Clear any active typing indicators
            for conv_id in self._subscribed_conversations:
                PresenceService.clear_typing(conv_id, self.user.id)

        await super().on_disconnect(code)

    def _get_conversation_group(self, conversation_id: int) -> str:
        """Get the group name for a conversation."""
        return f"{self.CONVERSATION_GROUP_PREFIX}{conversation_id}"

    async def _verify_conversation_access(self, conversation_id: int) -> bool:
        """Verify user has access to conversation."""
        from django_matt.messaging.models import Conversation

        try:
            conversation = await Conversation.objects.aget(id=conversation_id)
            return await conversation.ais_member(self.user)
        except Conversation.DoesNotExist:
            return False

    # -------------------------------------------------------------------------
    # Message Handlers
    # -------------------------------------------------------------------------

    async def handle_subscribe(self, data: dict) -> None:
        """Subscribe to conversation updates."""
        conversation_ids = data.get("conversation_ids", [])
        subscribed = []

        for conv_id in conversation_ids:
            if await self._verify_conversation_access(conv_id):
                group_name = self._get_conversation_group(conv_id)
                if await self.join_group(group_name):
                    self._subscribed_conversations.add(conv_id)
                    subscribed.append(conv_id)

        await self.send_json(
            {
                "type": "subscribed",
                "conversation_ids": subscribed,
            }
        )

    async def handle_unsubscribe(self, data: dict) -> None:
        """Unsubscribe from conversation updates."""
        conversation_ids = data.get("conversation_ids", [])

        for conv_id in conversation_ids:
            if conv_id in self._subscribed_conversations:
                group_name = self._get_conversation_group(conv_id)
                await self.leave_group(group_name)
                self._subscribed_conversations.discard(conv_id)

                # Clear typing indicator
                from django_matt.messaging.services import PresenceService

                PresenceService.clear_typing(conv_id, self.user.id)

        await self.send_json(
            {
                "type": "unsubscribed",
                "conversation_ids": conversation_ids,
            }
        )

    async def handle_typing(self, data: dict) -> None:
        """Handle typing indicator."""
        conversation_id = data.get("conversation_id")
        is_typing = data.get("is_typing", True)

        if not conversation_id or conversation_id not in self._subscribed_conversations:
            return

        from django_matt.messaging.services import PresenceService

        if is_typing:
            PresenceService.set_typing(conversation_id, self.user.id)
        else:
            PresenceService.clear_typing(conversation_id, self.user.id)

        # Broadcast to conversation
        event = create_typing_event(conversation_id, self.user.id, is_typing)
        await self.broadcast_to_group(
            self._get_conversation_group(conversation_id),
            event,
            exclude_self=True,
        )

    async def handle_send_message(self, data: dict) -> None:
        """Handle sending a message via WebSocket."""
        conversation_id = data.get("conversation_id")
        content = data.get("content", "")
        message_type = data.get("message_type", "text")
        reply_to_id = data.get("reply_to_id")

        if not conversation_id or not content:
            await self.send_error(4003, "Missing conversation_id or content")
            return

        if conversation_id not in self._subscribed_conversations:
            await self.send_error(4001, "Not subscribed to conversation")
            return

        from django_matt.messaging.models import Conversation, Message
        from django_matt.messaging.services import MessageService, PresenceService

        try:
            conversation = await Conversation.objects.aget(id=conversation_id)

            reply_to = None
            if reply_to_id:
                try:
                    reply_to = await Message.objects.aget(
                        id=reply_to_id,
                        conversation=conversation,
                    )
                except Message.DoesNotExist:
                    pass

            # Send message
            message = await MessageService.asend_message(
                conversation=conversation,
                sender=self.user,
                content=content,
                message_type=message_type,
                reply_to=reply_to,
            )

            # Clear typing indicator
            PresenceService.clear_typing(conversation_id, self.user.id)

            # Broadcast to conversation
            event = create_message_event(
                EventType.MESSAGE_NEW,
                conversation_id,
                message.id,
                sender_id=self.user.id,
                content=content,
            )
            await self.broadcast_to_group(
                self._get_conversation_group(conversation_id),
                event,
            )

            # Send confirmation to sender
            await self.send_json(
                {
                    "type": "message_sent",
                    "message_id": message.id,
                    "conversation_id": conversation_id,
                }
            )

        except PermissionError as e:
            await self.send_error(4001, str(e))
        except Exception as e:
            logger.exception(f"Error sending message: {e}")
            await self.send_error(1011, "Failed to send message")

    async def handle_mark_read(self, data: dict) -> None:
        """Handle marking messages as read."""
        conversation_id = data.get("conversation_id")
        message_id = data.get("message_id")

        if not conversation_id:
            return

        if conversation_id not in self._subscribed_conversations:
            return

        from django_matt.messaging.models import Conversation, Message
        from django_matt.messaging.services import MessageService

        try:
            conversation = await Conversation.objects.aget(id=conversation_id)

            up_to_message = None
            if message_id:
                try:
                    up_to_message = await Message.objects.aget(
                        id=message_id,
                        conversation=conversation,
                    )
                except Message.DoesNotExist:
                    pass

            await MessageService.amark_as_read(conversation, self.user, up_to_message)

            # Broadcast read receipt to conversation
            event = create_read_receipt_event(
                conversation_id,
                self.user.id,
                message_id,
            )
            await self.broadcast_to_group(
                self._get_conversation_group(conversation_id),
                event,
                exclude_self=True,
            )

        except Exception as e:
            logger.exception(f"Error marking as read: {e}")

    async def handle_ping(self, data: dict) -> None:
        """Handle heartbeat ping."""
        conversation_id = data.get("conversation_id")

        from django_matt.messaging.services import PresenceService

        PresenceService.heartbeat(self.user.id, conversation_id)

        await self.send_json({"type": "pong"})

    # -------------------------------------------------------------------------
    # Group Message Handlers (from channel layer)
    # -------------------------------------------------------------------------

    async def messaging_event(self, event: dict) -> None:
        """Handle messaging event from channel layer."""
        data = event.get("data", {})
        await self.send_json(data)


def get_conversation_group_name(conversation_id: int) -> str:
    """Get the channel layer group name for a conversation."""
    return f"{MessagingConsumer.CONVERSATION_GROUP_PREFIX}{conversation_id}"


async def broadcast_to_conversation(
    conversation_id: int,
    event: dict,
    exclude_user_id: int | None = None,
) -> None:
    """
    Broadcast an event to all users in a conversation.

    Can be called from anywhere (views, services, signals).

    Args:
        conversation_id: Target conversation
        event: Event data to broadcast
        exclude_user_id: Optional user ID to exclude from broadcast
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("No channel layer configured")
        return

    group_name = get_conversation_group_name(conversation_id)

    message: dict[str, Any] = {
        "type": "messaging_event",
        "data": event,
    }

    if exclude_user_id:
        message["exclude_user_id"] = exclude_user_id

    await channel_layer.group_send(group_name, message)


async def send_to_user(user_id: int, event: dict) -> None:
    """
    Send an event to a specific user.

    Args:
        user_id: Target user ID
        event: Event data to send
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("No channel layer configured")
        return

    group_name = f"user_{user_id}"

    await channel_layer.group_send(
        group_name,
        {
            "type": "messaging_event",
            "data": event,
        },
    )

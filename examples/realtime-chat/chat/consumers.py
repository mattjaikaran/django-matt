"""
WebSocket consumers for real-time chat functionality.

Handles:
- Real-time message delivery
- Typing indicators
- Presence tracking
- Read receipts
- Reactions
"""

import logging
from datetime import datetime
from uuid import UUID

from django.contrib.auth import get_user_model

from django_matt.websockets import (
    AuthenticatedConsumer,
    RoomConsumer,
    get_presence_manager,
)

from .models import Channel
from .services import (
    ChannelService,
    MessageService,
    ReactionService,
    ReadReceiptService,
    UserService,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatConsumer(RoomConsumer):
    """
    Main WebSocket consumer for the chat application.

    Handles all real-time events:
    - message.send / message.new
    - message.update / message.updated
    - message.delete / message.deleted
    - typing.start / typing.stop / typing.update
    - presence.update / presence.changed
    - reaction.add / reaction.remove / reaction.added / reaction.removed
    - channel.join / channel.joined / channel.leave / channel.left
    - read_receipt.mark / read_receipt.updated
    """

    # Require authentication
    auth_required = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_channel: Channel | None = None
        self.current_channel_id: UUID | None = None
        self.typing_users: dict[str, set[int]] = {}  # channel_id -> set of user_ids
        self.presence = get_presence_manager()

    async def on_connect(self) -> None:
        """Handle WebSocket connection."""
        if not self.is_authenticated:
            await self.close(code=4001)
            return

        await self.accept()

        # Update user presence to online
        await UserService.update_presence(self.user, "online")

        # Join user's personal notification channel
        user_group = f"user_{self.user.id}"
        await self.join_group(user_group)

        # Track presence
        await self.presence.user_joined(
            group_name=user_group,
            user_id=str(self.user.id),
            channel_name=self.channel_name,
            metadata={"username": self.user.username},
        )

        # Send connection confirmation
        await self.send_json(
            {
                "type": "connected",
                "user_id": self.user.id,
                "username": self.user.username,
            }
        )

        logger.info(f"User {self.user.username} connected")

    async def on_disconnect(self, code: int) -> None:
        """Handle WebSocket disconnection."""
        if not self.is_authenticated:
            return

        # Update presence to offline
        await UserService.update_presence(self.user, "offline")

        # Leave current channel
        if self.current_channel_id:
            await self._leave_channel()

        # Remove from user group
        user_group = f"user_{self.user.id}"
        await self.presence.user_left(user_group, str(self.user.id))
        await self.leave_group(user_group)

        # Notify about presence change
        await self._broadcast_presence_change("offline")

        logger.info(f"User {self.user.username} disconnected")

    # =========================================================================
    # Channel Events
    # =========================================================================

    async def handle_channel_join(self, data: dict) -> None:
        """Handle channel.join event."""
        channel_id = data.get("channel_id")
        if not channel_id:
            await self.send_error(4003, "channel_id required")
            return

        try:
            channel_uuid = UUID(channel_id)
        except ValueError:
            await self.send_error(4003, "Invalid channel_id format")
            return

        # Leave current channel if any
        if self.current_channel_id:
            await self._leave_channel()

        # Get channel and verify access
        channel = await ChannelService.get_channel(channel_uuid, self.user)
        if not channel:
            await self.send_error(4004, "Channel not found or access denied")
            return

        self.current_channel = channel
        self.current_channel_id = channel_uuid

        # Join channel group
        channel_group = f"channel_{channel_uuid}"
        await self.join_group(channel_group)

        # Track presence in channel
        await self.presence.user_joined(
            group_name=channel_group,
            user_id=str(self.user.id),
            channel_name=self.channel_name,
            metadata={"username": self.user.username},
        )

        # Get recent messages
        messages = await MessageService.get_channel_messages(channel, limit=50)
        message_responses = [
            MessageService.to_response(m, self.user).model_dump(mode="json") for m in messages
        ]

        # Get online members
        presence_list = await self.presence.get_users(channel_group)
        online_users = [
            {"user_id": int(p.user_id), "username": p.metadata.get("username")}
            for p in presence_list
        ]

        # Send joined confirmation
        await self.send_json(
            {
                "type": "channel.joined",
                "channel": {
                    "id": str(channel.id),
                    "name": channel.name,
                    "description": channel.description,
                    "topic": channel.topic,
                },
                "recent_messages": message_responses,
                "members_online": online_users,
            }
        )

        # Notify others in channel
        await self.broadcast_to_group(
            channel_group,
            {
                "type": "user.joined",
                "channel_id": str(channel_uuid),
                "user": {
                    "id": self.user.id,
                    "username": self.user.username,
                },
            },
            exclude_self=True,
        )

        logger.info(f"User {self.user.username} joined channel {channel.name}")

    async def handle_channel_leave(self, data: dict) -> None:
        """Handle channel.leave event."""
        if self.current_channel_id:
            await self._leave_channel()

    async def _leave_channel(self) -> None:
        """Internal method to leave current channel."""
        if not self.current_channel_id:
            return

        channel_group = f"channel_{self.current_channel_id}"

        # Notify others
        await self.broadcast_to_group(
            channel_group,
            {
                "type": "user.left",
                "channel_id": str(self.current_channel_id),
                "user": {
                    "id": self.user.id,
                    "username": self.user.username,
                },
            },
            exclude_self=True,
        )

        # Remove typing indicator
        if str(self.current_channel_id) in self.typing_users:
            self.typing_users[str(self.current_channel_id)].discard(self.user.id)

        # Leave presence and group
        await self.presence.user_left(channel_group, str(self.user.id))
        await self.leave_group(channel_group)

        # Send confirmation
        await self.send_json(
            {
                "type": "channel.left",
                "channel_id": str(self.current_channel_id),
            }
        )

        self.current_channel = None
        self.current_channel_id = None

    # =========================================================================
    # Message Events
    # =========================================================================

    async def handle_message_send(self, data: dict) -> None:
        """Handle message.send event."""
        channel_id = data.get("channel_id")
        content = data.get("content", "").strip()
        thread_id = data.get("thread_id")
        attachment_ids = data.get("attachment_ids", [])

        if not content:
            await self.send_error(4003, "Message content required")
            return

        # Verify we're in the channel
        if not channel_id or str(self.current_channel_id) != channel_id:
            await self.send_error(4003, "Must join channel first")
            return

        # Create message
        try:
            parent_id = UUID(thread_id) if thread_id else None
            attach_ids = [UUID(aid) for aid in attachment_ids] if attachment_ids else []

            message = await MessageService.create(
                user=self.user,
                content=content,
                channel=self.current_channel,
                parent_message_id=parent_id,
                attachment_ids=attach_ids,
            )

            # Convert to response
            message_data = MessageService.to_response(message, self.user).model_dump(mode="json")

            # Broadcast to channel
            await self.broadcast_to_group(
                f"channel_{self.current_channel_id}",
                {
                    "type": "message.new",
                    "message": message_data,
                },
            )

            # Stop typing indicator
            await self._stop_typing()

            logger.debug(
                f"Message sent by {self.user.username} in channel {self.current_channel_id}"
            )

        except Exception as e:
            logger.exception(f"Error sending message: {e}")
            await self.send_error(5000, f"Failed to send message: {e!s}")

    async def handle_message_update(self, data: dict) -> None:
        """Handle message.update event."""
        message_id = data.get("message_id")
        content = data.get("content", "").strip()

        if not message_id or not content:
            await self.send_error(4003, "message_id and content required")
            return

        try:
            message = await MessageService.get_message(UUID(message_id))
            if not message:
                await self.send_error(4004, "Message not found")
                return

            if message.author_id != self.user.id:
                await self.send_error(4003, "Can only edit own messages")
                return

            # Update message
            message = await MessageService.update(message, content)

            # Convert to response
            message_data = MessageService.to_response(message, self.user).model_dump(mode="json")

            # Broadcast update
            channel_id = message.channel_id or message.dm_thread_id
            await self.broadcast_to_group(
                f"channel_{channel_id}",
                {
                    "type": "message.updated",
                    "message": message_data,
                },
            )

        except Exception as e:
            logger.exception(f"Error updating message: {e}")
            await self.send_error(5000, f"Failed to update message: {e!s}")

    async def handle_message_delete(self, data: dict) -> None:
        """Handle message.delete event."""
        message_id = data.get("message_id")

        if not message_id:
            await self.send_error(4003, "message_id required")
            return

        try:
            message = await MessageService.get_message(UUID(message_id))
            if not message:
                await self.send_error(4004, "Message not found")
                return

            if message.author_id != self.user.id:
                await self.send_error(4003, "Can only delete own messages")
                return

            channel_id = message.channel_id or message.dm_thread_id

            # Delete message
            await MessageService.delete(message)

            # Broadcast deletion
            await self.broadcast_to_group(
                f"channel_{channel_id}",
                {
                    "type": "message.deleted",
                    "channel_id": str(channel_id),
                    "message_id": str(message_id),
                },
            )

        except Exception as e:
            logger.exception(f"Error deleting message: {e}")
            await self.send_error(5000, f"Failed to delete message: {e!s}")

    # =========================================================================
    # Typing Events
    # =========================================================================

    async def handle_typing_start(self, data: dict) -> None:
        """Handle typing.start event."""
        if not self.current_channel_id:
            return

        channel_key = str(self.current_channel_id)
        if channel_key not in self.typing_users:
            self.typing_users[channel_key] = set()

        self.typing_users[channel_key].add(self.user.id)

        await self._broadcast_typing_update()

    async def handle_typing_stop(self, data: dict) -> None:
        """Handle typing.stop event."""
        await self._stop_typing()

    async def _stop_typing(self) -> None:
        """Internal method to stop typing indicator."""
        if not self.current_channel_id:
            return

        channel_key = str(self.current_channel_id)
        if channel_key in self.typing_users:
            self.typing_users[channel_key].discard(self.user.id)
            await self._broadcast_typing_update()

    async def _broadcast_typing_update(self) -> None:
        """Broadcast typing indicator update."""
        if not self.current_channel_id:
            return

        channel_key = str(self.current_channel_id)
        typing_user_ids = self.typing_users.get(channel_key, set())

        # Get user info for typing users
        users = []
        for user_id in typing_user_ids:
            if user_id != self.user.id:  # Don't include self
                # In production, cache this lookup
                user = await User.objects.filter(id=user_id).afirst()
                if user:
                    users.append({"id": user.id, "username": user.username})

        await self.broadcast_to_group(
            f"channel_{self.current_channel_id}",
            {
                "type": "typing.update",
                "channel_id": str(self.current_channel_id),
                "users": users,
            },
            exclude_self=True,
        )

    # =========================================================================
    # Presence Events
    # =========================================================================

    async def handle_presence_update(self, data: dict) -> None:
        """Handle presence.update event."""
        status = data.get("status", "online")

        if status not in ("online", "away", "dnd", "offline"):
            await self.send_error(4003, "Invalid status")
            return

        await UserService.update_presence(self.user, status)
        await self._broadcast_presence_change(status)

    async def _broadcast_presence_change(self, status: str) -> None:
        """Broadcast presence change to relevant users."""
        # Broadcast to all workspaces user is in
        # In production, be more selective about who receives this
        await self.send_json(
            {
                "type": "presence.changed",
                "user_id": self.user.id,
                "status": status,
                "last_seen": datetime.utcnow().isoformat(),
            }
        )

    # =========================================================================
    # Reaction Events
    # =========================================================================

    async def handle_reaction_add(self, data: dict) -> None:
        """Handle reaction.add event."""
        message_id = data.get("message_id")
        emoji = data.get("emoji", "").strip()

        if not message_id or not emoji:
            await self.send_error(4003, "message_id and emoji required")
            return

        try:
            message = await MessageService.get_message(UUID(message_id))
            if not message:
                await self.send_error(4004, "Message not found")
                return

            # Add reaction
            reaction = await ReactionService.add(message, self.user, emoji)

            if reaction:
                channel_id = message.channel_id or message.dm_thread_id
                await self.broadcast_to_group(
                    f"channel_{channel_id}",
                    {
                        "type": "reaction.added",
                        "channel_id": str(channel_id),
                        "message_id": str(message_id),
                        "emoji": emoji,
                        "user": {
                            "id": self.user.id,
                            "username": self.user.username,
                        },
                    },
                )

        except Exception as e:
            logger.exception(f"Error adding reaction: {e}")
            await self.send_error(5000, f"Failed to add reaction: {e!s}")

    async def handle_reaction_remove(self, data: dict) -> None:
        """Handle reaction.remove event."""
        message_id = data.get("message_id")
        emoji = data.get("emoji", "").strip()

        if not message_id or not emoji:
            await self.send_error(4003, "message_id and emoji required")
            return

        try:
            message = await MessageService.get_message(UUID(message_id))
            if not message:
                await self.send_error(4004, "Message not found")
                return

            # Remove reaction
            removed = await ReactionService.remove(message, self.user, emoji)

            if removed:
                channel_id = message.channel_id or message.dm_thread_id
                await self.broadcast_to_group(
                    f"channel_{channel_id}",
                    {
                        "type": "reaction.removed",
                        "channel_id": str(channel_id),
                        "message_id": str(message_id),
                        "emoji": emoji,
                        "user_id": self.user.id,
                    },
                )

        except Exception as e:
            logger.exception(f"Error removing reaction: {e}")
            await self.send_error(5000, f"Failed to remove reaction: {e!s}")

    # =========================================================================
    # Read Receipt Events
    # =========================================================================

    async def handle_read_receipt_mark(self, data: dict) -> None:
        """Handle read_receipt.mark event."""
        channel_id = data.get("channel_id")
        message_id = data.get("message_id")

        if not channel_id or not message_id:
            await self.send_error(4003, "channel_id and message_id required")
            return

        try:
            message = await MessageService.get_message(UUID(message_id))
            if not message:
                await self.send_error(4004, "Message not found")
                return

            # Mark as read
            await ReadReceiptService.mark_read(
                user=self.user,
                message=message,
                channel=message.channel,
                dm_thread=message.dm_thread,
            )

            # Acknowledge
            await self.send_json(
                {
                    "type": "read_receipt.updated",
                    "channel_id": str(channel_id),
                    "last_read_message_id": str(message_id),
                }
            )

        except Exception as e:
            logger.exception(f"Error marking read receipt: {e}")

    # =========================================================================
    # Group Message Handlers (from channel layer)
    # =========================================================================

    async def user_joined(self, event: dict) -> None:
        """Handle user.joined group message."""
        await self.send_json(event.get("data", event))

    async def user_left(self, event: dict) -> None:
        """Handle user.left group message."""
        await self.send_json(event.get("data", event))

    async def message_new(self, event: dict) -> None:
        """Handle message.new group message."""
        await self.send_json(event.get("data", event))

    async def message_updated(self, event: dict) -> None:
        """Handle message.updated group message."""
        await self.send_json(event.get("data", event))

    async def message_deleted(self, event: dict) -> None:
        """Handle message.deleted group message."""
        await self.send_json(event.get("data", event))

    async def typing_update(self, event: dict) -> None:
        """Handle typing.update group message."""
        await self.send_json(event.get("data", event))

    async def reaction_added(self, event: dict) -> None:
        """Handle reaction.added group message."""
        await self.send_json(event.get("data", event))

    async def reaction_removed(self, event: dict) -> None:
        """Handle reaction.removed group message."""
        await self.send_json(event.get("data", event))

    async def presence_changed(self, event: dict) -> None:
        """Handle presence.changed group message."""
        await self.send_json(event.get("data", event))

    async def direct_message(self, event: dict) -> None:
        """Handle direct message to this user."""
        await self.send_json(event.get("data", event))


class NotificationConsumer(AuthenticatedConsumer):
    """
    Consumer for user-specific notifications.

    Receives:
    - Direct messages
    - Mentions
    - Channel invites
    - System notifications
    """

    async def on_connect(self) -> None:
        """Connect and join user's notification channel."""
        await super().on_connect()

        if not self.is_authenticated:
            return

        # Join user's personal notification group
        user_group = f"notifications_{self.user.id}"
        await self.join_group(user_group)

        logger.info(f"User {self.user.username} connected to notifications")

    async def on_disconnect(self, code: int) -> None:
        """Leave notification channel on disconnect."""
        if self.is_authenticated:
            await self.leave_group(f"notifications_{self.user.id}")

    async def notification(self, event: dict) -> None:
        """Handle notification event."""
        await self.send_json(event.get("data", event))

    async def mention(self, event: dict) -> None:
        """Handle mention notification."""
        await self.send_json(event.get("data", event))

    async def dm_notification(self, event: dict) -> None:
        """Handle DM notification."""
        await self.send_json(event.get("data", event))

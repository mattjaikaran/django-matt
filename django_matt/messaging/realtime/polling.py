"""
Polling controller for messaging.

Provides HTTP-based polling for clients that don't support WebSockets.
"""

from __future__ import annotations

from datetime import datetime

from django.http import HttpRequest
from django.utils import timezone

from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionDeniedAPIError
from django_matt.messaging.models import Conversation, Message
from django_matt.messaging.services import MessageService, PresenceService
from django_matt.permissions import IsAuthenticated


class PollingSchema:
    """Schema classes for polling responses."""


class PollingController(APIController):
    """
    Controller for long-polling message updates.

    Provides an alternative to WebSockets for real-time updates.
    Clients should poll these endpoints periodically.

    Recommended polling intervals:
    - Active conversation: 2-5 seconds
    - Background: 30-60 seconds
    - Typing indicators: 1-2 seconds
    """

    tags = ["Messaging", "Polling"]
    permission_classes = [IsAuthenticated]

    def poll_messages(
        self,
        request: HttpRequest,
        conversation_id: int,
    ) -> dict:
        """
        Poll for new messages in a conversation.

        Query params:
        - since: ISO timestamp or message ID to get messages after
        - limit: Maximum number of messages (default 50, max 100)

        Returns new messages and metadata.
        """
        conversation = self._get_conversation(conversation_id, request.user)

        # Parse 'since' parameter
        since = request.GET.get("since")
        since_message_id = None
        since_timestamp = None

        if since:
            try:
                since_message_id = int(since)
            except ValueError:
                try:
                    since_timestamp = datetime.fromisoformat(since.replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Get limit
        limit = min(int(request.GET.get("limit", 50)), 100)

        # Query new messages
        messages_qs = Message.objects.filter(conversation=conversation)

        if since_message_id:
            messages_qs = messages_qs.filter(id__gt=since_message_id)
        elif since_timestamp:
            messages_qs = messages_qs.filter(created_at__gt=since_timestamp)

        messages_qs = (
            messages_qs.select_related("sender")
            .prefetch_related("attachments", "reactions")
            .order_by("created_at")[:limit]
        )

        messages_list = list(messages_qs)

        # Update presence heartbeat
        PresenceService.heartbeat(request.user.id, conversation_id)

        # Get latest message ID for next poll
        last_message_id = messages_list[-1].id if messages_list else since_message_id

        return {
            "messages": [self._message_to_dict(m) for m in messages_list],
            "count": len(messages_list),
            "last_message_id": last_message_id,
            "timestamp": timezone.now().isoformat(),
        }

    def poll_updates(
        self,
        request: HttpRequest,
    ) -> dict:
        """
        Poll for updates across all conversations.

        Returns:
        - Unread counts per conversation
        - New messages summary
        - Typing indicators
        - Online users in active conversations

        Query params:
        - conversation_ids: Comma-separated list of conversation IDs to check
        """
        user = request.user

        # Get conversation IDs to check
        conv_ids_param = request.GET.get("conversation_ids", "")
        if conv_ids_param:
            conversation_ids = [int(x) for x in conv_ids_param.split(",") if x.isdigit()]
        else:
            # Get all user's conversations
            from django_matt.messaging.services import ConversationService

            conversations = ConversationService.get_user_conversations(user)
            conversation_ids = [c.id for c in conversations[:50]]

        # Get unread counts
        unread_counts = MessageService.get_unread_counts(user)

        # Get typing users for each conversation
        typing_users: dict[int, list[int]] = {}
        for conv_id in conversation_ids:
            typing = PresenceService.get_typing_users(
                conv_id,
                self._get_conversation_member_ids(conv_id, exclude_user=user),
            )
            if typing:
                typing_users[conv_id] = typing

        # Update presence
        PresenceService.heartbeat(user.id)

        return {
            "unread_counts": unread_counts,
            "typing_users": typing_users,
            "timestamp": timezone.now().isoformat(),
        }

    def poll_typing(
        self,
        request: HttpRequest,
        conversation_id: int,
    ) -> dict:
        """
        Poll for typing indicators in a conversation.

        Lightweight endpoint for frequent polling of typing status.
        """
        conversation = self._get_conversation(conversation_id, request.user)

        # Get other members
        member_ids = self._get_conversation_member_ids(
            conversation_id,
            exclude_user=request.user,
        )

        typing_users = PresenceService.get_typing_users(conversation_id, member_ids)

        return {
            "conversation_id": conversation_id,
            "typing_user_ids": typing_users,
            "timestamp": timezone.now().isoformat(),
        }

    def poll_presence(
        self,
        request: HttpRequest,
    ) -> dict:
        """
        Poll for online status of users.

        Query params:
        - user_ids: Comma-separated list of user IDs to check
        - conversation_id: Get presence for all members of a conversation
        """
        user_ids_param = request.GET.get("user_ids", "")
        conversation_id = request.GET.get("conversation_id")

        if conversation_id:
            conv_id = int(conversation_id)
            self._get_conversation(conv_id, request.user)
            user_ids = self._get_conversation_member_ids(conv_id)
        elif user_ids_param:
            user_ids = [int(x) for x in user_ids_param.split(",") if x.isdigit()]
        else:
            user_ids = []

        presence_info = PresenceService.get_presence_info(
            user_ids,
            conversation_id=int(conversation_id) if conversation_id else None,
        )

        return {
            "presence": presence_info,
            "timestamp": timezone.now().isoformat(),
        }

    def send_typing(
        self,
        request: HttpRequest,
        conversation_id: int,
    ) -> dict:
        """
        Send typing indicator.

        Called when user starts typing. Automatically expires after 5 seconds.
        """
        conversation = self._get_conversation(conversation_id, request.user)

        PresenceService.set_typing(conversation.id, request.user.id)

        return {
            "success": True,
            "expires_in": PresenceService.TYPING_TIMEOUT,
        }

    def clear_typing(
        self,
        request: HttpRequest,
        conversation_id: int,
    ) -> dict:
        """
        Clear typing indicator.

        Called when user stops typing or sends a message.
        """
        conversation = self._get_conversation(conversation_id, request.user)

        PresenceService.clear_typing(conversation.id, request.user.id)

        return {"success": True}

    def heartbeat(
        self,
        request: HttpRequest,
    ) -> dict:
        """
        Send heartbeat to maintain online status.

        Should be called every 30-60 seconds while user is active.

        Query params:
        - conversation_id: Optional current conversation for typing context
        """
        conversation_id = request.GET.get("conversation_id")

        PresenceService.heartbeat(
            request.user.id,
            int(conversation_id) if conversation_id else None,
        )

        return {
            "success": True,
            "online_timeout": PresenceService.ONLINE_TIMEOUT,
            "timestamp": timezone.now().isoformat(),
        }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_conversation(self, conversation_id: int, user) -> Conversation:
        """Get conversation and verify membership."""
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            raise NotFoundAPIError("Conversation not found", resource_type="Conversation")

        if not conversation.is_member(user):
            raise PermissionDeniedAPIError("You are not a member of this conversation")

        return conversation

    def _get_conversation_member_ids(
        self,
        conversation_id: int,
        exclude_user=None,
    ) -> list[int]:
        """Get member IDs for a conversation."""
        from django_matt.messaging.models import ConversationMember

        qs = ConversationMember.objects.filter(
            conversation_id=conversation_id,
            is_active=True,
        ).values_list("user_id", flat=True)

        if exclude_user:
            qs = qs.exclude(user=exclude_user)

        return list(qs)

    def _message_to_dict(self, message: Message) -> dict:
        """Convert message to dictionary."""
        attachments = [
            {
                "id": a.id,
                "filename": a.filename,
                "content_type": a.content_type,
                "file_size": a.file_size,
                "url": a.url,
            }
            for a in message.attachments.all()
        ]

        reactions = list(message.get_reactions_summary())

        return {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "message_type": message.message_type,
            "reply_to_id": message.reply_to_id,
            "created_at": message.created_at.isoformat(),
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "is_pinned": message.is_pinned,
            "is_edited": message.is_edited,
            "attachments": attachments,
            "reactions": reactions,
        }

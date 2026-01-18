"""
Message controller.

REST API endpoints for message operations.
"""

from __future__ import annotations

from django.http import HttpRequest

from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionDeniedAPIError
from django_matt.messaging.models import Conversation, Message
from django_matt.messaging.schemas import (
    EditMessageSchema,
    MessageDetailSchema,
    MessageSchema,
    PaginatedMessagesSchema,
    PresenceSchema,
    PresenceUpdateSchema,
    ReactionSchema,
    ReadReceiptSchema,
    SearchMessagesSchema,
    SearchResultSchema,
    SendMessageSchema,
    TypingIndicatorSchema,
)
from django_matt.messaging.services import MessageService, PresenceService
from django_matt.permissions import IsAuthenticated


class MessageController(APIController):
    """Controller for message operations."""

    tags = ["Messaging"]
    permission_classes = [IsAuthenticated]

    def list(
        self,
        request: HttpRequest,
        conversation_id: int,
    ) -> PaginatedMessagesSchema:
        """Get messages for a conversation."""
        conversation = self._get_conversation(conversation_id, request.user)

        cursor = request.GET.get("cursor")
        if cursor:
            cursor = int(cursor)

        limit = int(request.GET.get("limit", 50))
        limit = min(limit, 100)

        messages = MessageService.get_messages(
            conversation,
            request.user,
            cursor=cursor,
            limit=limit + 1,  # Get one extra to check if there are more
        )

        messages_list = list(messages)
        has_more = len(messages_list) > limit

        if has_more:
            messages_list = messages_list[:limit]

        next_cursor = messages_list[-1].id if messages_list and has_more else None

        return PaginatedMessagesSchema(
            messages=[self._message_to_schema(m) for m in messages_list],
            has_more=has_more,
            next_cursor=next_cursor,
        )

    def get(
        self,
        request: HttpRequest,
        message_id: int,
    ) -> MessageDetailSchema:
        """Get a specific message with full details."""
        message = self._get_message(message_id, request.user)

        edit_history = [
            {
                "previous_content": edit.previous_content,
                "edited_by_id": edit.edited_by_id,
                "edited_at": edit.edited_at,
            }
            for edit in message.edit_history.all()
        ]

        schema = self._message_to_schema(message)
        return MessageDetailSchema(
            **schema.model_dump(),
            edit_history=edit_history,
        )

    def send(
        self,
        request: HttpRequest,
        conversation_id: int,
        data: SendMessageSchema,
    ) -> MessageSchema:
        """Send a message to a conversation."""
        conversation = self._get_conversation(conversation_id, request.user)

        reply_to = None
        if data.reply_to_id:
            try:
                reply_to = Message.objects.get(
                    id=data.reply_to_id,
                    conversation=conversation,
                )
            except Message.DoesNotExist:
                raise NotFoundAPIError("Reply target not found", resource_type="Message")

        try:
            message = MessageService.send_message(
                conversation=conversation,
                sender=request.user,
                content=data.content,
                message_type=data.message_type,
                reply_to=reply_to,
                metadata=data.metadata,
            )
        except PermissionError as e:
            raise PermissionDeniedAPIError(str(e))

        # Clear typing indicator
        PresenceService.clear_typing(conversation_id, request.user.id)

        return self._message_to_schema(message)

    def edit(
        self,
        request: HttpRequest,
        message_id: int,
        data: EditMessageSchema,
    ) -> MessageSchema:
        """Edit a message."""
        message = self._get_message(message_id, request.user)

        try:
            message = MessageService.edit_message(message, data.content, request.user)
        except (PermissionError, ValueError) as e:
            raise PermissionDeniedAPIError(str(e))

        return self._message_to_schema(message)

    def delete(
        self,
        request: HttpRequest,
        message_id: int,
    ) -> dict[str, bool]:
        """Delete a message."""
        message = self._get_message(message_id, request.user)

        try:
            MessageService.delete_message(message, request.user)
        except PermissionError as e:
            raise PermissionDeniedAPIError(str(e))

        return {"success": True}

    def pin(
        self,
        request: HttpRequest,
        message_id: int,
    ) -> MessageSchema:
        """Pin a message."""
        message = self._get_message(message_id, request.user)

        try:
            message = MessageService.pin_message(message, request.user)
        except PermissionError as e:
            raise PermissionDeniedAPIError(str(e))

        return self._message_to_schema(message)

    def unpin(
        self,
        request: HttpRequest,
        message_id: int,
    ) -> MessageSchema:
        """Unpin a message."""
        message = self._get_message(message_id, request.user)

        try:
            message = MessageService.unpin_message(message, request.user)
        except PermissionError as e:
            raise PermissionDeniedAPIError(str(e))

        return self._message_to_schema(message)

    def add_reaction(
        self,
        request: HttpRequest,
        message_id: int,
        data: ReactionSchema,
    ) -> dict[str, bool]:
        """Add a reaction to a message."""
        message = self._get_message(message_id, request.user)

        try:
            _, created = MessageService.add_reaction(message, request.user, data.emoji)
        except PermissionError as e:
            raise PermissionDeniedAPIError(str(e))

        return {"success": True, "created": created}

    def remove_reaction(
        self,
        request: HttpRequest,
        message_id: int,
        data: ReactionSchema,
    ) -> dict[str, bool]:
        """Remove a reaction from a message."""
        message = self._get_message(message_id, request.user)
        removed = MessageService.remove_reaction(message, request.user, data.emoji)
        return {"success": removed}

    def mark_read(
        self,
        request: HttpRequest,
        conversation_id: int,
        data: ReadReceiptSchema,
    ) -> dict[str, bool]:
        """Mark messages as read."""
        conversation = self._get_conversation(conversation_id, request.user)

        up_to_message = None
        if data.up_to_message_id:
            try:
                up_to_message = Message.objects.get(
                    id=data.up_to_message_id,
                    conversation=conversation,
                )
            except Message.DoesNotExist:
                pass

        MessageService.mark_as_read(conversation, request.user, up_to_message)
        return {"success": True}

    def get_pinned(
        self,
        request: HttpRequest,
        conversation_id: int,
    ) -> list[MessageSchema]:
        """Get pinned messages in a conversation."""
        conversation = self._get_conversation(conversation_id, request.user)

        try:
            messages = MessageService.get_pinned_messages(conversation, request.user)
        except PermissionError as e:
            raise PermissionDeniedAPIError(str(e))

        return [self._message_to_schema(m) for m in messages]

    def search(
        self,
        request: HttpRequest,
        data: SearchMessagesSchema,
    ) -> SearchResultSchema:
        """Search messages."""
        conversation = None
        if data.conversation_id:
            conversation = self._get_conversation(data.conversation_id, request.user)

        messages = MessageService.search_messages(
            request.user,
            data.query,
            conversation=conversation,
            limit=data.limit,
        )

        return SearchResultSchema(
            messages=[self._message_to_schema(m) for m in messages],
            total=len(messages),
        )

    def typing(
        self,
        request: HttpRequest,
        conversation_id: int,
    ) -> TypingIndicatorSchema:
        """Send typing indicator."""
        conversation = self._get_conversation(conversation_id, request.user)
        PresenceService.set_typing(conversation.id, request.user.id)

        return TypingIndicatorSchema(
            conversation_id=conversation.id,
            user_id=request.user.id,
            is_typing=True,
        )

    def presence(
        self,
        request: HttpRequest,
        data: PresenceUpdateSchema,
    ) -> PresenceSchema:
        """Update presence/heartbeat."""
        PresenceService.heartbeat(request.user.id, data.conversation_id)

        is_typing = False
        if data.conversation_id:
            is_typing = PresenceService.is_typing(data.conversation_id, request.user.id)

        return PresenceSchema(
            user_id=request.user.id,
            online=True,
            typing=is_typing,
        )

    def get_unread_counts(self, request: HttpRequest) -> dict[int, int]:
        """Get unread message counts per conversation."""
        return MessageService.get_unread_counts(request.user)

    def _get_conversation(self, conversation_id: int, user) -> Conversation:
        """Get conversation and verify membership."""
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            raise NotFoundAPIError("Conversation not found", resource_type="Conversation")

        if not conversation.is_member(user):
            raise PermissionDeniedAPIError("You are not a member of this conversation")

        return conversation

    def _get_message(self, message_id: int, user) -> Message:
        """Get message and verify access."""
        try:
            message = (
                Message.objects.select_related("conversation", "sender")
                .prefetch_related("attachments", "reactions")
                .get(id=message_id)
            )
        except Message.DoesNotExist:
            raise NotFoundAPIError("Message not found", resource_type="Message")

        if not message.conversation.is_member(user):
            raise PermissionDeniedAPIError("You are not a member of this conversation")

        return message

    def _message_to_schema(self, message: Message) -> MessageSchema:
        """Convert message to schema."""
        attachments = [
            {
                "id": a.id,
                "filename": a.filename,
                "original_filename": a.original_filename,
                "content_type": a.content_type,
                "attachment_type": a.attachment_type,
                "file_size": a.file_size,
                "url": a.url,
                "thumbnail_url": a.thumbnail_url,
                "width": a.width,
                "height": a.height,
                "duration": a.duration,
            }
            for a in message.attachments.all()
        ]

        reactions = list(message.get_reactions_summary())

        return MessageSchema(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            content=message.content,
            message_type=message.message_type,
            reply_to_id=message.reply_to_id,
            forwarded_from_id=message.forwarded_from_id,
            created_at=message.created_at,
            edited_at=message.edited_at,
            is_pinned=message.is_pinned,
            is_edited=message.is_edited,
            attachments=attachments,
            reactions=reactions,
        )

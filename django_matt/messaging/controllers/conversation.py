"""
Conversation controller.

REST API endpoints for conversation management.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionDeniedAPIError
from django_matt.messaging.enums import MemberRole
from django_matt.messaging.models import Conversation, ConversationMember
from django_matt.messaging.schemas import (
    AddMembersSchema,
    ConversationDetailSchema,
    ConversationListSchema,
    ConversationSchema,
    ConversationSettingsSchema,
    CreateDirectConversationSchema,
    CreateGroupConversationSchema,
    UpdateConversationSchema,
    UpdateMemberRoleSchema,
)
from django_matt.messaging.services import ConversationService
from django_matt.permissions import IsAuthenticated

User = get_user_model()


class ConversationController(APIController):
    """Controller for conversation operations."""

    tags = ["Messaging"]
    permission_classes = [IsAuthenticated]

    def list(self, request: HttpRequest) -> list[ConversationListSchema]:
        """List user's conversations."""
        include_archived = request.GET.get("archived", "false").lower() == "true"

        conversations = ConversationService.get_user_conversations(
            request.user,
            include_archived=include_archived,
        )

        result = []
        for conv in conversations:
            _, unread_count = ConversationService.get_conversation_with_unread_count(
                conv, request.user
            )
            result.append(
                ConversationListSchema(
                    id=conv.id,
                    name=conv.name or self._get_display_name(conv, request.user),
                    avatar=conv.avatar,
                    conversation_type=conv.conversation_type,
                    last_message_at=conv.last_message_at,
                    last_message_preview=conv.last_message_preview,
                    unread_count=unread_count,
                    member_count=conv.member_count,
                )
            )
        return result

    def _get_display_name(self, conversation: Conversation, current_user) -> str:
        """Get display name for a conversation."""
        if conversation.name:
            return conversation.name

        # For direct conversations, show the other user's name
        other_members = conversation.members.exclude(user=current_user).select_related("user")[:1]
        if other_members:
            user = other_members[0].user
            return user.get_full_name() or user.email
        return f"Conversation #{conversation.id}"

    def get(self, request: HttpRequest, conversation_id: int) -> ConversationDetailSchema:
        """Get conversation details."""
        conversation = self._get_conversation(conversation_id, request.user)

        members = [
            {
                "id": m.id,
                "user_id": m.user_id,
                "role": m.role,
                "joined_at": m.joined_at,
                "nickname": m.nickname,
            }
            for m in conversation.get_members()
        ]

        return ConversationDetailSchema(
            id=conversation.id,
            name=conversation.name,
            description=conversation.description,
            avatar=conversation.avatar,
            conversation_type=conversation.conversation_type,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_message_at=conversation.last_message_at,
            last_message_preview=conversation.last_message_preview,
            is_archived=conversation.is_archived,
            is_locked=conversation.is_locked,
            members=members,
        )

    def create_direct(
        self,
        request: HttpRequest,
        data: CreateDirectConversationSchema,
    ) -> ConversationSchema:
        """Create or get a direct conversation."""
        try:
            other_user = User.objects.get(id=data.user_id)
        except User.DoesNotExist:
            raise NotFoundAPIError("User not found", resource_type="User")

        conversation, _ = ConversationService.create_direct_conversation(request.user, other_user)

        return ConversationSchema.model_validate(conversation)

    def create_group(
        self,
        request: HttpRequest,
        data: CreateGroupConversationSchema,
    ) -> ConversationSchema:
        """Create a group conversation."""
        members = list(User.objects.filter(id__in=data.member_ids))

        conversation = ConversationService.create_group_conversation(
            name=data.name,
            creator=request.user,
            members=members,
            description=data.description,
            avatar=data.avatar,
        )

        return ConversationSchema.model_validate(conversation)

    def update(
        self,
        request: HttpRequest,
        conversation_id: int,
        data: UpdateConversationSchema,
    ) -> ConversationSchema:
        """Update conversation details."""
        conversation = self._get_conversation(conversation_id, request.user)
        membership = self._get_membership(conversation, request.user)

        if not membership.can_manage_members():
            raise PermissionDeniedAPIError("Only admins can update conversation details")

        # Update fields
        update_fields = []
        if data.name is not None:
            conversation.name = data.name
            update_fields.append("name")
        if data.description is not None:
            conversation.description = data.description
            update_fields.append("description")
        if data.avatar is not None:
            conversation.avatar = data.avatar
            update_fields.append("avatar")

        if update_fields:
            update_fields.append("updated_at")
            conversation.save(update_fields=update_fields)

        return ConversationSchema.model_validate(conversation)

    def delete(self, request: HttpRequest, conversation_id: int) -> dict[str, bool]:
        """Delete/archive a conversation."""
        conversation = self._get_conversation(conversation_id, request.user)
        membership = self._get_membership(conversation, request.user)

        if membership.role != MemberRole.OWNER:
            raise PermissionDeniedAPIError("Only the owner can delete a conversation")

        ConversationService.delete_conversation(conversation, request.user)
        return {"success": True}

    def add_members(
        self,
        request: HttpRequest,
        conversation_id: int,
        data: AddMembersSchema,
    ) -> dict[str, Any]:
        """Add members to a conversation."""
        conversation = self._get_conversation(conversation_id, request.user)
        membership = self._get_membership(conversation, request.user)

        if not membership.can_manage_members():
            raise PermissionDeniedAPIError("Only admins can add members")

        users = list(User.objects.filter(id__in=data.user_ids))
        role = MemberRole(data.role)

        added = ConversationService.add_members(
            conversation, users, added_by=request.user, role=role
        )

        return {"added_count": len(added)}

    def remove_member(
        self,
        request: HttpRequest,
        conversation_id: int,
        user_id: int,
    ) -> dict[str, bool]:
        """Remove a member from a conversation."""
        conversation = self._get_conversation(conversation_id, request.user)
        membership = self._get_membership(conversation, request.user)

        # Users can remove themselves (leave)
        if user_id != request.user.id and not membership.can_manage_members():
            raise PermissionDeniedAPIError("Only admins can remove members")

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFoundAPIError("User not found", resource_type="User")

        success = ConversationService.remove_member(
            conversation, target_user, removed_by=request.user
        )
        return {"success": success}

    def update_member_role(
        self,
        request: HttpRequest,
        conversation_id: int,
        user_id: int,
        data: UpdateMemberRoleSchema,
    ) -> dict[str, bool]:
        """Update a member's role."""
        conversation = self._get_conversation(conversation_id, request.user)
        membership = self._get_membership(conversation, request.user)

        if membership.role != MemberRole.OWNER:
            raise PermissionDeniedAPIError("Only the owner can change roles")

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFoundAPIError("User not found", resource_type="User")

        member = ConversationService.update_member_role(
            conversation, target_user, MemberRole(data.role), request.user
        )

        return {"success": member is not None}

    def update_settings(
        self,
        request: HttpRequest,
        conversation_id: int,
        data: ConversationSettingsSchema,
    ) -> ConversationSettingsSchema:
        """Update conversation settings for the current user."""
        conversation = self._get_conversation(conversation_id, request.user)
        membership = self._get_membership(conversation, request.user)

        settings = ConversationService.update_settings(
            membership,
            is_muted=data.is_muted,
            is_pinned=data.is_pinned,
            is_archived=data.is_archived,
            show_notifications=data.show_notifications,
        )

        return ConversationSettingsSchema(
            is_muted=settings.is_muted,
            is_pinned=settings.is_pinned,
            is_archived=settings.is_archived,
            show_notifications=settings.show_notifications,
        )

    def leave(self, request: HttpRequest, conversation_id: int) -> dict[str, bool]:
        """Leave a conversation."""
        conversation = self._get_conversation(conversation_id, request.user)
        success = ConversationService.leave_conversation(conversation, request.user)
        return {"success": success}

    def _get_conversation(self, conversation_id: int, user) -> Conversation:
        """Get conversation and verify membership."""
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            raise NotFoundAPIError("Conversation not found", resource_type="Conversation")

        if not conversation.is_member(user):
            raise PermissionDeniedAPIError("You are not a member of this conversation")

        return conversation

    def _get_membership(self, conversation: Conversation, user) -> ConversationMember:
        """Get user's membership in a conversation."""
        try:
            return ConversationMember.objects.get(
                conversation=conversation,
                user=user,
                is_active=True,
            )
        except ConversationMember.DoesNotExist:
            raise PermissionDeniedAPIError("You are not a member of this conversation")

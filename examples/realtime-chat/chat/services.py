"""
Business logic services for the chat application.

Services handle the core business logic, keeping controllers thin.
"""

import re
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    Channel,
    ChannelMembership,
    DirectMessageThread,
    FileAttachment,
    Message,
    Reaction,
    ReadReceipt,
    UserProfile,
    Workspace,
    WorkspaceMembership,
)
from .schemas import (
    ChannelResponse,
    MessageResponse,
    ReactionSchema,
    UserBrief,
    WorkspaceResponse,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import User

User = get_user_model()


# =============================================================================
# User Service
# =============================================================================


class UserService:
    """Service for user-related operations."""

    @staticmethod
    async def get_or_create_profile(user: "User") -> UserProfile:
        """Get or create user profile."""
        profile, _ = await sync_to_async(
            UserProfile.objects.get_or_create,
            thread_sensitive=True,
        )(user=user, defaults={"display_name": user.username})
        return profile

    @staticmethod
    async def update_presence(user: "User", status: str) -> UserProfile:
        """Update user presence status."""
        profile = await UserService.get_or_create_profile(user)
        profile.status = status
        profile.last_seen = timezone.now()
        await sync_to_async(profile.save, thread_sensitive=True)()
        return profile

    @staticmethod
    def to_brief(user: "User", profile: UserProfile | None = None) -> UserBrief:
        """Convert user to brief schema."""
        return UserBrief(
            id=user.id,
            username=user.username,
            display_name=profile.display_name if profile else None,
            avatar_url=profile.avatar_url if profile else None,
            status=profile.status if profile else "offline",
        )


# =============================================================================
# Workspace Service
# =============================================================================


class WorkspaceService:
    """Service for workspace operations."""

    @staticmethod
    async def create(user: "User", name: str, slug: str, description: str = "") -> Workspace:
        """Create a new workspace."""

        @sync_to_async
        def _create():
            with transaction.atomic():
                workspace = Workspace.objects.create(
                    name=name,
                    slug=slug,
                    description=description,
                    owner=user,
                )
                # Add owner as member with owner role
                WorkspaceMembership.objects.create(
                    workspace=workspace,
                    user=user,
                    role="owner",
                )
                # Create default #general channel
                Channel.objects.create(
                    workspace=workspace,
                    name="general",
                    slug="general",
                    description="General discussion",
                    created_by=user,
                )
                return workspace

        return await _create()

    @staticmethod
    async def get_user_workspaces(user: "User") -> list[Workspace]:
        """Get all workspaces user is a member of."""
        return await sync_to_async(
            lambda: list(
                Workspace.objects.filter(memberships__user=user)
                .annotate(
                    member_count=Count("memberships"),
                    channel_count=Count("channels"),
                )
                .order_by("name")
            ),
            thread_sensitive=True,
        )()

    @staticmethod
    async def get_workspace(workspace_id: UUID, user: "User" | None = None) -> Workspace | None:
        """Get workspace by ID, optionally checking membership."""

        @sync_to_async
        def _get():
            qs = Workspace.objects.annotate(
                member_count=Count("memberships"),
                channel_count=Count("channels"),
            )
            if user:
                qs = qs.filter(memberships__user=user)
            return qs.filter(id=workspace_id).first()

        return await _get()

    @staticmethod
    async def add_member(
        workspace: Workspace,
        user: "User",
        role: str = "member",
        invited_by: "User" | None = None,
    ) -> WorkspaceMembership:
        """Add a member to workspace."""
        membership, _ = await sync_to_async(
            WorkspaceMembership.objects.get_or_create,
            thread_sensitive=True,
        )(
            workspace=workspace,
            user=user,
            defaults={"role": role, "invited_by": invited_by},
        )
        return membership

    @staticmethod
    def to_response(workspace: Workspace) -> WorkspaceResponse:
        """Convert workspace to response schema."""
        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            description=workspace.description,
            icon_url=workspace.icon_url,
            owner_id=workspace.owner_id,
            member_count=getattr(workspace, "member_count", 0),
            channel_count=getattr(workspace, "channel_count", 0),
            created_at=workspace.created_at,
        )


# =============================================================================
# Channel Service
# =============================================================================


class ChannelService:
    """Service for channel operations."""

    @staticmethod
    async def create(
        workspace: Workspace,
        user: "User",
        name: str,
        description: str = "",
        is_private: bool = False,
    ) -> Channel:
        """Create a new channel."""
        slug = slugify(name)

        @sync_to_async
        def _create():
            with transaction.atomic():
                # Ensure unique slug in workspace
                base_slug = slug
                counter = 1
                final_slug = base_slug
                while Channel.objects.filter(workspace=workspace, slug=final_slug).exists():
                    final_slug = f"{base_slug}-{counter}"
                    counter += 1

                channel = Channel.objects.create(
                    workspace=workspace,
                    name=name,
                    slug=final_slug,
                    description=description,
                    is_private=is_private,
                    created_by=user,
                )
                # Add creator as member
                ChannelMembership.objects.create(
                    channel=channel,
                    user=user,
                )
                return channel

        return await _create()

    @staticmethod
    async def get_workspace_channels(
        workspace: Workspace, user: "User", include_private: bool = False
    ) -> list[Channel]:
        """Get channels in workspace visible to user."""

        @sync_to_async
        def _get():
            qs = Channel.objects.filter(workspace=workspace, is_archived=False)

            if not include_private:
                # Show public channels + private channels user is member of
                qs = qs.filter(
                    Q(is_private=False) | Q(memberships__user=user)
                ).distinct()

            return list(
                qs.annotate(member_count=Count("memberships"))
                .select_related("created_by")
                .order_by("name")
            )

        return await _get()

    @staticmethod
    async def get_channel(
        channel_id: UUID, user: "User" | None = None, check_access: bool = True
    ) -> Channel | None:
        """Get channel by ID, optionally checking access."""

        @sync_to_async
        def _get():
            qs = Channel.objects.annotate(member_count=Count("memberships")).select_related(
                "workspace", "created_by"
            )

            channel = qs.filter(id=channel_id).first()
            if not channel:
                return None

            if check_access and user and channel.is_private:
                # Check if user is member of private channel
                if not channel.memberships.filter(user=user).exists():
                    return None

            return channel

        return await _get()

    @staticmethod
    async def add_member(channel: Channel, user: "User") -> ChannelMembership:
        """Add user to channel."""
        membership, _ = await sync_to_async(
            ChannelMembership.objects.get_or_create,
            thread_sensitive=True,
        )(channel=channel, user=user)
        return membership

    @staticmethod
    async def remove_member(channel: Channel, user: "User") -> bool:
        """Remove user from channel."""

        @sync_to_async
        def _remove():
            deleted, _ = ChannelMembership.objects.filter(
                channel=channel, user=user
            ).delete()
            return deleted > 0

        return await _remove()

    @staticmethod
    async def get_members(channel: Channel) -> list[ChannelMembership]:
        """Get all members of a channel."""
        return await sync_to_async(
            lambda: list(
                channel.memberships.select_related("user", "user__chat_profile").order_by(
                    "joined_at"
                )
            ),
            thread_sensitive=True,
        )()

    @staticmethod
    def to_response(channel: Channel) -> ChannelResponse:
        """Convert channel to response schema."""
        created_by = None
        if channel.created_by:
            created_by = UserBrief(
                id=channel.created_by.id,
                username=channel.created_by.username,
                display_name=None,
                avatar_url=None,
                status="offline",
            )

        return ChannelResponse(
            id=channel.id,
            workspace_id=channel.workspace_id,
            name=channel.name,
            slug=channel.slug,
            description=channel.description,
            topic=channel.topic,
            is_private=channel.is_private,
            is_archived=channel.is_archived,
            member_count=getattr(channel, "member_count", 0),
            created_at=channel.created_at,
            created_by=created_by,
        )


# =============================================================================
# Message Service
# =============================================================================


class MessageService:
    """Service for message operations."""

    # Regex for @mentions
    MENTION_PATTERN = re.compile(r"@(\w+)")

    @staticmethod
    async def create(
        user: "User",
        content: str,
        channel: Channel | None = None,
        dm_thread: DirectMessageThread | None = None,
        parent_message_id: UUID | None = None,
        attachment_ids: list[UUID] | None = None,
    ) -> Message:
        """Create a new message."""

        @sync_to_async
        def _create():
            with transaction.atomic():
                # Parse mentions
                mentions_everyone = "@everyone" in content or "@channel" in content
                mention_usernames = MessageService.MENTION_PATTERN.findall(content)

                # Create message
                message = Message.objects.create(
                    channel=channel,
                    dm_thread=dm_thread,
                    author=user,
                    content=content,
                    content_html=MessageService._render_content(content),
                    parent_message_id=parent_message_id,
                    mentions_everyone=mentions_everyone,
                )

                # Add mentioned users
                if mention_usernames:
                    mentioned = User.objects.filter(username__in=mention_usernames)
                    message.mentioned_users.set(mentioned)

                # Attach files
                if attachment_ids:
                    FileAttachment.objects.filter(
                        id__in=attachment_ids,
                        uploaded_by=user,
                        message__isnull=True,
                    ).update(message=message)

                # Update parent message reply count
                if parent_message_id:
                    parent = Message.objects.filter(id=parent_message_id).first()
                    if parent:
                        parent.reply_count = parent.replies.count()
                        parent.reply_users_count = (
                            parent.replies.values("author").distinct().count()
                        )
                        parent.save(update_fields=["reply_count", "reply_users_count"])

                # Update DM thread timestamp
                if dm_thread:
                    dm_thread.updated_at = timezone.now()
                    dm_thread.save(update_fields=["updated_at"])

                return message

        return await _create()

    @staticmethod
    def _render_content(content: str) -> str:
        """Render message content to HTML with mentions, links, etc."""
        import html

        # Escape HTML
        rendered = html.escape(content)

        # Convert @mentions to spans
        rendered = re.sub(
            r"@(\w+)",
            r'<span class="mention" data-username="\1">@\1</span>',
            rendered,
        )

        # Convert URLs to links
        url_pattern = r"(https?://[^\s<]+)"
        rendered = re.sub(
            url_pattern,
            r'<a href="\1" target="_blank" rel="noopener">\1</a>',
            rendered,
        )

        # Convert newlines to <br>
        rendered = rendered.replace("\n", "<br>")

        return rendered

    @staticmethod
    async def get_channel_messages(
        channel: Channel,
        limit: int = 50,
        before: datetime | None = None,
        after: datetime | None = None,
    ) -> list[Message]:
        """Get messages from a channel."""

        @sync_to_async
        def _get():
            qs = Message.objects.filter(
                channel=channel,
                is_deleted=False,
                parent_message__isnull=True,  # Exclude thread replies
            ).select_related("author")

            if before:
                qs = qs.filter(created_at__lt=before)
            if after:
                qs = qs.filter(created_at__gt=after)

            # Prefetch reactions and attachments
            qs = qs.prefetch_related(
                Prefetch(
                    "reactions",
                    queryset=Reaction.objects.select_related("user"),
                ),
                "attachments",
                "mentioned_users",
            )

            return list(qs.order_by("-created_at")[:limit])

        messages = await _get()
        return list(reversed(messages))  # Return in chronological order

    @staticmethod
    async def get_message(message_id: UUID) -> Message | None:
        """Get a single message by ID."""

        @sync_to_async
        def _get():
            return (
                Message.objects.filter(id=message_id, is_deleted=False)
                .select_related("author", "channel", "dm_thread")
                .prefetch_related(
                    Prefetch(
                        "reactions",
                        queryset=Reaction.objects.select_related("user"),
                    ),
                    "attachments",
                    "mentioned_users",
                )
                .first()
            )

        return await _get()

    @staticmethod
    async def update(message: Message, content: str) -> Message:
        """Update a message."""

        @sync_to_async
        def _update():
            message.content = content
            message.content_html = MessageService._render_content(content)
            message.is_edited = True
            message.edited_at = timezone.now()
            message.save()

            # Update mentions
            mention_usernames = MessageService.MENTION_PATTERN.findall(content)
            mentioned = User.objects.filter(username__in=mention_usernames)
            message.mentioned_users.set(mentioned)

            return message

        return await _update()

    @staticmethod
    async def delete(message: Message) -> None:
        """Soft delete a message."""

        @sync_to_async
        def _delete():
            message.soft_delete()

        await _delete()

    @staticmethod
    async def get_thread(parent_message: Message) -> list[Message]:
        """Get all replies to a message."""
        return await sync_to_async(
            lambda: list(
                parent_message.replies.filter(is_deleted=False)
                .select_related("author")
                .prefetch_related("reactions", "attachments", "mentioned_users")
                .order_by("created_at")
            ),
            thread_sensitive=True,
        )()

    @staticmethod
    def to_response(message: Message, current_user: "User" | None = None) -> MessageResponse:
        """Convert message to response schema."""
        author = None
        if message.author:
            author = UserBrief(
                id=message.author.id,
                username=message.author.username,
                display_name=None,
                avatar_url=None,
                status="offline",
            )

        # Group reactions by emoji
        reactions_by_emoji: dict[str, list] = {}
        for reaction in message.reactions.all():
            if reaction.emoji not in reactions_by_emoji:
                reactions_by_emoji[reaction.emoji] = []
            reactions_by_emoji[reaction.emoji].append(reaction)

        reactions = []
        for emoji, emoji_reactions in reactions_by_emoji.items():
            users = [
                UserBrief(
                    id=r.user.id,
                    username=r.user.username,
                    display_name=None,
                    avatar_url=None,
                    status="offline",
                )
                for r in emoji_reactions[:5]  # Limit users shown
            ]
            reactions.append(
                ReactionSchema(
                    emoji=emoji,
                    count=len(emoji_reactions),
                    users=users,
                    reacted_by_me=current_user
                    and any(r.user_id == current_user.id for r in emoji_reactions),
                )
            )

        mentioned_users = [
            UserBrief(
                id=u.id,
                username=u.username,
                display_name=None,
                avatar_url=None,
                status="offline",
            )
            for u in message.mentioned_users.all()
        ]

        return MessageResponse(
            id=message.id,
            channel_id=message.channel_id,
            dm_thread_id=message.dm_thread_id,
            author=author,
            content=message.content,
            content_html=message.content_html,
            parent_message_id=message.parent_message_id,
            reply_count=message.reply_count,
            reply_users_count=message.reply_users_count,
            reactions=reactions,
            attachments=[],  # TODO: Add attachments
            mentioned_users=mentioned_users,
            is_edited=message.is_edited,
            edited_at=message.edited_at,
            created_at=message.created_at,
        )


# =============================================================================
# Reaction Service
# =============================================================================


class ReactionService:
    """Service for reaction operations."""

    @staticmethod
    async def add(message: Message, user: "User", emoji: str) -> Reaction | None:
        """Add a reaction to a message."""
        reaction, created = await sync_to_async(
            Reaction.objects.get_or_create,
            thread_sensitive=True,
        )(message=message, user=user, emoji=emoji)
        return reaction if created else None

    @staticmethod
    async def remove(message: Message, user: "User", emoji: str) -> bool:
        """Remove a reaction from a message."""

        @sync_to_async
        def _remove():
            deleted, _ = Reaction.objects.filter(
                message=message, user=user, emoji=emoji
            ).delete()
            return deleted > 0

        return await _remove()


# =============================================================================
# Direct Message Service
# =============================================================================


class DirectMessageService:
    """Service for direct message operations."""

    @staticmethod
    async def get_or_create_thread(
        workspace: Workspace, participants: list["User"]
    ) -> DirectMessageThread:
        """Get or create a DM thread between participants."""

        @sync_to_async
        def _get_or_create():
            # Try to find existing thread with exact participants
            participant_ids = sorted(u.id for u in participants)

            # This query finds threads that have all and only the specified participants
            for thread in DirectMessageThread.objects.filter(workspace=workspace):
                thread_participant_ids = sorted(
                    thread.participants.values_list("id", flat=True)
                )
                if thread_participant_ids == participant_ids:
                    return thread

            # Create new thread
            thread = DirectMessageThread.objects.create(workspace=workspace)
            thread.participants.set(participants)
            return thread

        return await _get_or_create()

    @staticmethod
    async def get_user_threads(
        workspace: Workspace, user: "User"
    ) -> list[DirectMessageThread]:
        """Get all DM threads for a user in a workspace."""
        return await sync_to_async(
            lambda: list(
                DirectMessageThread.objects.filter(
                    workspace=workspace,
                    participants=user,
                )
                .prefetch_related("participants")
                .order_by("-updated_at")
            ),
            thread_sensitive=True,
        )()


# =============================================================================
# Read Receipt Service
# =============================================================================


class ReadReceiptService:
    """Service for read receipt operations."""

    @staticmethod
    async def mark_read(
        user: "User",
        message: Message,
        channel: Channel | None = None,
        dm_thread: DirectMessageThread | None = None,
    ) -> ReadReceipt:
        """Mark messages as read up to a specific message."""

        @sync_to_async
        def _mark():
            receipt, _ = ReadReceipt.objects.update_or_create(
                user=user,
                channel=channel,
                dm_thread=dm_thread,
                defaults={
                    "last_read_message": message,
                    "last_read_at": timezone.now(),
                },
            )
            return receipt

        return await _mark()

    @staticmethod
    async def get_unread_count(
        user: "User",
        channel: Channel | None = None,
        dm_thread: DirectMessageThread | None = None,
    ) -> int:
        """Get count of unread messages."""

        @sync_to_async
        def _count():
            receipt = ReadReceipt.objects.filter(
                user=user,
                channel=channel,
                dm_thread=dm_thread,
            ).first()

            qs = Message.objects.filter(is_deleted=False)
            if channel:
                qs = qs.filter(channel=channel)
            elif dm_thread:
                qs = qs.filter(dm_thread=dm_thread)
            else:
                return 0

            if receipt and receipt.last_read_message:
                qs = qs.filter(created_at__gt=receipt.last_read_message.created_at)

            # Exclude user's own messages
            qs = qs.exclude(author=user)

            return qs.count()

        return await _count()


# =============================================================================
# Search Service
# =============================================================================


class SearchService:
    """Service for message search."""

    @staticmethod
    async def search_messages(
        query: str,
        user: "User",
        workspace_id: UUID | None = None,
        channel_id: UUID | None = None,
        from_user_id: int | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Message], int]:
        """Search messages with filters."""

        @sync_to_async
        def _search():
            # Base query - search in content
            qs = Message.objects.filter(
                is_deleted=False,
                content__icontains=query,
            ).select_related("author", "channel", "channel__workspace")

            # Filter by workspace access
            if workspace_id:
                qs = qs.filter(channel__workspace_id=workspace_id)

            # User must have access to the channel
            qs = qs.filter(
                Q(channel__is_private=False)
                | Q(channel__memberships__user=user)
                | Q(dm_thread__participants=user)
            ).distinct()

            # Additional filters
            if channel_id:
                qs = qs.filter(channel_id=channel_id)
            if from_user_id:
                qs = qs.filter(author_id=from_user_id)
            if after:
                qs = qs.filter(created_at__gt=after)
            if before:
                qs = qs.filter(created_at__lt=before)

            total = qs.count()
            messages = list(qs.order_by("-created_at")[offset : offset + limit])

            return messages, total

        return await _search()

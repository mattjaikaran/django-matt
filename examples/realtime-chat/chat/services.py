"""
Business logic services for the chat application.

Services handle the core business logic, keeping controllers thin.
All ORM calls use native async methods (.aget, .acreate, .acount, etc.).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django.utils.text import slugify

from django_matt.services import BaseService, CRUDService

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


class UserService(BaseService["UserProfile"]):
    """Service for user profile and presence operations."""

    model = UserProfile

    async def get_or_create_profile(self, user: User) -> UserProfile:
        """Get or create user profile."""
        profile, _ = await UserProfile.objects.aget_or_create(
            user=user,
            defaults={"display_name": user.username},
        )
        return profile

    async def update_presence(self, user: User, status: str) -> UserProfile:
        """Update user presence status."""
        profile = await self.get_or_create_profile(user)
        profile.status = status
        profile.last_seen = timezone.now()
        await profile.asave(update_fields=["status", "last_seen"])
        return profile

    @staticmethod
    def to_brief(user: User, profile: UserProfile | None = None) -> UserBrief:
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


class WorkspaceService(CRUDService["Workspace"]):
    """Service for workspace CRUD and membership operations."""

    model = Workspace

    async def create_workspace(
        self,
        user: User,
        name: str,
        slug: str,
        description: str = "",
    ) -> Workspace:
        """Create a new workspace, add owner membership, and seed #general channel."""
        async with transaction.atomic():
            workspace = await Workspace.objects.acreate(
                name=name,
                slug=slug,
                description=description,
                owner=user,
            )
            await WorkspaceMembership.objects.acreate(
                workspace=workspace,
                user=user,
                role="owner",
            )
            await Channel.objects.acreate(
                workspace=workspace,
                name="general",
                slug="general",
                description="General discussion",
                created_by=user,
            )
        return workspace

    async def get_user_workspaces(self, user: User) -> list[Workspace]:
        """Get all workspaces user is a member of."""
        return [
            w
            async for w in Workspace.objects.filter(memberships__user=user)
            .annotate(
                member_count=Count("memberships"),
                channel_count=Count("channels"),
            )
            .order_by("name")
        ]

    async def get_workspace(
        self, workspace_id: UUID, user: User | None = None
    ) -> Workspace | None:
        """Get workspace by ID, optionally scoped to a user's memberships."""
        qs = Workspace.objects.annotate(
            member_count=Count("memberships"),
            channel_count=Count("channels"),
        )
        if user:
            qs = qs.filter(memberships__user=user)
        return await qs.filter(id=workspace_id).afirst()

    async def add_member(
        self,
        workspace: Workspace,
        user: User,
        role: str = "member",
        invited_by: User | None = None,
    ) -> WorkspaceMembership:
        """Add a member to workspace (idempotent)."""
        membership, _ = await WorkspaceMembership.objects.aget_or_create(
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


class ChannelService(CRUDService["Channel"]):
    """Service for channel CRUD and membership management."""

    model = Channel

    async def create_channel(
        self,
        workspace: Workspace,
        user: User,
        name: str,
        description: str = "",
        is_private: bool = False,
    ) -> Channel:
        """Create a new channel with a unique slug and add creator as member."""
        base_slug = slugify(name)
        async with transaction.atomic():
            # Guarantee unique slug within the workspace
            counter = 1
            final_slug = base_slug
            while await Channel.objects.filter(
                workspace=workspace, slug=final_slug
            ).aexists():
                final_slug = f"{base_slug}-{counter}"
                counter += 1

            channel = await Channel.objects.acreate(
                workspace=workspace,
                name=name,
                slug=final_slug,
                description=description,
                is_private=is_private,
                created_by=user,
            )
            await ChannelMembership.objects.acreate(channel=channel, user=user)

        return channel

    async def get_workspace_channels(
        self,
        workspace: Workspace,
        user: User,
        include_private: bool = False,
    ) -> list[Channel]:
        """Get non-archived channels in workspace visible to user."""
        qs = Channel.objects.filter(workspace=workspace, is_archived=False)

        if not include_private:
            qs = qs.filter(
                Q(is_private=False) | Q(memberships__user=user)
            ).distinct()

        return [
            c
            async for c in qs.annotate(member_count=Count("memberships"))
            .select_related("created_by")
            .order_by("name")
        ]

    async def get_channel(
        self,
        channel_id: UUID,
        user: User | None = None,
        check_access: bool = True,
    ) -> Channel | None:
        """Get channel by ID, optionally enforcing private-channel access."""
        qs = Channel.objects.annotate(member_count=Count("memberships")).select_related(
            "workspace", "created_by"
        )
        channel = await qs.filter(id=channel_id).afirst()

        if channel is None:
            return None

        if check_access and user and channel.is_private:
            has_membership = await channel.memberships.filter(user=user).aexists()
            if not has_membership:
                return None

        return channel

    async def add_member(self, channel: Channel, user: User) -> ChannelMembership:
        """Add user to channel (idempotent)."""
        membership, _ = await ChannelMembership.objects.aget_or_create(
            channel=channel, user=user
        )
        return membership

    async def remove_member(self, channel: Channel, user: User) -> bool:
        """Remove user from channel. Returns True if a row was deleted."""
        deleted, _ = await ChannelMembership.objects.filter(
            channel=channel, user=user
        ).adelete()
        return deleted > 0

    async def get_members(self, channel: Channel) -> list[ChannelMembership]:
        """Get all members of a channel."""
        return [
            m
            async for m in channel.memberships.select_related(
                "user", "user__chat_profile"
            ).order_by("joined_at")
        ]

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


class MessageService(CRUDService["Message"]):
    """Service for message CRUD, threading, and content rendering."""

    model = Message

    # Regex for @mentions
    MENTION_PATTERN = re.compile(r"@(\w+)")

    async def create_message(
        self,
        user: User,
        content: str,
        channel: Channel | None = None,
        dm_thread: DirectMessageThread | None = None,
        parent_message_id: UUID | None = None,
        attachment_ids: list[UUID] | None = None,
    ) -> Message:
        """Create a new message with mention parsing, attachments, and thread tracking."""
        async with transaction.atomic():
            mentions_everyone = "@everyone" in content or "@channel" in content
            mention_usernames = self.MENTION_PATTERN.findall(content)

            message = await Message.objects.acreate(
                channel=channel,
                dm_thread=dm_thread,
                author=user,
                content=content,
                content_html=self._render_content(content),
                parent_message_id=parent_message_id,
                mentions_everyone=mentions_everyone,
            )

            if mention_usernames:
                mentioned_qs = User.objects.filter(username__in=mention_usernames)
                await message.mentioned_users.aset(
                    [u async for u in mentioned_qs]
                )

            if attachment_ids:
                await FileAttachment.objects.filter(
                    id__in=attachment_ids,
                    uploaded_by=user,
                    message__isnull=True,
                ).aupdate(message=message)

            if parent_message_id:
                parent = await Message.objects.filter(id=parent_message_id).afirst()
                if parent:
                    parent.reply_count = await parent.replies.acount()
                    parent.reply_users_count = await (
                        parent.replies.values("author").distinct().acount()
                    )
                    await parent.asave(
                        update_fields=["reply_count", "reply_users_count"]
                    )

            if dm_thread:
                dm_thread.updated_at = timezone.now()
                await dm_thread.asave(update_fields=["updated_at"])

        return message

    @staticmethod
    def _render_content(content: str) -> str:
        """Render message content to HTML with mentions, links, and line breaks."""
        import html

        rendered = html.escape(content)
        rendered = re.sub(
            r"@(\w+)",
            r'<span class="mention" data-username="\1">@\1</span>',
            rendered,
        )
        rendered = re.sub(
            r"(https?://[^\s<]+)",
            r'<a href="\1" target="_blank" rel="noopener">\1</a>',
            rendered,
        )
        rendered = rendered.replace("\n", "<br>")
        return rendered

    async def get_channel_messages(
        self,
        channel: Channel,
        limit: int = 50,
        before: datetime | None = None,
        after: datetime | None = None,
    ) -> list[Message]:
        """Get non-deleted top-level messages from a channel in chronological order."""
        qs = Message.objects.filter(
            channel=channel,
            is_deleted=False,
            parent_message__isnull=True,
        ).select_related("author")

        if before:
            qs = qs.filter(created_at__lt=before)
        if after:
            qs = qs.filter(created_at__gt=after)

        qs = qs.prefetch_related(
            Prefetch(
                "reactions",
                queryset=Reaction.objects.select_related("user"),
            ),
            "attachments",
            "mentioned_users",
        )

        messages = [m async for m in qs.order_by("-created_at")[:limit]]
        return list(reversed(messages))  # Chronological order

    async def get_message(self, message_id: UUID) -> Message | None:
        """Get a single non-deleted message by ID with all related data."""
        return await (
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
            .afirst()
        )

    async def update_message(self, message: Message, content: str) -> Message:
        """Edit a message's content and re-parse mentions."""
        message.content = content
        message.content_html = self._render_content(content)
        message.is_edited = True
        message.edited_at = timezone.now()
        await message.asave(
            update_fields=["content", "content_html", "is_edited", "edited_at"]
        )

        mention_usernames = self.MENTION_PATTERN.findall(content)
        mentioned = [u async for u in User.objects.filter(username__in=mention_usernames)]
        await message.mentioned_users.aset(mentioned)

        return message

    async def delete_message(self, message: Message) -> None:
        """Soft-delete a message."""
        message.is_deleted = True
        await message.asave(update_fields=["is_deleted"])

    async def get_thread(self, parent_message: Message) -> list[Message]:
        """Get all non-deleted replies to a message in chronological order."""
        return [
            m
            async for m in parent_message.replies.filter(is_deleted=False)
            .select_related("author")
            .prefetch_related("reactions", "attachments", "mentioned_users")
            .order_by("created_at")
        ]

    @staticmethod
    def to_response(message: Message, current_user: User | None = None) -> MessageResponse:
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
                for r in emoji_reactions[:5]
            ]
            reactions.append(
                ReactionSchema(
                    emoji=emoji,
                    count=len(emoji_reactions),
                    users=users,
                    reacted_by_me=(
                        current_user is not None
                        and any(r.user_id == current_user.id for r in emoji_reactions)
                    ),
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
            attachments=[],
            mentioned_users=mentioned_users,
            is_edited=message.is_edited,
            edited_at=message.edited_at,
            created_at=message.created_at,
        )


# =============================================================================
# Reaction Service
# =============================================================================


class ReactionService(BaseService["Reaction"]):
    """Service for adding and removing message reactions."""

    model = Reaction

    async def add(self, message: Message, user: User, emoji: str) -> Reaction | None:
        """Add a reaction to a message. Returns None if already reacted."""
        reaction, created = await Reaction.objects.aget_or_create(
            message=message, user=user, emoji=emoji
        )
        return reaction if created else None

    async def remove(self, message: Message, user: User, emoji: str) -> bool:
        """Remove a reaction from a message. Returns True if deleted."""
        deleted, _ = await Reaction.objects.filter(
            message=message, user=user, emoji=emoji
        ).adelete()
        return deleted > 0


# =============================================================================
# Direct Message Service
# =============================================================================


class DirectMessageService(BaseService["DirectMessageThread"]):
    """Service for direct message thread management."""

    model = DirectMessageThread

    async def get_or_create_thread(
        self,
        workspace: Workspace,
        participants: list[User],
    ) -> DirectMessageThread:
        """
        Get or create a DM thread between the given participants.

        Searches existing threads by exact participant set (order-independent).
        """
        participant_ids = sorted(u.id for u in participants)

        async for thread in DirectMessageThread.objects.filter(workspace=workspace):
            thread_ids = sorted(
                [uid async for uid in thread.participants.values_list("id", flat=True)]
            )
            if thread_ids == participant_ids:
                return thread

        async with transaction.atomic():
            thread = await DirectMessageThread.objects.acreate(workspace=workspace)
            await thread.participants.aset(participants)
        return thread

    async def get_user_threads(
        self,
        workspace: Workspace,
        user: User,
    ) -> list[DirectMessageThread]:
        """Get all DM threads for a user in a workspace, most recent first."""
        return [
            t
            async for t in DirectMessageThread.objects.filter(
                workspace=workspace,
                participants=user,
            )
            .prefetch_related("participants")
            .order_by("-updated_at")
        ]


# =============================================================================
# Read Receipt Service
# =============================================================================


class ReadReceiptService(BaseService["ReadReceipt"]):
    """Service for tracking read positions in channels and DM threads."""

    model = ReadReceipt

    async def mark_read(
        self,
        user: User,
        message: Message,
        channel: Channel | None = None,
        dm_thread: DirectMessageThread | None = None,
    ) -> ReadReceipt:
        """Mark messages as read up to and including ``message``."""
        receipt, _ = await ReadReceipt.objects.aupdate_or_create(
            user=user,
            channel=channel,
            dm_thread=dm_thread,
            defaults={
                "last_read_message": message,
                "last_read_at": timezone.now(),
            },
        )
        return receipt

    async def get_unread_count(
        self,
        user: User,
        channel: Channel | None = None,
        dm_thread: DirectMessageThread | None = None,
    ) -> int:
        """Return count of messages unread by ``user`` in channel or DM thread."""
        if channel is None and dm_thread is None:
            return 0

        receipt = await ReadReceipt.objects.filter(
            user=user, channel=channel, dm_thread=dm_thread
        ).afirst()

        qs = Message.objects.filter(is_deleted=False)
        if channel:
            qs = qs.filter(channel=channel)
        else:
            qs = qs.filter(dm_thread=dm_thread)

        if receipt and receipt.last_read_message:
            qs = qs.filter(created_at__gt=receipt.last_read_message.created_at)

        qs = qs.exclude(author=user)
        return await qs.acount()


# =============================================================================
# Search Service
# =============================================================================


class SearchService(BaseService["Message"]):
    """Service for message full-text search."""

    model = Message

    async def search_messages(
        self,
        query: str,
        user: User,
        workspace_id: UUID | None = None,
        channel_id: UUID | None = None,
        from_user_id: int | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Message], int]:
        """
        Search non-deleted messages by keyword with optional filters.

        Only returns messages the requesting user is permitted to see
        (public channels, private channels they belong to, or DM threads
        they participate in).
        """
        qs = Message.objects.filter(
            is_deleted=False,
            content__icontains=query,
        ).select_related("author", "channel", "channel__workspace")

        if workspace_id:
            qs = qs.filter(channel__workspace_id=workspace_id)

        qs = qs.filter(
            Q(channel__is_private=False)
            | Q(channel__memberships__user=user)
            | Q(dm_thread__participants=user)
        ).distinct()

        if channel_id:
            qs = qs.filter(channel_id=channel_id)
        if from_user_id:
            qs = qs.filter(author_id=from_user_id)
        if after:
            qs = qs.filter(created_at__gt=after)
        if before:
            qs = qs.filter(created_at__lt=before)

        total = await qs.acount()
        messages = [m async for m in qs.order_by("-created_at")[offset : offset + limit]]
        return messages, total

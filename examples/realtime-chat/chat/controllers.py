"""
REST API controllers for the chat application.

Uses django-matt APIController for clean, organized endpoints.
"""

from datetime import datetime
from uuid import UUID

from django.contrib.auth import authenticate, get_user_model
from django.http import HttpRequest

from django_matt import MattAPI
from django_matt.auth import create_token_pair, jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionDeniedAPIError, ValidationAPIError

from .models import Channel, DirectMessageThread, Message, Workspace
from .schemas import (
    ChannelCreate,
    ChannelMember,
    ChannelResponse,
    ChannelUpdate,
    DMThreadCreate,
    DMThreadResponse,
    FileUploadResponse,
    LoginRequest,
    MessageCreate,
    MessageResponse,
    MessageUpdate,
    RefreshRequest,
    SearchQuery,
    SearchResponse,
    SearchResult,
    ThreadResponse,
    TokenResponse,
    UserBrief,
    UserProfile,
    WorkspaceCreate,
    WorkspaceInvite,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from .services import (
    ChannelService,
    DirectMessageService,
    MessageService,
    ReactionService,
    ReadReceiptService,
    SearchService,
    UserService,
    WorkspaceService,
)

User = get_user_model()


# =============================================================================
# Auth Controller
# =============================================================================


class AuthController(APIController):
    """Authentication endpoints."""

    async def login(self, request: HttpRequest, data: LoginRequest) -> TokenResponse:
        """Login and get JWT tokens."""
        user = await User.objects.filter(email=data.email).afirst()

        if not user or not user.check_password(data.password):
            raise ValidationAPIError("Invalid email or password")

        token_pair = create_token_pair(user)

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=3600,
        )

    async def register(
        self, request: HttpRequest, data: LoginRequest
    ) -> TokenResponse:
        """Register a new user."""
        # Check if email exists
        if await User.objects.filter(email=data.email).aexists():
            raise ValidationAPIError("Email already registered")

        # Create user
        user = await User.objects.acreate_user(
            username=data.email.split("@")[0],
            email=data.email,
            password=data.password,
        )

        # Create profile
        await UserService.get_or_create_profile(user)

        token_pair = create_token_pair(user)

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=3600,
        )

    async def refresh(self, request: HttpRequest, data: RefreshRequest) -> TokenResponse:
        """Refresh access token."""
        from django_matt.auth import refresh_tokens

        try:
            token_pair = refresh_tokens(data.refresh_token)
            return TokenResponse(
                access_token=token_pair.access_token,
                refresh_token=token_pair.refresh_token,
                token_type="bearer",
                expires_in=3600,
            )
        except Exception as e:
            raise ValidationAPIError(f"Invalid refresh token: {e}")

    @jwt_required
    async def me(self, request: HttpRequest) -> UserProfile:
        """Get current user profile."""
        user = request.user
        profile = await UserService.get_or_create_profile(user)

        return UserProfile(
            user_id=user.id,
            username=user.username,
            email=user.email,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            status=profile.status,
            status_text=profile.status_text,
            last_seen=profile.last_seen,
        )


# =============================================================================
# Workspace Controller
# =============================================================================


class WorkspaceController(APIController):
    """Workspace management endpoints."""

    @jwt_required
    async def list(self, request: HttpRequest) -> list[WorkspaceResponse]:
        """List user's workspaces."""
        workspaces = await WorkspaceService.get_user_workspaces(request.user)
        return [WorkspaceService.to_response(w) for w in workspaces]

    @jwt_required
    async def create(
        self, request: HttpRequest, data: WorkspaceCreate
    ) -> WorkspaceResponse:
        """Create a new workspace."""
        workspace = await WorkspaceService.create(
            user=request.user,
            name=data.name,
            slug=data.slug,
            description=data.description,
        )
        return WorkspaceService.to_response(workspace)

    @jwt_required
    async def get(self, request: HttpRequest, workspace_id: UUID) -> WorkspaceResponse:
        """Get workspace details."""
        workspace = await WorkspaceService.get_workspace(workspace_id, request.user)
        if not workspace:
            raise NotFoundAPIError("Workspace not found")
        return WorkspaceService.to_response(workspace)

    @jwt_required
    async def update(
        self, request: HttpRequest, workspace_id: UUID, data: WorkspaceUpdate
    ) -> WorkspaceResponse:
        """Update workspace."""
        workspace = await WorkspaceService.get_workspace(workspace_id, request.user)
        if not workspace:
            raise NotFoundAPIError("Workspace not found")

        # Only owner can update
        if workspace.owner_id != request.user.id:
            raise PermissionDeniedAPIError("Only owner can update workspace")

        if data.name:
            workspace.name = data.name
        if data.description is not None:
            workspace.description = data.description
        if data.icon_url is not None:
            workspace.icon_url = data.icon_url

        await workspace.asave()
        return WorkspaceService.to_response(workspace)

    @jwt_required
    async def delete(self, request: HttpRequest, workspace_id: UUID) -> dict:
        """Delete workspace."""
        workspace = await WorkspaceService.get_workspace(workspace_id, request.user)
        if not workspace:
            raise NotFoundAPIError("Workspace not found")

        if workspace.owner_id != request.user.id:
            raise PermissionDeniedAPIError("Only owner can delete workspace")

        await workspace.adelete()
        return {"deleted": True}

    @jwt_required
    async def invite(
        self, request: HttpRequest, workspace_id: UUID, data: WorkspaceInvite
    ) -> dict:
        """Invite user to workspace."""
        workspace = await WorkspaceService.get_workspace(workspace_id, request.user)
        if not workspace:
            raise NotFoundAPIError("Workspace not found")

        # Find user by email
        user = await User.objects.filter(email=data.email).afirst()
        if not user:
            # In production, would send invite email
            raise NotFoundAPIError("User not found")

        await WorkspaceService.add_member(
            workspace=workspace,
            user=user,
            role=data.role,
            invited_by=request.user,
        )

        return {"invited": True, "email": data.email}

    @jwt_required
    async def channels(
        self, request: HttpRequest, workspace_id: UUID
    ) -> list[ChannelResponse]:
        """List channels in workspace."""
        workspace = await WorkspaceService.get_workspace(workspace_id, request.user)
        if not workspace:
            raise NotFoundAPIError("Workspace not found")

        channels = await ChannelService.get_workspace_channels(workspace, request.user)
        return [ChannelService.to_response(c) for c in channels]

    @jwt_required
    async def create_channel(
        self, request: HttpRequest, workspace_id: UUID, data: ChannelCreate
    ) -> ChannelResponse:
        """Create channel in workspace."""
        workspace = await WorkspaceService.get_workspace(workspace_id, request.user)
        if not workspace:
            raise NotFoundAPIError("Workspace not found")

        channel = await ChannelService.create(
            workspace=workspace,
            user=request.user,
            name=data.name,
            description=data.description,
            is_private=data.is_private,
        )
        return ChannelService.to_response(channel)


# =============================================================================
# Channel Controller
# =============================================================================


class ChannelController(APIController):
    """Channel management endpoints."""

    @jwt_required
    async def get(self, request: HttpRequest, channel_id: UUID) -> ChannelResponse:
        """Get channel details."""
        channel = await ChannelService.get_channel(channel_id, request.user)
        if not channel:
            raise NotFoundAPIError("Channel not found")
        return ChannelService.to_response(channel)

    @jwt_required
    async def update(
        self, request: HttpRequest, channel_id: UUID, data: ChannelUpdate
    ) -> ChannelResponse:
        """Update channel."""
        channel = await ChannelService.get_channel(channel_id, request.user)
        if not channel:
            raise NotFoundAPIError("Channel not found")

        if data.name:
            channel.name = data.name
        if data.description is not None:
            channel.description = data.description
        if data.topic is not None:
            channel.topic = data.topic
        if data.is_archived is not None:
            channel.is_archived = data.is_archived

        await channel.asave()
        return ChannelService.to_response(channel)

    @jwt_required
    async def delete(self, request: HttpRequest, channel_id: UUID) -> dict:
        """Delete channel."""
        channel = await ChannelService.get_channel(channel_id, request.user)
        if not channel:
            raise NotFoundAPIError("Channel not found")

        # Check if user created the channel or is workspace owner
        if (
            channel.created_by_id != request.user.id
            and channel.workspace.owner_id != request.user.id
        ):
            raise PermissionDeniedAPIError("Cannot delete this channel")

        await channel.adelete()
        return {"deleted": True}

    @jwt_required
    async def members(self, request: HttpRequest, channel_id: UUID) -> list[ChannelMember]:
        """List channel members."""
        channel = await ChannelService.get_channel(channel_id, request.user)
        if not channel:
            raise NotFoundAPIError("Channel not found")

        memberships = await ChannelService.get_members(channel)
        return [
            ChannelMember(
                user=UserBrief(
                    id=m.user.id,
                    username=m.user.username,
                    display_name=getattr(m.user, "chat_profile", None)
                    and m.user.chat_profile.display_name,
                    avatar_url=getattr(m.user, "chat_profile", None)
                    and m.user.chat_profile.avatar_url,
                    status=getattr(m.user, "chat_profile", None)
                    and m.user.chat_profile.status
                    or "offline",
                ),
                joined_at=m.joined_at,
                is_muted=m.is_muted,
            )
            for m in memberships
        ]

    @jwt_required
    async def add_member(
        self, request: HttpRequest, channel_id: UUID, user_id: int
    ) -> dict:
        """Add member to channel."""
        channel = await ChannelService.get_channel(channel_id, request.user)
        if not channel:
            raise NotFoundAPIError("Channel not found")

        user = await User.objects.filter(id=user_id).afirst()
        if not user:
            raise NotFoundAPIError("User not found")

        await ChannelService.add_member(channel, user)
        return {"added": True}

    @jwt_required
    async def remove_member(
        self, request: HttpRequest, channel_id: UUID, user_id: int
    ) -> dict:
        """Remove member from channel."""
        channel = await ChannelService.get_channel(channel_id, request.user)
        if not channel:
            raise NotFoundAPIError("Channel not found")

        user = await User.objects.filter(id=user_id).afirst()
        if not user:
            raise NotFoundAPIError("User not found")

        removed = await ChannelService.remove_member(channel, user)
        return {"removed": removed}

    @jwt_required
    async def messages(
        self,
        request: HttpRequest,
        channel_id: UUID,
        limit: int = 50,
        before: str | None = None,
    ) -> list[MessageResponse]:
        """Get channel messages."""
        channel = await ChannelService.get_channel(channel_id, request.user)
        if not channel:
            raise NotFoundAPIError("Channel not found")

        before_dt = datetime.fromisoformat(before) if before else None

        messages = await MessageService.get_channel_messages(
            channel=channel,
            limit=limit,
            before=before_dt,
        )

        return [MessageService.to_response(m, request.user) for m in messages]

    @jwt_required
    async def send_message(
        self, request: HttpRequest, channel_id: UUID, data: MessageCreate
    ) -> MessageResponse:
        """Send message to channel."""
        channel = await ChannelService.get_channel(channel_id, request.user)
        if not channel:
            raise NotFoundAPIError("Channel not found")

        message = await MessageService.create(
            user=request.user,
            content=data.content,
            channel=channel,
            parent_message_id=data.thread_id,
            attachment_ids=data.attachment_ids,
        )

        return MessageService.to_response(message, request.user)


# =============================================================================
# Message Controller
# =============================================================================


class MessageController(APIController):
    """Message management endpoints."""

    @jwt_required
    async def get(self, request: HttpRequest, message_id: UUID) -> MessageResponse:
        """Get message details."""
        message = await MessageService.get_message(message_id)
        if not message:
            raise NotFoundAPIError("Message not found")
        return MessageService.to_response(message, request.user)

    @jwt_required
    async def update(
        self, request: HttpRequest, message_id: UUID, data: MessageUpdate
    ) -> MessageResponse:
        """Edit a message."""
        message = await MessageService.get_message(message_id)
        if not message:
            raise NotFoundAPIError("Message not found")

        if message.author_id != request.user.id:
            raise PermissionDeniedAPIError("Can only edit own messages")

        message = await MessageService.update(message, data.content)
        return MessageService.to_response(message, request.user)

    @jwt_required
    async def delete(self, request: HttpRequest, message_id: UUID) -> dict:
        """Delete a message."""
        message = await MessageService.get_message(message_id)
        if not message:
            raise NotFoundAPIError("Message not found")

        if message.author_id != request.user.id:
            raise PermissionDeniedAPIError("Can only delete own messages")

        await MessageService.delete(message)
        return {"deleted": True}

    @jwt_required
    async def thread(self, request: HttpRequest, message_id: UUID) -> ThreadResponse:
        """Get message thread (replies)."""
        message = await MessageService.get_message(message_id)
        if not message:
            raise NotFoundAPIError("Message not found")

        replies = await MessageService.get_thread(message)

        return ThreadResponse(
            parent_message=MessageService.to_response(message, request.user),
            replies=[MessageService.to_response(r, request.user) for r in replies],
            reply_count=len(replies),
        )

    @jwt_required
    async def add_reaction(
        self, request: HttpRequest, message_id: UUID, emoji: str
    ) -> dict:
        """Add reaction to message."""
        message = await MessageService.get_message(message_id)
        if not message:
            raise NotFoundAPIError("Message not found")

        reaction = await ReactionService.add(message, request.user, emoji)
        return {"added": reaction is not None}

    @jwt_required
    async def remove_reaction(
        self, request: HttpRequest, message_id: UUID, emoji: str
    ) -> dict:
        """Remove reaction from message."""
        message = await MessageService.get_message(message_id)
        if not message:
            raise NotFoundAPIError("Message not found")

        removed = await ReactionService.remove(message, request.user, emoji)
        return {"removed": removed}


# =============================================================================
# Direct Message Controller
# =============================================================================


class DirectMessageController(APIController):
    """Direct message endpoints."""

    @jwt_required
    async def list(
        self, request: HttpRequest, workspace_id: UUID
    ) -> list[DMThreadResponse]:
        """List DM threads for user in workspace."""
        workspace = await WorkspaceService.get_workspace(workspace_id, request.user)
        if not workspace:
            raise NotFoundAPIError("Workspace not found")

        threads = await DirectMessageService.get_user_threads(workspace, request.user)

        responses = []
        for thread in threads:
            participants = [
                UserBrief(
                    id=u.id,
                    username=u.username,
                    display_name=None,
                    avatar_url=None,
                    status="offline",
                )
                for u in thread.participants.all()
            ]

            responses.append(
                DMThreadResponse(
                    id=thread.id,
                    workspace_id=thread.workspace_id,
                    participants=participants,
                    last_message=None,  # TODO: Get last message
                    unread_count=0,  # TODO: Calculate
                    created_at=thread.created_at,
                    updated_at=thread.updated_at,
                )
            )

        return responses

    @jwt_required
    async def create(
        self, request: HttpRequest, workspace_id: UUID, data: DMThreadCreate
    ) -> DMThreadResponse:
        """Create or get DM thread."""
        workspace = await WorkspaceService.get_workspace(workspace_id, request.user)
        if not workspace:
            raise NotFoundAPIError("Workspace not found")

        # Get users
        users = await User.objects.filter(id__in=data.user_ids).alist()
        if not users:
            raise NotFoundAPIError("Users not found")

        # Include current user
        participants = list(users)
        if request.user not in participants:
            participants.append(request.user)

        thread = await DirectMessageService.get_or_create_thread(workspace, participants)

        return DMThreadResponse(
            id=thread.id,
            workspace_id=thread.workspace_id,
            participants=[
                UserBrief(
                    id=u.id,
                    username=u.username,
                    display_name=None,
                    avatar_url=None,
                    status="offline",
                )
                for u in participants
            ],
            last_message=None,
            unread_count=0,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
        )

    @jwt_required
    async def messages(
        self, request: HttpRequest, dm_id: UUID, limit: int = 50
    ) -> list[MessageResponse]:
        """Get DM messages."""
        thread = await DirectMessageThread.objects.filter(
            id=dm_id, participants=request.user
        ).afirst()

        if not thread:
            raise NotFoundAPIError("DM thread not found")

        messages = await Message.objects.filter(
            dm_thread=thread, is_deleted=False
        ).select_related("author").order_by("-created_at")[:limit]

        return [
            MessageService.to_response(m, request.user)
            for m in reversed(list(messages))
        ]

    @jwt_required
    async def send_message(
        self, request: HttpRequest, dm_id: UUID, data: MessageCreate
    ) -> MessageResponse:
        """Send DM."""
        thread = await DirectMessageThread.objects.filter(
            id=dm_id, participants=request.user
        ).afirst()

        if not thread:
            raise NotFoundAPIError("DM thread not found")

        message = await MessageService.create(
            user=request.user,
            content=data.content,
            dm_thread=thread,
            attachment_ids=data.attachment_ids,
        )

        return MessageService.to_response(message, request.user)


# =============================================================================
# File Controller
# =============================================================================


class FileController(APIController):
    """File upload endpoints."""

    @jwt_required
    async def upload(self, request: HttpRequest) -> FileUploadResponse:
        """Upload a file."""
        from django.conf import settings

        from .models import FileAttachment

        if "file" not in request.FILES:
            raise ValidationAPIError("No file provided")

        file = request.FILES["file"]
        workspace_id = request.POST.get("workspace_id")

        if not workspace_id:
            raise ValidationAPIError("workspace_id required")

        workspace = await WorkspaceService.get_workspace(
            UUID(workspace_id), request.user
        )
        if not workspace:
            raise NotFoundAPIError("Workspace not found")

        # Validate file size
        if file.size > settings.MAX_UPLOAD_SIZE:
            raise ValidationAPIError(
                f"File too large. Max size: {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB"
            )

        # Validate file type
        if file.content_type not in settings.ALLOWED_UPLOAD_TYPES:
            raise ValidationAPIError(f"File type not allowed: {file.content_type}")

        # Create attachment
        attachment = await FileAttachment.objects.acreate(
            workspace=workspace,
            uploaded_by=request.user,
            file=file,
            original_filename=file.name,
            mime_type=file.content_type,
            file_size=file.size,
        )

        return FileUploadResponse(
            id=attachment.id,
            original_filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            file_size=attachment.file_size,
            url=attachment.file.url,
            thumbnail_url=attachment.thumbnail_url,
            width=attachment.width,
            height=attachment.height,
        )

    @jwt_required
    async def get(self, request: HttpRequest, file_id: UUID) -> FileUploadResponse:
        """Get file info."""
        from .models import FileAttachment

        attachment = await FileAttachment.objects.filter(id=file_id).afirst()
        if not attachment:
            raise NotFoundAPIError("File not found")

        return FileUploadResponse(
            id=attachment.id,
            original_filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            file_size=attachment.file_size,
            url=attachment.file.url,
            thumbnail_url=attachment.thumbnail_url,
            width=attachment.width,
            height=attachment.height,
        )

    @jwt_required
    async def delete(self, request: HttpRequest, file_id: UUID) -> dict:
        """Delete a file."""
        from .models import FileAttachment

        attachment = await FileAttachment.objects.filter(
            id=file_id, uploaded_by=request.user
        ).afirst()

        if not attachment:
            raise NotFoundAPIError("File not found")

        # Delete the actual file
        if attachment.file:
            attachment.file.delete(save=False)

        await attachment.adelete()
        return {"deleted": True}


# =============================================================================
# Search Controller
# =============================================================================


class SearchController(APIController):
    """Search endpoints."""

    @jwt_required
    async def messages(self, request: HttpRequest, q: SearchQuery) -> SearchResponse:
        """Search messages."""
        messages, total = await SearchService.search_messages(
            query=q.query,
            user=request.user,
            workspace_id=q.workspace_id,
            channel_id=q.channel_id,
            from_user_id=q.from_user_id,
            after=q.after,
            before=q.before,
            limit=q.limit,
            offset=q.offset,
        )

        results = []
        for message in messages:
            channel_response = None
            if message.channel:
                channel_response = ChannelService.to_response(message.channel)

            # Create highlight with context
            content = message.content
            query_lower = q.query.lower()
            content_lower = content.lower()
            idx = content_lower.find(query_lower)

            if idx >= 0:
                start = max(0, idx - 50)
                end = min(len(content), idx + len(q.query) + 50)
                highlight = content[start:end]
                if start > 0:
                    highlight = "..." + highlight
                if end < len(content):
                    highlight = highlight + "..."
            else:
                highlight = content[:100]

            results.append(
                SearchResult(
                    message=MessageService.to_response(message, request.user),
                    channel=channel_response,
                    highlight=highlight,
                )
            )

        return SearchResponse(
            results=results,
            total_count=total,
            query=q.query,
        )

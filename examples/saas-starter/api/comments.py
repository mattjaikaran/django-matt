"""
Comment API controllers.

Includes:
- Comment CRUD
- Reactions
- Mentions handling
"""

import re

from django.db import models
from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.router import delete, get, patch, post

from core.models import Membership, Organization, User
from projects.models import Comment, Project, ProjectMember, Task, TaskActivity
from projects.schemas import (
    CommentCreate,
    CommentDetailResponse,
    CommentResponse,
    CommentUpdate,
    ReactionRequest,
)


class CommentController(APIController):
    prefix = "/organizations/<str:org_slug>/projects/<str:project_slug>/tasks/<str:task_id>/comments"
    tags = ["Comments"]

    async def get_task_and_check_access(self, request, org_slug: str, project_slug: str, task_id: str, require_edit: bool = False):
        """Helper to get task and check user access."""
        try:
            org = await Organization.objects.aget(slug=org_slug)
        except Organization.DoesNotExist:
            return None, None, None, None, ({"error": "Organization not found"}, 404)

        membership = await Membership.objects.filter(
            user=request.user,
            organization=org,
            is_active=True,
        ).afirst()

        if not membership:
            return None, None, None, None, ({"error": "Not a member of this organization"}, 403)

        try:
            project = await Project.objects.aget(organization=org, slug=project_slug)
        except Project.DoesNotExist:
            return None, None, None, None, ({"error": "Project not found"}, 404)

        try:
            task = await Task.objects.aget(id=task_id, project=project)
        except Task.DoesNotExist:
            return None, None, None, None, ({"error": "Task not found"}, 404)

        # Check project access
        if not membership.is_admin and not project.is_public:
            pm = await ProjectMember.objects.filter(project=project, user=request.user).afirst()
            if not pm:
                return None, None, None, None, ({"error": "Access denied"}, 403)

        return org, project, task, membership, None

    async def extract_mentions(self, content: str, org) -> list:
        """Extract and validate mentions from comment content."""
        # Pattern matches @username or @[Full Name]
        mention_pattern = r"@(\w+)|@\[([^\]]+)\]"
        mentions = re.findall(mention_pattern, content)

        mentioned_users = []
        for username, display_name in mentions:
            name = username or display_name
            # Try to find user by username part of email or full name
            users = User.objects.filter(
                memberships__organization=org,
                memberships__is_active=True,
            ).filter(
                models.Q(email__istartswith=f"{name}@") |
                models.Q(first_name__iexact=name) |
                models.Q(last_name__iexact=name)
            )[:5]

            async for user in users:
                if user not in mentioned_users:
                    mentioned_users.append(user)

        return mentioned_users

    # =========================================================================
    # Comment CRUD
    # =========================================================================

    @get("/")
    @jwt_required
    async def list_comments(self, request, org_slug: str, project_slug: str, task_id: str) -> list:
        """List all comments on a task."""
        org, project, task, membership, error = await self.get_task_and_check_access(
            request, org_slug, project_slug, task_id
        )
        if error:
            return error

        comments = Comment.objects.filter(
            task=task,
            parent__isnull=True,  # Top-level comments only
        ).select_related("author").prefetch_related("mentions", "replies")

        result = []
        async for comment in comments.order_by("created_at"):
            comment_data = CommentDetailResponse.model_validate(comment)

            # Add replies
            replies = []
            async for reply in comment.replies.select_related("author"):
                replies.append(CommentResponse.model_validate(reply))
            comment_data.replies = replies

            # Add mentions
            mentions = []
            async for user in comment.mentions.all():
                from core.schemas import UserMiniResponse
                mentions.append(UserMiniResponse.model_validate(user))
            comment_data.mentions = mentions

            result.append(comment_data)

        return result

    @post("/")
    @jwt_required
    async def create_comment(self, request, org_slug: str, project_slug: str, task_id: str, data: CommentCreate) -> dict:
        """Add a comment to a task."""
        org, project, task, membership, error = await self.get_task_and_check_access(
            request, org_slug, project_slug, task_id
        )
        if error:
            return error

        # Validate parent if provided
        parent = None
        if data.parent_id:
            try:
                parent = await Comment.objects.aget(id=data.parent_id, task=task)
            except Comment.DoesNotExist:
                return {"error": "Parent comment not found"}, 404

        # Create comment
        comment = await Comment.objects.acreate(
            task=task,
            author=request.user,
            parent=parent,
            content=data.content,
            attachments=data.attachments,
        )

        # Extract and add mentions
        mentioned_users = await self.extract_mentions(data.content, org)
        for user in mentioned_users:
            if user != request.user:
                await comment.mentions.aadd(user)

        # Create activity
        await TaskActivity.objects.acreate(
            task=task,
            user=request.user,
            action="commented",
            metadata={"comment_id": str(comment.id)},
        )

        # Broadcast to WebSocket
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            await channel_layer.group_send(
                f"task_{task_id}",
                {
                    "type": "comment_added",
                    "comment_id": str(comment.id),
                    "author_id": str(request.user.id),
                }
            )

        return CommentDetailResponse.model_validate(comment)

    @patch("/<str:comment_id>")
    @jwt_required
    async def update_comment(self, request, org_slug: str, project_slug: str, task_id: str, comment_id: str, data: CommentUpdate) -> dict:
        """Update a comment. Only the comment author can edit."""
        org, project, task, membership, error = await self.get_task_and_check_access(
            request, org_slug, project_slug, task_id
        )
        if error:
            return error

        try:
            comment = await Comment.objects.aget(id=comment_id, task=task)

            # Check ownership
            if comment.author_id != request.user.id and not membership.is_admin:
                return {"error": "Can only edit your own comments"}, 403

            comment.content = data.content
            comment.is_edited = True
            comment.edited_at = timezone.now()
            await comment.asave()

            # Re-extract mentions
            await comment.mentions.aclear()
            mentioned_users = await self.extract_mentions(data.content, org)
            for user in mentioned_users:
                if user != request.user:
                    await comment.mentions.aadd(user)

            return CommentDetailResponse.model_validate(comment)

        except Comment.DoesNotExist:
            return {"error": "Comment not found"}, 404

    @delete("/<str:comment_id>")
    @jwt_required
    async def delete_comment(self, request, org_slug: str, project_slug: str, task_id: str, comment_id: str) -> dict:
        """Delete a comment. Only the comment author or admins can delete."""
        org, project, task, membership, error = await self.get_task_and_check_access(
            request, org_slug, project_slug, task_id
        )
        if error:
            return error

        try:
            comment = await Comment.objects.aget(id=comment_id, task=task)

            # Check ownership
            if comment.author_id != request.user.id and not membership.is_admin:
                return {"error": "Can only delete your own comments"}, 403

            await comment.adelete()

            return {"message": "Comment deleted"}

        except Comment.DoesNotExist:
            return {"error": "Comment not found"}, 404

    # =========================================================================
    # Reactions
    # =========================================================================

    @post("/<str:comment_id>/reactions")
    @jwt_required
    async def add_reaction(self, request, org_slug: str, project_slug: str, task_id: str, comment_id: str, data: ReactionRequest) -> dict:
        """Add a reaction to a comment."""
        org, project, task, membership, error = await self.get_task_and_check_access(
            request, org_slug, project_slug, task_id
        )
        if error:
            return error

        try:
            comment = await Comment.objects.aget(id=comment_id, task=task)

            user_id = str(request.user.id)
            reaction = data.reaction

            # Add reaction
            if reaction not in comment.reactions:
                comment.reactions[reaction] = []

            if user_id not in comment.reactions[reaction]:
                comment.reactions[reaction].append(user_id)
                await comment.asave(update_fields=["reactions", "updated_at"])

            return {"reactions": comment.reactions}

        except Comment.DoesNotExist:
            return {"error": "Comment not found"}, 404

    @delete("/<str:comment_id>/reactions/<str:reaction>")
    @jwt_required
    async def remove_reaction(self, request, org_slug: str, project_slug: str, task_id: str, comment_id: str, reaction: str) -> dict:
        """Remove a reaction from a comment."""
        org, project, task, membership, error = await self.get_task_and_check_access(
            request, org_slug, project_slug, task_id
        )
        if error:
            return error

        try:
            comment = await Comment.objects.aget(id=comment_id, task=task)

            user_id = str(request.user.id)

            if reaction in comment.reactions and user_id in comment.reactions[reaction]:
                comment.reactions[reaction].remove(user_id)
                if not comment.reactions[reaction]:
                    del comment.reactions[reaction]
                await comment.asave(update_fields=["reactions", "updated_at"])

            return {"reactions": comment.reactions}

        except Comment.DoesNotExist:
            return {"error": "Comment not found"}, 404

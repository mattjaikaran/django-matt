"""Comments controller."""

from uuid import UUID

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionAPIError, ValidationAPIError
from django_matt.core.router import delete, get, patch, post

from blog.comments.models import Comment
from blog.comments.schemas import CommentCreate, CommentResponse, CommentUpdate
from blog.posts.models import Post


class CommentController(APIController):
    prefix = "/comments"
    tags = ["Comments"]

    @get("/")
    async def list_comments(self, request) -> list[CommentResponse]:
        """Return top-level approved comments for a post (by post UUID)."""
        post_id = request.GET.get("post", "")
        post_obj = await Post.objects.filter(id=post_id, status="published").afirst()
        if post_obj is None:
            raise NotFoundAPIError("Post not found.")

        top_level = (
            Comment.objects.filter(post=post_obj, parent=None, is_approved=True)
            .select_related("author")
            .prefetch_related("replies__author")
            .order_by("created_at")
        )
        return [CommentResponse.model_validate(c) async for c in top_level]

    @post("/")
    async def create_comment(self, request, body: CommentCreate) -> CommentResponse:
        """Create a comment. Auth optional — unauthenticated users supply name/email."""
        post = await Post.objects.filter(id=body.post_id, status="published").afirst()
        if post is None:
            raise NotFoundAPIError("Post not found.")

        user = getattr(request, "user", None)
        is_authenticated = user is not None and user.is_authenticated

        if not is_authenticated and not body.author_name:
            raise ValidationAPIError("author_name is required for unauthenticated comments.")

        parent = None
        if body.parent_id:
            parent = await Comment.objects.filter(id=body.parent_id, post=post).afirst()
            if parent is None:
                raise NotFoundAPIError("Parent comment not found.")

        comment = await Comment.objects.acreate(
            post=post,
            author=user if is_authenticated else None,
            author_name="" if is_authenticated else body.author_name,
            author_email="" if is_authenticated else (body.author_email or ""),
            content=body.content,
            parent=parent,
            is_approved=True,
        )
        await comment.arefresh_from_db()
        return CommentResponse.model_validate(comment)

    @patch("/<uuid:comment_id>")
    @jwt_required
    async def update_comment(
        self, request, comment_id: UUID, body: CommentUpdate
    ) -> CommentResponse:
        """Edit your own comment."""
        comment = await Comment.objects.select_related("author").filter(id=comment_id).afirst()
        if comment is None:
            raise NotFoundAPIError("Comment not found.")
        if comment.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You can only edit your own comments.")
        comment.content = body.content
        await comment.asave(update_fields=["content", "updated_at"])
        return CommentResponse.model_validate(comment)

    @delete("/<uuid:comment_id>")
    @jwt_required
    async def delete_comment(self, request, comment_id: UUID) -> dict:
        """Delete your own comment (or any if staff)."""
        comment = await Comment.objects.filter(id=comment_id).afirst()
        if comment is None:
            raise NotFoundAPIError("Comment not found.")
        if comment.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You can only delete your own comments.")
        await comment.adelete()
        return {"deleted": True}

    @post("/<uuid:comment_id>/approve")
    @jwt_required
    async def approve_comment(self, request, comment_id: UUID) -> CommentResponse:
        """Staff-only: approve a pending comment."""
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can approve comments.")
        comment = await Comment.objects.select_related("author").filter(id=comment_id).afirst()
        if comment is None:
            raise NotFoundAPIError("Comment not found.")
        comment.is_approved = True
        await comment.asave(update_fields=["is_approved"])
        return CommentResponse.model_validate(comment)

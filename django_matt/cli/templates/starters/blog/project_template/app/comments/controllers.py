"""Comment controller."""

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionAPIError
from django_matt.core.router import delete, get, post

from {{ project_name }}_app.comments.models import Comment
from {{ project_name }}_app.comments.schemas import CommentCreateSchema, CommentSchema
from {{ project_name }}_app.posts.models import Post


class CommentController(APIController):
    prefix = "/comments"
    tags = ["Comments"]

    @get("/")
    async def list_comments(self, request) -> list[CommentSchema]:
        post_id = request.GET.get("post", "")
        post_obj = await Post.objects.filter(id=post_id, status="published").afirst()
        if post_obj is None:
            raise NotFoundAPIError("Post not found.")
        comments = (
            Comment.objects.filter(post=post_obj, approved=True)
            .select_related("post")
            .order_by("created_at")
        )
        return [CommentSchema.model_validate(c) async for c in comments]

    @post("/")
    async def create_comment(self, request, body: CommentCreateSchema) -> CommentSchema:
        post_id = request.GET.get("post", "")
        post_obj = await Post.objects.filter(id=post_id, status="published").afirst()
        if post_obj is None:
            raise NotFoundAPIError("Post not found.")
        comment = await Comment.objects.acreate(
            post=post_obj,
            author_name=body.author_name,
            author_email=body.author_email,
            body=body.body,
            approved=True,
        )
        return CommentSchema.model_validate(comment)

    @post("/{comment_id}/approve")
    @jwt_required
    async def approve_comment(self, request, comment_id: str) -> CommentSchema:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can approve comments.")
        comment = await Comment.objects.filter(id=comment_id).afirst()
        if comment is None:
            raise NotFoundAPIError("Comment not found.")
        comment.approved = True
        await comment.asave()
        return CommentSchema.model_validate(comment)

    @delete("/{comment_id}")
    @jwt_required
    async def delete_comment(self, request, comment_id: str) -> dict:
        comment = await Comment.objects.filter(id=comment_id).afirst()
        if comment is None:
            raise NotFoundAPIError("Comment not found.")
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can delete comments.")
        await comment.adelete()
        return {"deleted": True}

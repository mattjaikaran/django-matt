"""Post and tag controllers."""

import math

from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionAPIError, ValidationAPIError
from django_matt.core.router import delete, get, patch, post

from {{ project_name }}_app.posts.models import Post, Tag
from {{ project_name }}_app.posts.schemas import (
    PaginatedPosts,
    PostCreateSchema,
    PostDetailSchema,
    PostListSchema,
    PostUpdateSchema,
    TagSchema,
)


def serialize_post_list(post: Post) -> dict:
    return {
        "id": str(post.id),
        "title": post.title,
        "slug": post.slug,
        "excerpt": post.excerpt,
        "featured": post.featured,
        "author_name": post.author.username,
        "tags": [{"name": t.name, "slug": t.slug} for t in post.tags.all()],
        "published_at": post.published_at.isoformat() if post.published_at else None,
    }


def serialize_post_detail(post: Post) -> dict:
    data = serialize_post_list(post)
    data["content"] = post.content
    data["status"] = post.status
    data["created_at"] = post.created_at.isoformat()
    data["updated_at"] = post.updated_at.isoformat()
    return data


class TagController(APIController):
    prefix = "/tags"
    tags = ["Tags"]

    @get("/")
    async def list_tags(self) -> list[TagSchema]:
        return [TagSchema.model_validate(t) async for t in Tag.objects.all()]

    @get("/{slug}")
    async def get_tag(self, slug: str) -> TagSchema:
        tag = await Tag.objects.filter(slug=slug).afirst()
        if tag is None:
            raise NotFoundAPIError(f"Tag '{slug}' not found.")
        return TagSchema.model_validate(tag)

    @post("/")
    @jwt_required
    async def create_tag(self, request, body: TagSchema) -> TagSchema:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can create tags.")
        tag, _ = await Tag.objects.aget_or_create(
            name=body.name, defaults={"name": body.name}
        )
        return TagSchema.model_validate(tag)


class PostController(APIController):
    prefix = "/posts"
    tags = ["Posts"]

    @get("/")
    async def list_posts(
        self,
        tag: str | None = None,
        author: str | None = None,
        status: str = "published",
        featured: bool | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedPosts:
        page_size = min(page_size, 50)
        qs = (
            Post.objects.select_related("author")
            .prefetch_related("tags")
            .order_by("-published_at", "-created_at")
        )
        if status:
            qs = qs.filter(status=status)
        if tag:
            qs = qs.filter(tags__slug=tag)
        if author:
            qs = qs.filter(author__username=author)
        if featured is not None:
            qs = qs.filter(featured=featured)

        total = await qs.acount()
        offset = (page - 1) * page_size
        posts = [p async for p in qs[offset : offset + page_size]]

        return PaginatedPosts(
            items=[PostListSchema(**serialize_post_list(p)) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @get("/{slug}")
    async def get_post(self, slug: str) -> PostDetailSchema:
        post = await (
            Post.objects.select_related("author")
            .prefetch_related("tags")
            .filter(slug=slug, status="published")
            .afirst()
        )
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        return PostDetailSchema(**serialize_post_detail(post))

    @get("/search")
    async def search(
        self, q: str, page: int = 1, page_size: int = 10
    ) -> PaginatedPosts:
        if not q or len(q.strip()) < 2:
            raise ValidationAPIError("Search query must be at least 2 characters.")
        page_size = min(page_size, 50)
        qs = (
            Post.objects.filter(
                status="published", content__icontains=q.strip()
            )
            .select_related("author")
            .prefetch_related("tags")
            .order_by("-published_at")
        )
        total = await qs.acount()
        offset = (page - 1) * page_size
        posts = [p async for p in qs[offset : offset + page_size]]
        return PaginatedPosts(
            items=[PostListSchema(**serialize_post_list(p)) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @get("/my")
    @jwt_required
    async def my_posts(
        self, request, status: str | None = None, page: int = 1, page_size: int = 10
    ) -> PaginatedPosts:
        page_size = min(page_size, 50)
        qs = (
            Post.objects.filter(author=request.user)
            .select_related("author")
            .prefetch_related("tags")
            .order_by("-created_at")
        )
        if status:
            qs = qs.filter(status=status)
        total = await qs.acount()
        offset = (page - 1) * page_size
        posts = [p async for p in qs[offset : offset + page_size]]
        return PaginatedPosts(
            items=[PostListSchema(**serialize_post_list(p)) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @post("/")
    @jwt_required
    async def create_post(self, request, body: PostCreateSchema) -> PostDetailSchema:
        post = await Post.objects.acreate(
            title=body.title,
            content=body.content,
            excerpt=body.excerpt or "",
            status=body.status,
            featured=body.featured,
            author=request.user,
            published_at=timezone.now() if body.status == "published" else None,
        )
        if body.tag_names:
            tags = []
            for name in body.tag_names:
                tag, _ = await Tag.objects.aget_or_create(
                    name=name, defaults={"name": name}
                )
                tags.append(tag)
            await post.tags.aset(tags)
        return PostDetailSchema(**serialize_post_detail(post))

    @patch("/{slug}")
    @jwt_required
    async def update_post(
        self, request, slug: str, body: PostUpdateSchema
    ) -> PostDetailSchema:
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You don't have permission to edit this post.")

        update_data = body.model_dump(exclude_unset=True)
        tag_names = update_data.pop("tag_names", None)

        for field, value in update_data.items():
            setattr(post, field, value)
        await post.asave()

        if tag_names is not None:
            tags = []
            for name in tag_names:
                tag, _ = await Tag.objects.aget_or_create(
                    name=name, defaults={"name": name}
                )
                tags.append(tag)
            await post.tags.aset(tags)

        return PostDetailSchema(**serialize_post_detail(post))

    @post("/{slug}/publish")
    @jwt_required
    async def publish_post(self, request, slug: str) -> PostDetailSchema:
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You don't have permission to publish this post.")
        post.status = "published"
        post.published_at = timezone.now()
        await post.asave()
        return PostDetailSchema(**serialize_post_detail(post))

    @delete("/{slug}")
    @jwt_required
    async def delete_post(self, request, slug: str) -> dict:
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You don't have permission to delete this post.")
        await post.adelete()
        return {"deleted": True}

"""API controllers for posts, tags, and categories."""

import math
from uuid import UUID

from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import ForbiddenAPIError, NotFoundAPIError, ValidationAPIError

from blog.posts.models import Category, Post, Tag
from blog.posts.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    PaginatedPostsResponse,
    PostCreate,
    PostDetailResponse,
    PostListResponse,
    PostUpdate,
    SEOMetaResponse,
    TagCreate,
    TagResponse,
)
from blog.posts.services import (
    get_post_by_slug,
    get_published_posts,
    get_seo_meta,
    publish_post,
    record_view,
    search_posts,
)


class TagController(APIController):
    prefix = "/tags"
    tags = ["Tags"]

    @staticmethod
    async def list_tags() -> list[TagResponse]:
        return [TagResponse.model_validate(t) async for t in Tag.objects.all()]

    @staticmethod
    async def get_tag(slug: str) -> TagResponse:
        tag = await Tag.objects.filter(slug=slug).afirst()
        if tag is None:
            raise NotFoundAPIError(f"Tag '{slug}' not found.")
        return TagResponse.model_validate(tag)

    @jwt_required
    async def create_tag(self, request, data: TagCreate) -> TagResponse:
        if not request.user.is_staff:
            raise ForbiddenAPIError("Only staff can create tags.")
        tag, _ = await Tag.objects.aget_or_create(
            name=data.name,
            defaults={"name": data.name},
        )
        return TagResponse.model_validate(tag)


class CategoryController(APIController):
    prefix = "/categories"
    tags = ["Categories"]

    @staticmethod
    async def list_categories() -> list[CategoryResponse]:
        return [CategoryResponse.model_validate(c) async for c in Category.objects.all()]

    @staticmethod
    async def get_category(slug: str) -> CategoryResponse:
        cat = await Category.objects.filter(slug=slug).afirst()
        if cat is None:
            raise NotFoundAPIError(f"Category '{slug}' not found.")
        return CategoryResponse.model_validate(cat)

    @jwt_required
    async def create_category(self, request, data: CategoryCreate) -> CategoryResponse:
        if not request.user.is_staff:
            raise ForbiddenAPIError("Only staff can create categories.")
        cat = await Category.objects.acreate(
            name=data.name,
            description=data.description,
            parent_id=data.parent_id,
        )
        return CategoryResponse.model_validate(cat)

    @jwt_required
    async def update_category(
        self, request, slug: str, data: CategoryUpdate
    ) -> CategoryResponse:
        if not request.user.is_staff:
            raise ForbiddenAPIError("Only staff can update categories.")
        cat = await Category.objects.filter(slug=slug).afirst()
        if cat is None:
            raise NotFoundAPIError(f"Category '{slug}' not found.")
        if data.name is not None:
            cat.name = data.name
        if data.description is not None:
            cat.description = data.description
        if data.parent_id is not None:
            cat.parent_id = data.parent_id
        await cat.asave()
        return CategoryResponse.model_validate(cat)

    @jwt_required
    async def delete_category(self, request, slug: str) -> dict:
        if not request.user.is_staff:
            raise ForbiddenAPIError("Only staff can delete categories.")
        deleted, _ = await Category.objects.filter(slug=slug).adelete()
        if not deleted:
            raise NotFoundAPIError(f"Category '{slug}' not found.")
        return {"deleted": True}


class PostController(APIController):
    prefix = "/posts"
    tags = ["Posts"]

    @staticmethod
    async def list_posts(
        category: str | None = None,
        tag: str | None = None,
        author: str | None = None,
        featured: bool | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedPostsResponse:
        """List published posts with optional filters."""
        page_size = min(page_size, 50)
        posts, total = await get_published_posts(
            category_slug=category,
            tag_slug=tag,
            author_username=author,
            featured=featured,
            page=page,
            page_size=page_size,
        )
        return PaginatedPostsResponse(
            items=[PostListResponse.model_validate(p) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @staticmethod
    async def get_post(slug: str, request) -> PostDetailResponse:
        """Get a single published post by slug and record the view."""
        post = await get_post_by_slug(slug)
        if post is None or post.status != "published":
            raise NotFoundAPIError(f"Post '{slug}' not found.")

        session_key = getattr(request.session, "session_key", "") or ""
        ip = request.META.get("REMOTE_ADDR")
        await record_view(post, session_key=session_key, ip_address=ip)

        return PostDetailResponse.model_validate(post)

    @staticmethod
    async def get_post_seo(slug: str) -> SEOMetaResponse:
        """Return SEO metadata for a post (used by frontend for meta tags)."""
        post = await get_post_by_slug(slug)
        if post is None or post.status != "published":
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        return SEOMetaResponse(**get_seo_meta(post))

    @staticmethod
    async def search(q: str, page: int = 1, page_size: int = 10) -> PaginatedPostsResponse:
        """Full-text search across posts."""
        if not q or len(q.strip()) < 2:
            raise ValidationAPIError("Search query must be at least 2 characters.")
        page_size = min(page_size, 50)
        posts, total = await search_posts(q.strip(), page=page, page_size=page_size)
        return PaginatedPostsResponse(
            items=[PostListResponse.model_validate(p) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @jwt_required
    async def create_post(self, request, data: PostCreate) -> PostDetailResponse:
        """Create a new post. Author is set to the authenticated user."""
        post = await Post.objects.acreate(
            title=data.title,
            content=data.content,
            excerpt=data.excerpt,
            status=data.status,
            featured=data.featured,
            author=request.user,
            category_id=data.category_id,
            seo_title=data.seo_title,
            seo_description=data.seo_description,
            published_at=data.published_at
            or (timezone.now() if data.status == "published" else None),
        )
        if data.tag_ids:
            await post.tags.aset(await _resolve_tags(data.tag_ids))

        return await _fetch_post_detail(post.id)

    @jwt_required
    async def update_post(self, request, slug: str, data: PostUpdate) -> PostDetailResponse:
        """Update a post. Authors can only edit their own; staff can edit any."""
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise ForbiddenAPIError("You don't have permission to edit this post.")

        fields = []
        if data.title is not None:
            post.title = data.title
            fields.append("title")
        if data.content is not None:
            post.content = data.content
            fields.append("content")
        if data.excerpt is not None:
            post.excerpt = data.excerpt
            fields.append("excerpt")
        if data.featured is not None:
            post.featured = data.featured
            fields.append("featured")
        if data.category_id is not None:
            post.category_id = data.category_id
            fields.append("category_id")
        if data.seo_title is not None:
            post.seo_title = data.seo_title
            fields.append("seo_title")
        if data.seo_description is not None:
            post.seo_description = data.seo_description
            fields.append("seo_description")

        if data.status is not None and data.status != post.status:
            post.status = data.status
            fields.append("status")
            if data.status == "published" and post.published_at is None:
                post.published_at = data.published_at or timezone.now()
                fields.append("published_at")

        if fields:
            fields.append("updated_at")
            await post.asave(update_fields=fields)

        if data.tag_ids is not None:
            await post.tags.aset(await _resolve_tags(data.tag_ids))

        return await _fetch_post_detail(post.id)

    @jwt_required
    async def publish_post(self, request, slug: str) -> PostDetailResponse:
        """Publish a draft post."""
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise ForbiddenAPIError("You don't have permission to publish this post.")
        post = await publish_post(post)
        return await _fetch_post_detail(post.id)

    @jwt_required
    async def delete_post(self, request, slug: str) -> dict:
        """Delete a post. Authors can delete their own; staff can delete any."""
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise ForbiddenAPIError("You don't have permission to delete this post.")
        await post.adelete()
        return {"deleted": True}

    @jwt_required
    async def my_posts(
        self, request, status: str | None = None, page: int = 1, page_size: int = 10
    ) -> PaginatedPostsResponse:
        """Return the authenticated user's posts (all statuses)."""
        page_size = min(page_size, 50)
        qs = (
            Post.objects.filter(author=request.user)
            .select_related("author", "author__author_profile", "category")
            .prefetch_related("tags")
            .order_by("-created_at")
        )
        if status:
            qs = qs.filter(status=status)
        total = await qs.acount()
        offset = (page - 1) * page_size
        posts = [p async for p in qs[offset : offset + page_size]]
        return PaginatedPostsResponse(
            items=[PostListResponse.model_validate(p) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_tags(tag_ids: list[UUID]) -> list[Tag]:
    return [t async for t in Tag.objects.filter(id__in=tag_ids)]


async def _fetch_post_detail(post_id: UUID) -> PostDetailResponse:
    post = await (
        Post.objects.select_related("author", "author__author_profile", "category")
        .prefetch_related("tags")
        .aget(id=post_id)
    )
    return PostDetailResponse.model_validate(post)

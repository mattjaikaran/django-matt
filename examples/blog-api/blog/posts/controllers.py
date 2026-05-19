"""API controllers for posts, tags, and categories."""

import math
from uuid import UUID

from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import PermissionAPIError, NotFoundAPIError, ValidationAPIError
from django_matt.core.router import delete, get, patch, post

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
    serialize_post_list,
    serialize_post_detail,
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
    @get("/")
    async def list_tags() -> list[TagResponse]:
        return [TagResponse.model_validate(t) async for t in Tag.objects.all()]

    @staticmethod
    @get("/<str:slug>")
    async def get_tag(slug: str) -> TagResponse:
        tag = await Tag.objects.filter(slug=slug).afirst()
        if tag is None:
            raise NotFoundAPIError(f"Tag '{slug}' not found.")
        return TagResponse.model_validate(tag)

    @post("/")
    @jwt_required
    async def create_tag(self, request, data: TagCreate) -> TagResponse:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can create tags.")
        tag, _ = await Tag.objects.aget_or_create(
            name=data.name,
            defaults={"name": data.name},
        )
        return TagResponse.model_validate(tag)


class CategoryController(APIController):
    prefix = "/categories"
    tags = ["Categories"]

    @staticmethod
    @get("/")
    async def list_categories() -> list[CategoryResponse]:
        return [CategoryResponse.model_validate(c) async for c in Category.objects.all()]

    @staticmethod
    @get("/<str:slug>")
    async def get_category(slug: str) -> CategoryResponse:
        cat = await Category.objects.filter(slug=slug).afirst()
        if cat is None:
            raise NotFoundAPIError(f"Category '{slug}' not found.")
        return CategoryResponse.model_validate(cat)

    @post("/")
    @jwt_required
    async def create_category(self, request, data: CategoryCreate) -> CategoryResponse:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can create categories.")
        cat = await Category.objects.acreate(
            name=data.name,
            description=data.description,
            parent_id=data.parent_id,
        )
        return CategoryResponse.model_validate(cat)

    @patch("/<str:slug>")
    @jwt_required
    async def update_category(
        self, request, slug: str, data: CategoryUpdate
    ) -> CategoryResponse:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can update categories.")
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

    @delete("/<str:slug>")
    @jwt_required
    async def delete_category(self, request, slug: str) -> dict:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can delete categories.")
        deleted, _ = await Category.objects.filter(slug=slug).adelete()
        if not deleted:
            raise NotFoundAPIError(f"Category '{slug}' not found.")
        return {"deleted": True}


class PostController(APIController):
    prefix = "/posts"
    tags = ["Posts"]

    @staticmethod
    @get("/")
    async def list_posts(
        category: str | None = None,
        tag: str | None = None,
        author: str | None = None,
        featured: bool | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedPostsResponse:
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
            items=[serialize_post_list(p) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @staticmethod
    @get("/search")
    async def search(q: str, page: int = 1, page_size: int = 10) -> PaginatedPostsResponse:
        if not q or len(q.strip()) < 2:
            raise ValidationAPIError("Search query must be at least 2 characters.")
        page_size = min(page_size, 50)
        posts, total = await search_posts(q.strip(), page=page, page_size=page_size)
        return PaginatedPostsResponse(
            items=[serialize_post_list(p) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @get("/my")
    @jwt_required
    async def my_posts(
        self, request, status: str | None = None, page: int = 1, page_size: int = 10
    ) -> PaginatedPostsResponse:
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
            items=[serialize_post_list(p) for p in posts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @staticmethod
    @get("/<str:slug>")
    async def get_post(slug: str, request) -> PostDetailResponse:
        post = await get_post_by_slug(slug)
        if post is None or post.status != "published":
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        session_key = getattr(request.session, "session_key", "") or ""
        ip = request.META.get("REMOTE_ADDR")
        await record_view(post, session_key=session_key, ip_address=ip)
        return serialize_post_detail(post)

    @staticmethod
    @get("/<str:slug>/seo")
    async def get_post_seo(slug: str) -> SEOMetaResponse:
        post = await get_post_by_slug(slug)
        if post is None or post.status != "published":
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        return SEOMetaResponse(**get_seo_meta(post))

    @post("/")
    @jwt_required
    async def create_post(self, request, data: PostCreate) -> PostDetailResponse:
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

    @patch("/<str:slug>")
    @jwt_required
    async def update_post(self, request, slug: str, data: PostUpdate) -> PostDetailResponse:
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You don't have permission to edit this post.")

        fields = []
        for field in ("title", "content", "excerpt", "featured", "category_id", "seo_title", "seo_description"):
            val = getattr(data, field.replace("_id", ""), None) if field == "category_id" else getattr(data, field, None)
            if field == "category_id":
                val = data.category_id
            if val is not None:
                setattr(post, field, val)
                fields.append(field)

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

    @post("/<str:slug>/publish")
    @jwt_required
    async def publish_post_endpoint(self, request, slug: str) -> PostDetailResponse:
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You don't have permission to publish this post.")
        post = await publish_post(post)
        return await _fetch_post_detail(post.id)

    @delete("/<str:slug>")
    @jwt_required
    async def delete_post(self, request, slug: str) -> dict:
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You don't have permission to delete this post.")
        await post.adelete()
        return {"deleted": True}


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
    return serialize_post_detail(post)

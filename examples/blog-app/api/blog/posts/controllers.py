"""API controllers for posts, tags, and categories."""

import math
from uuid import UUID

from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionAPIError, ValidationAPIError
from django_matt.core.router import delete, get, patch, post

from blog.posts.models import Category, Post, Tag
from blog.posts.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    PaginatedPostsResponse,
    PostCreate,
    PostDetailResponse,
    PostUpdate,
    SEOMetaResponse,
    TagCreate,
    TagResponse,
    serialize_post_detail,
    serialize_post_list,
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

    @get("/")
    async def list_tags(self) -> list[TagResponse]:
        return [TagResponse.model_validate(t) async for t in Tag.objects.all()]

    @get("/<str:slug>")
    async def get_tag(self, slug: str) -> TagResponse:
        tag = await Tag.objects.filter(slug=slug).afirst()
        if tag is None:
            raise NotFoundAPIError(f"Tag '{slug}' not found.")
        return TagResponse.model_validate(tag)

    @post("/")
    @jwt_required
    async def create_tag(self, request, body: TagCreate) -> TagResponse:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can create tags.")
        tag, _ = await Tag.objects.aget_or_create(
            name=body.name,
            defaults={"name": body.name},
        )
        return TagResponse.model_validate(tag)


class CategoryController(APIController):
    prefix = "/categories"
    tags = ["Categories"]

    @get("/")
    async def list_categories(self) -> list[CategoryResponse]:
        return [CategoryResponse.model_validate(c) async for c in Category.objects.all()]

    @get("/<str:slug>")
    async def get_category(self, slug: str) -> CategoryResponse:
        cat = await Category.objects.filter(slug=slug).afirst()
        if cat is None:
            raise NotFoundAPIError(f"Category '{slug}' not found.")
        return CategoryResponse.model_validate(cat)

    @post("/")
    @jwt_required
    async def create_category(self, request, body: CategoryCreate) -> CategoryResponse:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can create categories.")
        cat = await Category.objects.acreate(
            name=body.name,
            description=body.description,
            parent_id=body.parent_id,
        )
        return CategoryResponse.model_validate(cat)

    @patch("/<str:slug>")
    @jwt_required
    async def update_category(self, request, slug: str, body: CategoryUpdate) -> CategoryResponse:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can update categories.")
        cat = await Category.objects.filter(slug=slug).afirst()
        if cat is None:
            raise NotFoundAPIError(f"Category '{slug}' not found.")
        if body.name is not None:
            cat.name = body.name
        if body.description is not None:
            cat.description = body.description
        if body.parent_id is not None:
            cat.parent_id = body.parent_id
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

    @get("/")
    async def list_posts(
        self,
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

    @get("/search")
    async def search(self, request, page: int = 1, page_size: int = 10) -> PaginatedPostsResponse:
        q = request.GET.get("q", "")
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

    @get("/<str:slug>")
    async def get_post(self, request, slug: str) -> PostDetailResponse:
        post = await get_post_by_slug(slug)
        if post is None or post.status != "published":
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        session_key = getattr(request.session, "session_key", "") or ""
        ip = request.META.get("REMOTE_ADDR")
        await record_view(post, session_key=session_key, ip_address=ip)
        return serialize_post_detail(post)

    @get("/<str:slug>/seo")
    async def get_post_seo(self, slug: str) -> SEOMetaResponse:
        post = await get_post_by_slug(slug)
        if post is None or post.status != "published":
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        return SEOMetaResponse(**get_seo_meta(post))

    @post("/")
    @jwt_required
    async def create_post(self, request, body: PostCreate) -> PostDetailResponse:
        post = await Post.objects.acreate(
            title=body.title,
            content=body.content,
            excerpt=body.excerpt,
            status=body.status,
            featured=body.featured,
            author=request.user,
            category_id=body.category_id,
            seo_title=body.seo_title,
            seo_description=body.seo_description,
            published_at=body.published_at
            or (timezone.now() if body.status == "published" else None),
        )
        if body.tag_ids:
            await post.tags.aset(await _resolve_tags(body.tag_ids))
        return await _fetch_post_detail(post.id)

    @patch("/<str:slug>")
    @jwt_required
    async def update_post(self, request, slug: str, body: PostUpdate) -> PostDetailResponse:
        post = await Post.objects.filter(slug=slug).afirst()
        if post is None:
            raise NotFoundAPIError(f"Post '{slug}' not found.")
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionAPIError("You don't have permission to edit this post.")

        fields = []
        for field in (
            "title",
            "content",
            "excerpt",
            "featured",
            "category_id",
            "seo_title",
            "seo_description",
        ):
            val = (
                getattr(body, field.replace("_id", ""), None)
                if field == "category_id"
                else getattr(body, field, None)
            )
            if field == "category_id":
                val = body.category_id
            if val is not None:
                setattr(post, field, val)
                fields.append(field)

        if body.status is not None and body.status != post.status:
            post.status = body.status
            fields.append("status")
            if body.status == "published" and post.published_at is None:
                post.published_at = body.published_at or timezone.now()
                fields.append("published_at")

        if fields:
            fields.append("updated_at")
            await post.asave(update_fields=fields)

        if body.tag_ids is not None:
            await post.tags.aset(await _resolve_tags(body.tag_ids))

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

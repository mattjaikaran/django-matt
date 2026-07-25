"""Pydantic schemas for posts app."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Tag schemas
# ---------------------------------------------------------------------------


class TagResponse(BaseModel):
    id: UUID
    name: str
    slug: str

    class Config:
        from_attributes = True


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Category schemas
# ---------------------------------------------------------------------------


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    parent_id: UUID | None = None

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    parent_id: UUID | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None


# ---------------------------------------------------------------------------
# Author (embedded in post responses)
# ---------------------------------------------------------------------------


class AuthorSummary(BaseModel):
    id: UUID
    username: str
    full_name: str
    avatar: str | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Post schemas
# ---------------------------------------------------------------------------


class PostListResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    excerpt: str
    cover_image_url: str | None = None
    author: AuthorSummary
    category: CategoryResponse | None = None
    tags: list[TagResponse] = []
    status: str
    featured: bool
    published_at: datetime | None = None
    view_count: int
    reading_time_minutes: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PostDetailResponse(PostListResponse):
    content: str
    seo_title: str
    seo_description: str


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    excerpt: str = ""
    status: str = "draft"
    featured: bool = False
    category_id: UUID | None = None
    tag_ids: list[UUID] = []
    seo_title: str = ""
    seo_description: str = ""
    published_at: datetime | None = None


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    excerpt: str | None = None
    status: str | None = None
    featured: bool | None = None
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    published_at: datetime | None = None


class PaginatedPostsResponse(BaseModel):
    items: list[PostListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SEOMetaResponse(BaseModel):
    title: str
    description: str
    og_title: str
    og_description: str
    og_image: str | None = None
    canonical_url: str
    published_at: datetime | None = None
    author: str


def serialize_post_list(post) -> PostListResponse:
    """Serialize a Post ORM object, resolving M2M tags from prefetch cache."""
    cache = getattr(post, "_prefetched_objects_cache", {})
    tags = list(cache.get("tags", []))
    return PostListResponse.model_validate({
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "excerpt": post.excerpt,
        "cover_image_url": post.cover_image.url if post.cover_image else None,
        "author": post.author,
        "category": post.category,
        "tags": tags,
        "status": post.status,
        "featured": post.featured,
        "published_at": post.published_at,
        "view_count": post.view_count,
        "reading_time_minutes": post.reading_time_minutes,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    })


def serialize_post_detail(post) -> "PostDetailResponse":
    """Serialize a Post ORM object to detail schema, resolving M2M tags."""
    cache = getattr(post, "_prefetched_objects_cache", {})
    tags = list(cache.get("tags", []))
    return PostDetailResponse.model_validate({
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "excerpt": post.excerpt,
        "cover_image_url": post.cover_image.url if post.cover_image else None,
        "author": post.author,
        "category": post.category,
        "tags": tags,
        "status": post.status,
        "featured": post.featured,
        "published_at": post.published_at,
        "view_count": post.view_count,
        "reading_time_minutes": post.reading_time_minutes,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "content": post.content,
        "seo_title": post.seo_title,
        "seo_description": post.seo_description,
    })

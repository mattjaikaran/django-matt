from ninja import Schema
from pydantic import Field


class TagSchema(Schema):
    name: str
    slug: str

    class Config:
        from_attributes = True


class PostListSchema(Schema):
    id: str
    title: str
    slug: str
    excerpt: str | None = None
    featured: bool
    author_name: str
    tags: list[TagSchema] = []
    published_at: str | None = None

    class Config:
        from_attributes = True


class PostDetailSchema(PostListSchema):
    content: str
    status: str
    created_at: str
    updated_at: str


class PostCreateSchema(Schema):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    excerpt: str | None = None
    status: str = "draft"
    featured: bool = False
    tag_names: list[str] = []


class PostUpdateSchema(Schema):
    title: str | None = None
    content: str | None = None
    excerpt: str | None = None
    status: str | None = None
    featured: bool | None = None
    tag_names: list[str] | None = None


class PaginatedPosts(Schema):
    items: list[PostListSchema]
    total: int
    page: int
    page_size: int
    total_pages: int

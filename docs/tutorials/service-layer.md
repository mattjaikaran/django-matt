# Service Layer Deep Dive

This tutorial builds a complete service layer for a blog application, step by step. By the end you will have a `PostService` with custom business methods, event emission, caching, tests, and a thin controller wired on top.

## Prerequisites

- A Django project with django-matt installed
- A basic understanding of async/await in Django
- A database configured and `migrate` run

## 1. Define the Model

```python
# blog/models.py
from django.conf import settings
from django.db import models

class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        PUBLISHED = "published"
        ARCHIVED = "archived"

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status, default=Status.DRAFT)
    featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
```

## 2. Create the CRUDService Subclass

```python
# blog/services.py
from __future__ import annotations

from django.utils import timezone
from django_matt.services import CRUDService, ValidationError, ConflictError

from .models import Post


class PostService(CRUDService["Post"]):
    model = Post

    def get_queryset(self):
        return super().get_queryset().select_related("created_by")
```

This gives you `get()`, `get_or_none()`, `get_by()`, `exists()`, `count()`, `list()`, `all()`, `create()`, `update()`, `update_fields()`, `delete()`, `bulk_create()`, `bulk_update()`, and `bulk_delete()` — all async, all respecting `get_queryset()`.

## 3. Add Custom Business Methods

Business logic goes here, not in the controller.

```python
class PostService(CRUDService["Post"]):
    model = Post

    def get_queryset(self):
        return super().get_queryset().select_related("created_by")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def publish(self, pk: int, user) -> Post:
        """Transition a draft post to published."""
        post = await self.get(pk)
        if post.status == Post.Status.PUBLISHED:
            raise ConflictError(f"Post {pk} is already published")
        if post.status == Post.Status.ARCHIVED:
            raise ValidationError("Cannot publish an archived post")
        return await self.update(pk, {
            "status": Post.Status.PUBLISHED,
            "published_at": timezone.now(),
        }, user=user)

    async def archive(self, pk: int, user) -> Post:
        """Archive a post (removes it from public listings)."""
        return await self.update_fields(pk, status=Post.Status.ARCHIVED, user=user)

    async def list_published(self, *, page: int = 1, page_size: int = 20):
        """Public listing of published posts, newest first."""
        return await self.list(
            page=page,
            page_size=page_size,
            status=Post.Status.PUBLISHED,
            ordering="-published_at",
        )

    async def get_by_slug(self, slug: str) -> Post:
        """Fetch a published post by slug."""
        return await self.get_by(slug=slug, status=Post.Status.PUBLISHED)

    async def get_featured(self) -> list[Post]:
        """Return all featured published posts."""
        return await self.all(featured=True, status=Post.Status.PUBLISHED)

    async def feature(self, pk: int, user) -> Post:
        """Mark a published post as featured."""
        post = await self.get(pk)
        if post.status != Post.Status.PUBLISHED:
            raise ValidationError("Only published posts can be featured")
        return await self.update_fields(pk, featured=True, user=user)
```

## 4. Wire Into a Controller

The controller is a thin HTTP adapter. Each method is 1-3 lines.

```python
# blog/controllers.py
from django_matt.core import APIController
from django_matt.permissions import IsAuthenticated
from .schemas import PostCreateSchema, PostUpdateSchema
from .services import PostService

@api.controller("/posts", tags=["Blog"])
class PostController(APIController):
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.service = PostService()
        super().__init__()

    # -- Public (read) endpoints --

    @api.get("/")
    async def list_posts(self, request, page: int = 1, page_size: int = 20):
        items, total = await self.service.list_published(page=page, page_size=page_size)
        return {"items": items, "total": total, "page": page}

    @api.get("/featured")
    async def featured_posts(self, request):
        return await self.service.get_featured()

    @api.get("/{slug}")
    async def get_post(self, request, slug: str):
        return await self.service.get_by_slug(slug)

    # -- Author (write) endpoints --

    @api.post("/")
    async def create_post(self, request, data: PostCreateSchema):
        return await self.service.create(data.model_dump(), user=request.user)

    @api.patch("/{id}")
    async def update_post(self, request, id: int, data: PostUpdateSchema):
        return await self.service.update(id, data.model_dump(), user=request.user, partial=True)

    @api.post("/{id}/publish")
    async def publish_post(self, request, id: int):
        return await self.service.publish(id, user=request.user)

    @api.post("/{id}/archive")
    async def archive_post(self, request, id: int):
        return await self.service.archive(id, user=request.user)

    @api.post("/{id}/feature")
    async def feature_post(self, request, id: int):
        return await self.service.feature(id, user=request.user)

    @api.delete("/{id}")
    async def delete_post(self, request, id: int):
        await self.service.delete(id, user=request.user)
        return {"deleted": True}
```

## 5. Add Event Emission

Emit domain events after important mutations so other modules can react.

```python
# blog/events.py
from django_matt.events.bus import Event

class PostPublished(Event):
    __event_type__ = "post.published"
    post_id: int
    slug: str
    author_id: int

class PostArchived(Event):
    __event_type__ = "post.archived"
    post_id: int
```

Update the service to emit after mutations:

```python
# blog/services.py (updated publish method)
from django_matt.events.bus import get_event_bus
from .events import PostPublished, PostArchived

class PostService(CRUDService["Post"]):
    # ... get_queryset, other methods unchanged ...

    async def publish(self, pk: int, user) -> Post:
        post = await self.get(pk)
        if post.status == Post.Status.PUBLISHED:
            raise ConflictError(f"Post {pk} is already published")
        if post.status == Post.Status.ARCHIVED:
            raise ValidationError("Cannot publish an archived post")

        post = await self.update(pk, {
            "status": Post.Status.PUBLISHED,
            "published_at": timezone.now(),
        }, user=user)

        await get_event_bus().emit(PostPublished(
            post_id=post.pk,
            slug=post.slug,
            author_id=post.created_by_id,
        ))
        return post

    async def archive(self, pk: int, user) -> Post:
        post = await self.update_fields(pk, status=Post.Status.ARCHIVED, user=user)
        await get_event_bus().emit(PostArchived(post_id=post.pk))
        return post
```

## 6. Add Caching

Cache expensive read operations. Invalidate on writes.

```python
from django.core.cache import cache

class PostService(CRUDService["Post"]):
    # ... other methods ...

    FEATURED_CACHE_KEY = "posts:featured"
    FEATURED_CACHE_TTL = 300  # 5 minutes

    async def get_featured(self) -> list[Post]:
        cached = cache.get(self.FEATURED_CACHE_KEY)
        if cached is not None:
            return cached
        posts = await self.all(featured=True, status=Post.Status.PUBLISHED)
        cache.set(self.FEATURED_CACHE_KEY, posts, self.FEATURED_CACHE_TTL)
        return posts

    async def feature(self, pk: int, user) -> Post:
        post = await self.get(pk)
        if post.status != Post.Status.PUBLISHED:
            raise ValidationError("Only published posts can be featured")
        result = await self.update_fields(pk, featured=True, user=user)
        cache.delete(self.FEATURED_CACHE_KEY)  # invalidate
        return result
```

## 7. Test the Service

Test services directly against the database. No HTTP overhead, no mocking the DB.

```python
# blog/tests/test_services.py
import pytest
from django.utils import timezone
from django_matt.services import ConflictError, NotFoundError, ValidationError

from blog.models import Post
from blog.services import PostService


@pytest.fixture
def service():
    return PostService()


@pytest.fixture
async def draft_post(db, user):
    return await Post.objects.acreate(
        title="Test Post",
        slug="test-post",
        body="Hello world",
        status=Post.Status.DRAFT,
        created_by=user,
    )


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_create_post(service, user):
    post = await service.create(
        {"title": "New Post", "slug": "new-post", "body": "Content"},
        user=user,
    )
    assert post.pk is not None
    assert post.created_by == user
    assert post.status == Post.Status.DRAFT


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_publish_sets_published_at(service, draft_post, user):
    post = await service.publish(draft_post.pk, user=user)
    assert post.status == Post.Status.PUBLISHED
    assert post.published_at is not None


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_publish_already_published_raises(service, draft_post, user):
    await service.publish(draft_post.pk, user=user)
    with pytest.raises(ConflictError, match="already published"):
        await service.publish(draft_post.pk, user=user)


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_publish_archived_raises(service, draft_post, user):
    await service.archive(draft_post.pk, user=user)
    with pytest.raises(ValidationError, match="archived"):
        await service.publish(draft_post.pk, user=user)


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_not_found(service):
    with pytest.raises(NotFoundError):
        await service.get(999999)


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_list_published_excludes_drafts(service, user):
    await service.create(
        {"title": "Draft", "slug": "draft", "body": "..."},
        user=user,
    )
    published = await service.create(
        {"title": "Live", "slug": "live", "body": "..."},
        user=user,
    )
    await service.publish(published.pk, user=user)

    items, total = await service.list_published()
    assert total == 1
    assert items[0].slug == "live"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_event_emitted_on_publish(service, draft_post, user):
    from django_matt.events.bus import get_event_bus, reset_event_bus

    reset_event_bus()
    bus = get_event_bus()
    received = []
    bus.subscribe("post.published", lambda e: received.append(e))

    await service.publish(draft_post.pk, user=user)

    assert len(received) == 1
    assert received[0].post_id == draft_post.pk
```

## 8. The generate_crud Shortcut

For new apps, skip the boilerplate entirely:

```bash
python manage.py generate_crud blog.Post --full
```

This generates:
- `blog/services.py` — `PostService(CRUDService["Post"])` with `get_queryset()` stub
- `blog/controllers.py` — thin controller wired to the service
- `blog/schemas.py` — Pydantic create/update/response schemas
- `blog/admin.py` — Django Unfold admin registration
- `blog/tests/` — test stubs for service and controller

Then add your domain methods to the generated service.

## Summary

| Layer | Responsibility | Knows about HTTP? |
|-------|---------------|-------------------|
| Schema | Input/output shape, validation | No |
| Controller | Parse request, call service, format response | Yes |
| Service | Business logic, DB operations, events | No |
| Model | Data persistence, constraints | No |

The service is the only place where business rules live. Controllers stay thin. Models stay dumb. This makes the logic testable without HTTP, reusable from management commands and Celery tasks, and easy to reason about.

## See Also

- [Service Layer Overview](../services/index.md)
- [CRUDService API Reference](../services/crud-service.md)
- [Service Patterns](../services/patterns.md)
- [Migration Guide](../services/migration.md)
- [Events](../events/overview.md)
- [CQRS](../cqrs/overview.md)

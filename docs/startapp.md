# startapp — Package-Based App Scaffolding

Django Matt overrides Django's built-in `startapp` command to enforce a **modular, package-based** directory structure from day one. No more 2000-line `models.py` files.

## Philosophy

> **Every file stays small. Every concern gets its own module.**

Django's default `startapp` creates flat files (`models.py`, `admin.py`, `views.py`) that inevitably become monolithic as your app grows. Django Matt replaces this with a package-based layout where each model, schema, controller, admin config, service, test, and factory lives in its own file.

This is the same convention used by Rails generators — each resource gets its own set of files, organized by purpose.

## Quick Start

```bash
# Create an app with default model derived from app name
python manage.py startapp blog

# Create an app with specific models
python manage.py startapp blog --models Post Comment

# Preview without writing files
python manage.py startapp blog --models Post Comment --dry-run

# Skip the service layer
python manage.py startapp blog --models Post --no-service
```

Or via Make:

```bash
make startapp NAME=blog
make startapp NAME=blog MODELS="Post Comment"
```

## Generated Structure

Running `python manage.py startapp blog --models Post Comment` produces:

```
blog/
├── __init__.py              # App init (from Django)
├── apps.py                  # App config (from Django)
├── urls.py                  # API router with controllers registered
├── models/
│   ├── __init__.py          # from blog.models.post import Post; ...
│   ├── post.py              # Post model (UUID pk, timestamps)
│   └── comment.py           # Comment model
├── schemas/
│   ├── __init__.py          # Auto-imports all schemas
│   ├── post_schema.py       # PostSchema, PostCreateSchema, PostUpdateSchema
│   └── comment_schema.py    # CommentSchema, CommentCreateSchema, CommentUpdateSchema
├── controllers/
│   ├── __init__.py          # Auto-imports all controllers
│   ├── post_controller.py   # Async CRUD controller
│   └── comment_controller.py
├── admin/
│   ├── __init__.py          # Auto-imports all admin classes
│   ├── post_admin.py        # @admin.register with ModelAdmin
│   └── comment_admin.py
├── services/
│   ├── __init__.py          # Auto-imports all services
│   ├── post_service.py      # Business logic (async)
│   └── comment_service.py
├── tests/
│   ├── __init__.py
│   ├── test_post.py         # pytest model + API test stubs
│   ├── test_comment.py
│   └── factories/
│       ├── __init__.py      # Auto-imports all factories
│       ├── post_factory.py  # Factory Boy factory
│       └── comment_factory.py
├── utils/
│   └── __init__.py
└── management/
    └── commands/
        └── __init__.py
```

## Command Options

| Option | Description |
|--------|-------------|
| `name` | App name (positional, required) |
| `--models` / `-m` | Model names to scaffold (space-separated) |
| `--no-service` | Skip generating the service layer |
| `--dry-run` | Preview files without writing |
| `--directory` | Target directory (inherited from Django) |

## What Gets Generated

### Model (`models/post.py`)

UUID primary key, timestamps, `__str__`, Meta with ordering:

```python
import uuid
from django.db import models


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Post"
        verbose_name_plural = "Posts"
```

### Schema (`schemas/post_schema.py`)

Pydantic v2 schemas for read, create, and partial update:

```python
import datetime
import uuid
from typing import Optional
from pydantic import Field
from django_matt.core.schema import Schema


class PostSchema(Schema):
    id: uuid.UUID
    title: str
    description: str
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class PostCreateSchema(Schema):
    title: str = Field(..., max_length=255)
    description: str = ""


class PostUpdateSchema(Schema):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
```

### Controller (`controllers/post_controller.py`)

Async CRUD with typed request/response:

```python
class PostController(CRUDController):
    prefix = "posts/"
    model = Post
    schema = PostSchema
    create_schema = PostCreateSchema
    update_schema = PostUpdateSchema

    @get("", response_model=PostSchema)
    async def list_posts(self, request): ...

    @get("{id}", response_model=PostSchema)
    async def get_post(self, request, id: str): ...

    @post("", response_model=PostSchema)
    async def create_post(self, request, data: PostCreateSchema): ...

    @put("{id}", response_model=PostSchema)
    async def update_post(self, request, id: str, data: PostUpdateSchema): ...

    @delete("{id}")
    async def delete_post(self, request, id: str): ...
```

### Service (`services/post_service.py`)

Async business logic layer with all ORM calls using async methods:

```python
class PostService:
    @staticmethod
    async def get_all() -> QuerySet:
        return Post.objects.all()

    @staticmethod
    async def get_by_id(post_id: uuid.UUID) -> Post:
        return await Post.objects.aget(id=post_id)

    @staticmethod
    async def create(data: PostCreateSchema) -> Post:
        return await Post.objects.acreate(**data.model_dump())

    @staticmethod
    async def update(post_id: uuid.UUID, data: PostUpdateSchema) -> Post:
        post = await Post.objects.aget(id=post_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(post, field, value)
        await post.asave()
        return post

    @staticmethod
    async def delete(post_id: uuid.UUID) -> None:
        post = await Post.objects.aget(id=post_id)
        await post.adelete()
```

### Admin (`admin/post_admin.py`)

```python
from django.contrib import admin
from blog.models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("title", "description")
    readonly_fields = ("id", "created_at", "updated_at")
```

### Factory (`tests/factories/post_factory.py`)

```python
import factory
from blog.models import Post


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("paragraph")
```

### Tests (`tests/test_post.py`)

```python
import pytest
from blog.models import Post
from blog.tests.factories import PostFactory


@pytest.mark.django_db
class TestPostModel:
    def test_create_post(self):
        post = PostFactory()
        assert post.pk is not None

    def test_post_str(self):
        post = PostFactory(title="Test Post")
        assert str(post) == "Test Post"

    def test_post_ordering(self):
        first = PostFactory(title="First")
        second = PostFactory(title="Second")
        posts = list(Post.objects.all())
        assert posts[0] == second  # Most recent first


@pytest.mark.django_db
class TestPostAPI:
    def test_list_posts(self):
        pass  # TODO: implement

    def test_create_post(self):
        pass  # TODO: implement
```

## Auto-Imports

Every `__init__.py` is pre-configured with correct imports so you can do:

```python
from blog.models import Post, Comment
from blog.schemas import PostSchema, PostCreateSchema
from blog.controllers import PostController
from blog.services import PostService
from blog.tests.factories import PostFactory
```

## After Creating an App

1. Add the app to `INSTALLED_APPS` in your settings
2. Run `python manage.py makemigrations blog`
3. Run `python manage.py migrate blog`
4. Add model-specific fields to the generated models
5. Use `generate_crud` to regenerate scaffolding if your model changes significantly

## The Two-Step Workflow

Django Matt follows a Rails-like scaffold approach:

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `python manage.py startapp blog` | Creates the package structure + default model |
| 2 | `python manage.py generate_crud blog.Post --full` | Regenerates schema/controller/admin/tests from the actual model fields |

**Step 1** sets up the skeleton. **Step 2** fills it with code that matches your real model fields after you've customized them.

See [Scaffolding Workflow](scaffolding.md) for the full guide.

See [CRUD Generator](crud-generator.md) for `generate_crud` options.

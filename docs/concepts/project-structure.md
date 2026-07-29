# Project Structure

Django Matt projects follow a **modular, package-based architecture** inspired by the [django-ninja-boilerplate](https://github.com/mattjaikaran/django-ninja-boilerplate). Every Django app uses internal packages instead of monolithic files. This is the default and recommended way to build with Django Matt.

## Why Modular?

Django's default flat structure (`models.py`, `views.py`, `admin.py`) works for tutorials. It collapses at scale:

| Flat (anti-pattern) | Modular (Django Matt default) |
|---------------------|-------------------------------|
| `models.py` — 3,000 lines, 15 models | `models/` — one file per model, ~40 lines each |
| `views.py` — 2,000 lines | `controllers/` — one file per resource |
| `admin.py` — 800 lines | `admin/` — one file per model |
| `tests.py` — 1,500 lines | `tests/` — one test module per model |
| Merge conflicts on every PR | Clean diffs, files don't overlap |
| Can't find anything | Navigate by convention |

The `startapp` and `generate_crud` commands create this structure automatically. There is no path to a 3,000-line `views.py` — the package structure makes it structurally impossible.

## The Default App Structure

Every Django Matt app follows this layout. Create it with one command:

```bash
python manage.py startapp blog --models Post Comment Tag
```

```
blog/
├── __init__.py
├── apps.py                          # Django AppConfig
├── urls.py                          # URL patterns, controller registration
│
├── models/                          # Database layer
│   ├── __init__.py                  # Re-exports: from .post import Post
│   ├── post.py                      # Post model (~40 lines)
│   ├── comment.py                   # Comment model (~35 lines)
│   └── tag.py                       # Tag model (~25 lines)
│
├── schemas/                         # API contract (Pydantic v2)
│   ├── __init__.py                  # Re-exports all schemas
│   ├── post_schema.py               # PostSchema, CreatePostSchema, UpdatePostSchema
│   ├── comment_schema.py
│   └── tag_schema.py
│
├── controllers/                     # HTTP layer (thin adapters)
│   ├── __init__.py                  # Re-exports all controllers
│   ├── post_controller.py           # Post CRUD endpoints
│   ├── comment_controller.py
│   └── tag_controller.py
│
├── services/                        # Business logic
│   ├── __init__.py                  # Re-exports all services
│   ├── post_service.py              # PostService(CRUDService)
│   ├── comment_service.py
│   └── tag_service.py
│
├── admin/                           # Django admin configuration
│   ├── __init__.py
│   ├── post_admin.py
│   └── comment_admin.py
│
├── tests/                           # Tests (pytest + Factory Boy)
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures
│   ├── test_post.py                 # Post model + API tests
│   ├── test_comment.py
│   └── factories/
│       ├── __init__.py
│       ├── post_factory.py          # Factory Boy factory
│       └── comment_factory.py
│
├── management/                      # Custom Django commands
│   └── commands/
│       └── seed_blog.py
│
└── migrations/                      # Django migrations (auto-generated)
    └── __init__.py
```

## The Service Layer

The service layer is the core architectural pattern. Controllers are **thin HTTP adapters** — they parse requests, call services, and format responses. Services contain all business logic.

```
Request → Controller → Service → Model (ORM)
                  ↑            ↑
            HTTP concerns   Business logic
            Auth, parsing   Validation, queries, side effects
```

### Controller (thin — HTTP only)

```python
# blog/controllers/post_controller.py
from django_matt import APIController, get, post, patch, delete
from django_matt.permissions import IsAuthenticated
from blog.schemas import PostSchema, PostCreateSchema, PostUpdateSchema
from blog.services import PostService

@api.controller("/posts", tags=["Blog"])
class PostController(APIController):
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.service = PostService()

    @get("/")
    async def list_posts(self, request, page: int = 1):
        items, total = await self.service.list_published(page=page)
        return {"items": items, "total": total, "page": page}

    @get("/{slug}")
    async def get_post(self, request, slug: str):
        return await self.service.get_by_slug(slug)

    @post("/")
    async def create_post(self, request, data: PostCreateSchema):
        return await self.service.create(data.model_dump(), user=request.user)

    @patch("/{id}")
    async def update_post(self, request, id: int, data: PostUpdateSchema):
        return await self.service.update(id, data.model_dump(), user=request.user)

    @post("/{id}/publish")
    async def publish_post(self, request, id: int):
        return await self.service.publish(id, user=request.user)

    @delete("/{id}")
    async def delete_post(self, request, id: int):
        await self.service.delete(id, user=request.user)
        return {"deleted": True}
```

### Service (domain logic)

```python
# blog/services/post_service.py
from django.utils import timezone
from django_matt.services import CRUDService, ConflictError, ValidationError
from blog.models import Post

class PostService(CRUDService["Post"]):
    model = Post

    def get_queryset(self):
        return super().get_queryset().select_related("created_by")

    # Domain methods ----------------------------------------------------

    async def list_published(self, *, page: int = 1, page_size: int = 20):
        return await self.list(
            page=page, page_size=page_size,
            status=Post.Status.PUBLISHED,
            ordering="-published_at",
        )

    async def get_by_slug(self, slug: str) -> Post:
        return await self.get_by(slug=slug, status=Post.Status.PUBLISHED)

    async def publish(self, pk: int, user) -> Post:
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
        return await self.update_fields(pk, status=Post.Status.ARCHIVED, user=user)

    async def get_featured(self) -> list[Post]:
        return await self.all(featured=True, status=Post.Status.PUBLISHED)
```

### Why This Pattern?

| Benefit | Without Service Layer | With Service Layer |
|---------|----------------------|-------------------|
| **Testability** | Must test through HTTP client | Test service directly against DB |
| **Reusability** | Logic locked in controller | Same service works in tasks, commands, WebSockets |
| **Reviewability** | Business logic interleaved with HTTP | Domain logic isolated, easy to review |
| **Swapability** | Can't replace without rewriting | Inject mock or alternative implementation |

## Naming Conventions

Consistency across every Django Matt project:

### Files

| What | Naming | Example |
|------|--------|---------|
| Model | `{model}.py` | `post.py` |
| Schema | `{model}_schema.py` | `post_schema.py` |
| Controller | `{model}_controller.py` | `post_controller.py` |
| Service | `{model}_service.py` | `post_service.py` |
| Admin | `{model}_admin.py` | `post_admin.py` |
| Test | `test_{model}.py` | `test_post.py` |
| Factory | `{model}_factory.py` | `post_factory.py` |

### Classes

| What | Naming | Example |
|------|--------|---------|
| Model | `PascalCase` | `Post`, `Comment` |
| Schema | `PascalCase` + `Schema` | `PostSchema`, `CreatePostSchema` |
| Controller | `PascalCase` + `Controller` | `PostController` |
| Service | `PascalCase` + `Service` | `PostService` |
| Factory | `PascalCase` + `Factory` | `PostFactory` |

### URLs

| What | Pattern | Example |
|------|---------|---------|
| Collection | Plural noun | `/posts` |
| Resource | `/{resource_id}` | `/posts/{post_id}` |
| Action | Verb or noun | `/posts/{id}/publish` |
| Nested | `/{parent}/{id}/{child}` | `/users/{user_id}/posts` |

### Module Exports

Always export public classes in `__init__.py`:

```python
# models/__init__.py
from .post import Post
from .comment import Comment

__all__ = ["Post", "Comment"]
```

This keeps imports clean — consumers import from the package, not the file:

```python
# Good
from blog.models import Post
from blog.services import PostService

# Bad (brittle, bypasses __init__)
from blog.models.post import Post
```

## File Size Limits

Enforced by convention and checked by CI:

| File type | Max lines |
|-----------|-----------|
| Model | 100 |
| Schema | 150 |
| Controller | 200 |
| Service | 300 |
| Test | 400 |

If a file exceeds these limits, split it. Large files signal mixed responsibilities.

## Adding a New Model

After initial scaffolding, add new models without re-running `startapp`:

```bash
# 1. Create the model file
touch blog/models/category.py

# 2. Write your model class

# 3. Export it in blog/models/__init__.py:
#    from .category import Category

# 4. Create and run migrations
python manage.py makemigrations blog && python manage.py migrate

# 5. Generate everything from the real model
python manage.py generate_crud blog.Category --full
```

## The Two-Step Workflow

1. **`startapp`** — creates the package skeleton with starter files
2. **`generate_crud --full`** — regenerates schema, controller, service, admin, and tests from your actual model fields

```bash
# Step 1: Create structure
python manage.py startapp blog --models Post Comment Tag

# Step 2: Edit models to add real fields

# Step 3: Migrate
python manage.py makemigrations blog && python manage.py migrate

# Step 4: Regenerate from real models
python manage.py generate_crud blog.Post --full
python manage.py generate_crud blog.Comment --full
```

## Project-Level Architecture

At the project level, Django Matt supports several architectures:

### API-Only (Most Common)

```
myproject/
├── config/              # Django settings, ASGI config
├── apps/
│   ├── core/            # Users, auth, base models
│   ├── blog/            # Blog domain
│   ├── products/        # Product domain
│   └── orders/          # Order domain
├── frontend/            # Separate React/Next.js app
└── manage.py
```

### Monorepo

```
myproject/
├── server/              # Django API
│   ├── config/
│   └── apps/
├── web/                 # Next.js frontend
├── mobile/              # React Native / Swift
├── docs/                # API documentation
└── shared/              # Shared types, configs
```

### B2B SaaS (Multi-Tenant)

```
myproject/
├── config/
├── apps/
│   ├── core/            # Users, auth
│   ├── organizations/   # Tenant management
│   ├── billing/         # Stripe subscriptions
│   └── dashboard/       # Tenant-specific features
└── manage.py
```

Create B2B projects with one command:

```bash
python manage.py startapi myproject --template b2b --auth jwt --docker
```

## See Also

- [Architecture](../architecture.md) — framework architecture and design philosophy
- [Best Practices](../best-practices.md) — anti-patterns and code organization
- [Scaffolding Workflow](../scaffolding.md) — `startapp` and `generate_crud` in detail
- [Service Layer Tutorial](../tutorials/service-layer.md) — build a complete service with events and caching
- [Build a REST API](../tutorials/build-a-rest-api.md) — full tutorial from zero to production

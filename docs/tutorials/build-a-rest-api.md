# Build a REST API in 10 Minutes

Build a fully-featured blog API with CRUD endpoints, JWT authentication,
pagination, and filtering -- all backed by automatic Swagger documentation.

## Prerequisites

- Python 3.12+
- PostgreSQL running locally (or SQLite for quick experimentation)
- Basic Django knowledge

## 1. Create the Project

```bash
# Install django-matt
uv add django-matt

# Scaffold a new project
python manage.py startapi blog --template default --auth jwt
```

This generates a Django project with `django_matt` wired into
`INSTALLED_APPS`, JWT middleware configured, and an `api.py` ready to go.

If you already have a Django project, add `"django_matt"` to
`INSTALLED_APPS` and create `api.py` at the project root:

```python
# api.py
from django_matt import MattAPI

api = MattAPI(
    title="Blog API",
    version="1.0.0",
    description="A blog REST API built with Django Matt",
)
```

Wire it into `urls.py`:

```python
# urls.py
from django.urls import path, include
from .api import api

urlpatterns = [
    path("api/", include(api.urls)),
]
```

Visit `http://localhost:8000/api/docs` to see the Swagger UI.

## 2. Define the Post Model

```python
# blog/models.py
import uuid
from django.conf import settings
from django.db import models


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    body = models.TextField()
    published = models.BooleanField(default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title
```

Run migrations:

```bash
python manage.py makemigrations blog
python manage.py migrate
```

## 3. Create Pydantic Schemas

`ModelSchema` introspects the Django model and generates Pydantic fields
automatically.  Use `Config.include` to pick fields, or `Config.exclude`
to drop them.

```python
# blog/schemas.py
from django_matt.core.schema import ModelSchema
from blog.models import Post


class PostSchema(ModelSchema):
    """Read schema -- returned in responses."""

    class Config:
        model = Post
        include = [
            "id", "title", "slug", "body",
            "published", "author", "created_at", "updated_at",
        ]


class PostCreateSchema(ModelSchema):
    """Write schema -- used for create/update requests."""

    class Config:
        model = Post
        include = ["title", "slug", "body", "published"]
        optional = ["published"]  # default False from model


class PostUpdateSchema(ModelSchema):
    """Partial update schema -- all fields optional."""

    class Config:
        model = Post
        include = ["title", "slug", "body", "published"]
        optional = "__all__"
```

Key points:

- `ModelSchema` reads `_meta.fields` and maps Django field types to Python
  types via `FIELD_TYPE_MAP` (e.g. `UUIDField -> uuid.UUID`,
  `DateTimeField -> datetime.datetime`).
- `Config.optional = "__all__"` makes every field `Optional[T]` with a
  `None` default -- perfect for PATCH schemas.
- ForeignKey fields become `int` (the PK) by default. Set
  `Config.model_fk_use_pks = True` to use the `_id` column name instead.

## 4. Create a Controller

A `Controller` groups related endpoints under a URL prefix. Methods
decorated with `@api.get`, `@api.post`, etc. become routes.

```python
# blog/controllers.py
from django.http import HttpRequest
from django_matt.core.controller import Controller
from django_matt.permissions import IsAuthenticated
from blog.models import Post
from blog.schemas import PostSchema, PostCreateSchema, PostUpdateSchema
from .api import api


@api.controller("/posts", tags=["Posts"])
class PostController(Controller):
    """Blog post CRUD endpoints."""

    @api.get("/")
    async def list_posts(self, request: HttpRequest):
        posts = []
        async for post in Post.objects.select_related("author").all():
            posts.append(PostSchema.from_orm(post))
        return {"items": [p.model_dump() for p in posts]}

    @api.get("/{post_id}")
    async def get_post(self, request: HttpRequest, post_id: str):
        post = await Post.objects.select_related("author").aget(id=post_id)
        return PostSchema.from_orm(post).model_dump()

    @api.post("/")
    async def create_post(self, request: HttpRequest, data: PostCreateSchema):
        post = await Post.objects.acreate(
            **data.model_dump(),
            author=request.user,
        )
        return PostSchema.from_orm(post).model_dump()

    @api.put("/{post_id}")
    async def update_post(
        self, request: HttpRequest, post_id: str, data: PostCreateSchema
    ):
        post = await Post.objects.aget(id=post_id)
        for field, value in data.model_dump().items():
            setattr(post, field, value)
        await post.asave()
        return PostSchema.from_orm(post).model_dump()

    @api.patch("/{post_id}")
    async def patch_post(
        self, request: HttpRequest, post_id: str, data: PostUpdateSchema
    ):
        post = await Post.objects.aget(id=post_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(post, field, value)
        await post.asave()
        return PostSchema.from_orm(post).model_dump()

    @api.delete("/{post_id}")
    async def delete_post(self, request: HttpRequest, post_id: str):
        post = await Post.objects.aget(id=post_id)
        await post.adelete()
        return {"success": True}
```

The controller auto-parses JSON bodies with `orjson` and validates
`PostCreateSchema` / `PostUpdateSchema` via Pydantic. Validation errors
return a `422` with structured error details.

## 5. Run and Test

```bash
python manage.py runserver
```

### Create a post

```bash
http POST http://localhost:8000/api/posts/ \
    title="Hello World" \
    slug="hello-world" \
    body="My first post" \
    Authorization:"Bearer <token>"
```

Expected response:

```json
{
    "id": "a1b2c3d4-...",
    "title": "Hello World",
    "slug": "hello-world",
    "body": "My first post",
    "published": false,
    "author": 1,
    "created_at": "2026-04-06T12:00:00Z",
    "updated_at": "2026-04-06T12:00:00Z"
}
```

### List posts

```bash
http GET http://localhost:8000/api/posts/
```

### Update a post

```bash
http PATCH http://localhost:8000/api/posts/a1b2c3d4-.../ \
    published:=true \
    Authorization:"Bearer <token>"
```

### Delete a post

```bash
http DELETE http://localhost:8000/api/posts/a1b2c3d4-.../ \
    Authorization:"Bearer <token>"
```

## 6. Add JWT Authentication

Django Matt ships a zero-dependency JWT implementation.  Configure it in
`settings.py`:

```python
# settings.py
from datetime import timedelta

DJANGO_MATT_JWT = {
    "SECRET_KEY": SECRET_KEY,            # defaults to Django SECRET_KEY
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "sub",
    "AUTH_HEADER_TYPES": ["Bearer"],
}

MIDDLEWARE = [
    # ... existing middleware ...
    "django_matt.auth.middleware.JWTAuthenticationMiddlewareAsync",
]
```

Add the built-in auth controller for login/register/refresh:

```python
# api.py
from django_matt.auth import AuthController

api.register_controller(AuthController, prefix="/auth")
```

This gives you:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Returns access + refresh tokens |
| `/api/auth/register` | POST | Create account, returns tokens |
| `/api/auth/refresh` | POST | Refresh an access token |
| `/api/auth/me` | GET | Current user profile |

Protect your controller with `permission_classes`:

```python
from django_matt.permissions import IsAuthenticated

@api.controller("/posts", tags=["Posts"])
class PostController(Controller):
    permission_classes = [IsAuthenticated]
    # ... all methods now require a valid JWT
```

Or protect individual methods with decorators:

```python
from django_matt.auth import jwt_required, jwt_optional

@api.controller("/posts", tags=["Posts"])
class PostController(Controller):

    @api.get("/")
    @jwt_optional
    async def list_posts(self, request: HttpRequest):
        """Public -- anonymous users see published posts only."""
        qs = Post.objects.all()
        if not request.user.is_authenticated:
            qs = qs.filter(published=True)
        ...

    @api.post("/")
    @jwt_required
    async def create_post(self, request: HttpRequest, data: PostCreateSchema):
        ...
```

## 7. Add Pagination and Filtering

### Using the ViewSet pattern

For standard CRUD with pagination and filtering, `APIViewSet` is more
concise than a hand-written controller:

```python
# blog/views.py
from django_matt.views import (
    APIViewSet,
    ListView,
    CreateView,
    ReadView,
    UpdateView,
    DeleteView,
)
from django_matt.pagination import PageNumberPagination
from blog.models import Post
from blog.schemas import PostSchema, PostCreateSchema, PostUpdateSchema
from .api import api


class PostViewSet(APIViewSet):
    api = api
    model = Post
    prefix = "/posts"
    tags = ["Posts"]
    default_response_schema = PostSchema
    default_request_schema = PostCreateSchema

    # Pagination
    pagination_class = PageNumberPagination

    # Filtering and search
    filter_fields = ["published", "author"]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "title"]
    ordering = "-created_at"

    # CRUD views
    list_posts = ListView(page_size=20, max_page_size=100)
    create_post = CreateView()
    read_post = ReadView()
    update_post = UpdateView(request_schema=PostUpdateSchema)
    delete_post = DeleteView()
```

`ListView` supports three pagination classes out of the box:

| Class | Query params | Notes |
|-------|-------------|-------|
| `PageNumberPagination` | `?page=2&page_size=20` | Offset-based |
| `LimitOffsetPagination` | `?limit=20&offset=40` | Offset-based |
| `CursorPagination` | `?cursor=<opaque>` | Keyset-based, no count |

### Query examples

```bash
# Page 2, 10 items per page
http GET "http://localhost:8000/api/posts/?page=2&page_size=10"

# Filter by published status
http GET "http://localhost:8000/api/posts/?published=true"

# Full-text search
http GET "http://localhost:8000/api/posts/?search=django"

# Order by title ascending
http GET "http://localhost:8000/api/posts/?ordering=title"
```

### Lifecycle hooks

ViewSets support before/after hooks for each operation:

```python
class PostViewSet(APIViewSet):
    # ...

    async def before_create(self, request, data):
        """Set author from authenticated user."""
        data["author_id"] = request.user.id
        return data

    async def after_create(self, request, instance):
        """Send notification after post is created."""
        # custom logic here
        return instance
```

## 8. Complete Code Listing

```python
# settings.py (additions)
from datetime import timedelta

INSTALLED_APPS = [
    # ...
    "django_matt",
    "blog",
]

MIDDLEWARE = [
    # ...
    "django_matt.auth.middleware.JWTAuthenticationMiddlewareAsync",
]

DJANGO_MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}
```

```python
# api.py
from django_matt import MattAPI
from django_matt.auth import AuthController

api = MattAPI(
    title="Blog API",
    version="1.0.0",
    description="A blog REST API built with Django Matt",
)

api.register_controller(AuthController, prefix="/auth")
```

```python
# blog/models.py
import uuid
from django.conf import settings
from django.db import models


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    body = models.TextField()
    published = models.BooleanField(default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
```

```python
# blog/schemas.py
from django_matt.core.schema import ModelSchema
from blog.models import Post


class PostSchema(ModelSchema):
    class Config:
        model = Post
        include = [
            "id", "title", "slug", "body",
            "published", "author", "created_at", "updated_at",
        ]


class PostCreateSchema(ModelSchema):
    class Config:
        model = Post
        include = ["title", "slug", "body", "published"]
        optional = ["published"]


class PostUpdateSchema(ModelSchema):
    class Config:
        model = Post
        include = ["title", "slug", "body", "published"]
        optional = "__all__"
```

```python
# blog/views.py
from django_matt.views import (
    APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView,
)
from django_matt.pagination import PageNumberPagination
from blog.models import Post
from blog.schemas import PostSchema, PostCreateSchema, PostUpdateSchema
from .api import api


class PostViewSet(APIViewSet):
    api = api
    model = Post
    prefix = "/posts"
    tags = ["Posts"]
    default_response_schema = PostSchema
    default_request_schema = PostCreateSchema
    pagination_class = PageNumberPagination

    filter_fields = ["published", "author"]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "title"]
    ordering = "-created_at"

    list_posts = ListView(page_size=20, max_page_size=100)
    create_post = CreateView()
    read_post = ReadView()
    update_post = UpdateView(request_schema=PostUpdateSchema)
    delete_post = DeleteView()

    async def before_create(self, request, data):
        data["author_id"] = request.user.id
        return data
```

```python
# urls.py
from django.urls import path, include
from .api import api

urlpatterns = [
    path("api/", include(api.urls)),
]
```

## Next Steps

- [Testing Your Django Matt App](testing-guide.md) -- write tests for this API
- [Build a Multi-Tenant SaaS API](build-a-saas-app.md) -- add organizations and billing
- [Add Real-Time Features](realtime-features.md) -- WebSockets and SSE

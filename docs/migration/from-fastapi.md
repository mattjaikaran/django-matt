# Migrating from FastAPI (Legacy)

> **This is a legacy guide.** The current, authoritative version is [`docs/migrations/from-fastapi.md`](../migrations/from-fastapi.md). This file is preserved for historical reference.

This guide is for Python developers coming from FastAPI who want to use Django's ORM, admin, and ecosystem while keeping the modern API patterns they know. django-matt brings Pydantic v2, async-first design, and dependency injection to Django.

## Why Switch?

| Feature | FastAPI | django-matt |
|---------|---------|-------------|
| ORM | SQLAlchemy (manual migrations) | Django ORM (auto migrations) |
| Admin panel | None built-in | Django Admin + Unfold |
| Auth | Roll your own | Built-in JWT, OAuth, SSO, Passkeys, API Keys |
| Billing | None | Built-in Stripe/PayPal/Polar |
| Background tasks | Celery (separate setup) | Built-in task abstraction (Celery/Dramatiq/Django-Q) |
| Real-time | WebSocket support | Built-in WebSocket consumers + presence |
| Schema validation | Pydantic v2 | Pydantic v2 (same) |
| Async support | Full | Full (async-first) |
| Type codegen | None built-in | Built-in TypeScript/Swift generation |
| OpenAPI | Built-in | Built-in (Swagger + ReDoc) |
| Feature flags | None | Built-in (DB, Redis, LaunchDarkly) |
| Multi-tenancy | None | Built-in org/team/membership |

## Installation

```bash
uv add django-matt
```

django-matt is a Django package, so you need a Django project:

```bash
# Scaffold a new project with CLI
python manage.py startapi myproject --template saas --auth jwt --docker
```

Or add to an existing Django project in `settings.py`:

```python
INSTALLED_APPS = [
    ...
    'django_matt',
]
```

---

## App Structure

### FastAPI

```
app/
    main.py          # FastAPI app, middleware
    routers/         # APIRouter modules
    models.py        # SQLAlchemy models
    schemas.py       # Pydantic schemas
    crud.py          # Database operations
    deps.py          # Dependency functions
    core/
        config.py    # Settings via pydantic-settings
        security.py  # JWT, password hashing
    alembic/         # Migrations
```

### django-matt

```
project/
    manage.py
    config/
        settings.py    # Django settings
        urls.py        # URL routing
        asgi.py        # ASGI entry point
    myapp/
        models.py      # Django models
        schemas.py     # Pydantic schemas (same as FastAPI)
        api.py         # DjangoMattAPI + controllers
        admin.py       # Admin panel (free!)
        tests.py       # Tests
```

---

## Defining Models

### FastAPI + SQLAlchemy

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    posts = relationship("Post", back_populates="author")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200))
    content = Column(String)
    author_id = Column(Integer, ForeignKey("users.id"))

    author = relationship("User", back_populates="posts")
```

### django-matt (Django ORM)

```python
from django.db import models

class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
```

**Key differences:**
- Django auto-generates `id` (BigAutoField by default)
- Relationships are defined once (Django infers the reverse)
- Migrations are auto-generated: `python manage.py makemigrations && python manage.py migrate`
- No Alembic config needed

---

## Pydantic Schemas

### FastAPI

```python
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class PostCreate(BaseModel):
    title: str
    content: str

class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    author_id: int

    model_config = ConfigDict(from_attributes=True)
```

### django-matt

```python
from django_matt import Schema, ModelSchema

class UserCreateSchema(Schema):
    email: str
    password: str

class UserSchema(ModelSchema):
    class Meta:
        model = User
        fields = ['id', 'email', 'is_active', 'created_at']

class PostCreateSchema(Schema):
    title: str
    content: str

class PostSchema(ModelSchema):
    class Meta:
        model = Post
        fields = ['id', 'title', 'content', 'author_id', 'created_at']
```

**Key differences:**
- `ModelSchema` auto-generates fields from the Django model -- no manual `id: int`, `email: str` duplication
- `from_attributes=True` is set automatically
- `Schema` is a plain Pydantic `BaseModel` alias -- works identically to FastAPI schemas
- `ModelSchema` provides `from_orm()` and `from_orm_fast()` for efficient serialization

---

## Routes and Endpoints

### FastAPI

```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/posts", tags=["Posts"])

@router.get("/", response_model=list[PostResponse])
async def list_posts(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Post).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/", response_model=PostResponse, status_code=201)
async def create_post(
    data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = Post(**data.model_dump(), author_id=current_user.id)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post

@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.delete("/{post_id}", status_code=204)
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your post")
    await db.delete(post)
    await db.commit()
```

### django-matt (Controller style)

```python
from django_matt import DjangoMattAPI, APIController, IsAuthenticated
from django_matt.auth import jwt_required
from django_matt.core.errors import NotFoundError, ForbiddenError

api = DjangoMattAPI()

@api.controller("/posts", tags=["Posts"])
class PostController(APIController):

    @api.get("/", response_model=list[PostSchema])
    async def list_posts(self, skip: int = 0, limit: int = 20):
        posts = []
        async for post in Post.objects.all()[skip:skip + limit]:
            posts.append(PostSchema.from_orm(post))
        return posts

    @api.post("/", response_model=PostSchema, status_code=201)
    @jwt_required
    async def create_post(self, request, data: PostCreateSchema):
        post = await Post.objects.acreate(
            **data.model_dump(), author=request.user
        )
        return PostSchema.from_orm(post)

    @api.get("/{post_id}", response_model=PostSchema)
    async def get_post(self, post_id: int):
        try:
            post = await Post.objects.aget(id=post_id)
        except Post.DoesNotExist:
            raise NotFoundError("Post not found")
        return PostSchema.from_orm(post)

    @api.delete("/{post_id}")
    @jwt_required
    async def delete_post(self, request, post_id: int):
        try:
            post = await Post.objects.aget(id=post_id)
        except Post.DoesNotExist:
            raise NotFoundError("Post not found")
        if post.author_id != request.user.id:
            raise ForbiddenError("Not your post")
        await post.adelete()
        return {"deleted": True}
```

### django-matt (ViewSet style -- zero boilerplate)

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, DeleteView

class PostViewSet(APIViewSet):
    api = api
    model = Post
    default_response_schema = PostSchema

    list = ListView()
    create = CreateView(request_schema=PostCreateSchema)
    read = ReadView()
    delete = DeleteView()

    async def before_create(self, request, data):
        data["author_id"] = request.user.id
        return data
```

---

## Dependency Injection

### FastAPI

```python
from fastapi import Depends

async def get_db():
    async with async_session() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token)
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=401)
    return user

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return user
```

### django-matt

```python
from django_matt.di import Depends, CurrentUser, container, Singleton

# Built-in: CurrentUser resolves the authenticated user from the request
@api.get("/me")
@jwt_required
async def me(request):
    return UserSchema.from_orm(request.user)

# Custom services with DI container
class NotificationService:
    async def send(self, user_id: int, message: str):
        ...

container.register(NotificationService, lifetime=Singleton)

@api.post("/notify")
@jwt_required
async def notify(
    request,
    data: NotifySchema,
    notifications: NotificationService = Depends(),
):
    await notifications.send(request.user.id, data.message)
    return {"sent": True}
```

**Key differences:**
- No database session dependency needed -- Django ORM manages connections automatically
- `request.user` is populated by middleware (no manual token decoding per endpoint)
- DI container supports `Singleton`, `Scoped`, and `Transient` lifetimes
- Built-in dependencies: `CurrentUser`, `CurrentRequest`, `CurrentOrg`

---

## Authentication

### FastAPI

```python
# You build everything yourself:
from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])

def create_access_token(data: dict):
    encoded = jwt.encode(data, SECRET_KEY, algorithm="HS256")
    return encoded

def verify_token(token: str):
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return payload

# Plus: OAuth2PasswordBearer, OAuth2 flows, etc.
# Plus: route protection with Depends(get_current_user) on every endpoint
```

### django-matt

```python
# settings.py -- that's it for basic JWT
DJANGO_MATT_JWT = {
    "SECRET_KEY": SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": 3600,
    "REFRESH_TOKEN_LIFETIME": 604800,
}

MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",
]

# api.py
from django_matt.auth import AuthController
api.register_controller(AuthController)
# Gives you: login, register, refresh, logout, me endpoints

# Protect routes with decorators
from django_matt.auth import jwt_required, with_roles

@api.get("/admin/stats")
@jwt_required
@with_roles("admin")
async def admin_stats(request):
    ...
```

Also built in: OAuth (Google, GitHub, Apple, Microsoft), SAML/OIDC SSO, Passkeys/WebAuthn, Magic Links, API Keys with rate limiting.

---

## Middleware

### FastAPI

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_timing_header(request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.time() - start)
    return response
```

### django-matt

```python
# settings.py
MIDDLEWARE = [
    "django_matt.middleware.SecurityHeadersMiddleware",
    "django_matt.middleware.CORSMiddleware",
    "django_matt.middleware.RequestIDMiddleware",
    "django_matt.middleware.TimingMiddleware",
    "django_matt.auth.JWTAuthenticationMiddleware",
    ...
]

# Or use preset stacks
from django_matt import PRODUCTION_STACK, DEVELOPMENT_STACK
```

django-matt also supports route-scoped middleware (interceptors) that run only on specific controllers or endpoints.

---

## Background Tasks

### FastAPI

```python
from fastapi import BackgroundTasks

@router.post("/send-email")
async def send_email(
    data: EmailSchema,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(send_email_task, data.to, data.body)
    return {"queued": True}
```

### django-matt

```python
# Simple in-process tasks (like FastAPI BackgroundTasks)
from django_matt.tasks import enqueue

@api.post("/send-email")
@jwt_required
async def send_email(request, data: EmailSchema):
    await enqueue(send_email_task, data.to, data.body)
    return {"queued": True}
```

django-matt's task system abstracts over Celery, Dramatiq, and Django-Q. Switch backends without changing application code.

---

## Error Handling

### FastAPI

```python
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="Item not found")

# Custom exception handler
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
```

### django-matt

```python
from django_matt.core.errors import (
    NotFoundError,
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
)

raise NotFoundError("Item not found")
raise ValidationError("Invalid email", field="email")

# APIController handles exceptions automatically:
# - DoesNotExist -> 404
# - ValidationError -> 422
# - APIError subclasses -> appropriate status codes
# - Unhandled exceptions -> 500 with debug info in dev
```

---

## Testing

### FastAPI

```python
from httpx import AsyncClient

async def test_create_post():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/posts/",
            json={"title": "Test", "content": "Body"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["title"] == "Test"
```

### django-matt

```python
from django_matt.testing import AsyncAPITestClient, assert_created

async def test_create_post():
    client = AsyncAPITestClient(api)
    await client.force_authenticate(user)

    response = await client.post(
        "/posts/",
        json={"title": "Test", "content": "Body"},
    )
    assert_created(response)
    assert response.json()["title"] == "Test"
```

django-matt also provides: model factories (no factory-boy needed), built-in data generators (no Faker needed), and assertion helpers.

---

## Settings / Configuration

### FastAPI (pydantic-settings)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
```

### django-matt (Django settings)

```python
# settings.py (standard Django)
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", False)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
    }
}

# django-matt specific
DJANGO_MATT_JWT = { ... }
DJANGO_MATT = {
    "CAMEL_CASE_API": True,
    "DI_AUTO_WIRE": True,
}
```

---

## What You Gain by Switching

1. **Django Admin** -- free CRUD admin panel for every model, no extra code
2. **Auto migrations** -- `makemigrations` detects model changes automatically
3. **Built-in auth** -- JWT, OAuth, SSO, Passkeys, Magic Links, API Keys -- all configured, not hand-rolled
4. **Django ecosystem** -- thousands of packages (django-celery-beat, django-storages, etc.)
5. **Multi-tenancy** -- built-in org/team/membership models for B2B SaaS
6. **Billing** -- Stripe/PayPal/Polar integration out of the box
7. **TypeScript codegen** -- `python manage.py sync_types --target typescript --output frontend/types`
8. **Feature flags, A/B testing, analytics** -- built-in modules, not third-party services

## What You Give Up

1. **Starlette's raw ASGI speed** -- Django adds overhead (mitigated by orjson + Rust router)
2. **SQLAlchemy flexibility** -- Django ORM is simpler but less flexible for complex queries (raw SQL always available)
3. **Ecosystem independence** -- you are in Django-land now (this is usually a net positive)

---

## Quick Reference: Import Mapping

```python
# FastAPI                              # django-matt
from fastapi import FastAPI            from django_matt import DjangoMattAPI
from fastapi import APIRouter          from django_matt import APIRouter
from fastapi import Depends            from django_matt.di import Depends
from fastapi import HTTPException      from django_matt.core.errors import NotFoundError
from fastapi import BackgroundTasks    from django_matt.tasks import enqueue
from pydantic import BaseModel         from django_matt import Schema  # (or just use BaseModel)
# SQLAlchemy model                     # Django model (django.db.models.Model)
# Alembic                              # python manage.py makemigrations
```

---

## Next Steps

- [Django Tutorial](https://docs.djangoproject.com/en/5.2/intro/tutorial01/) -- If new to Django
- [Authentication Guide](../auth/overview.md) -- Configure JWT, OAuth, SSO
- [CRUD Views](../features/views.md) -- ViewSets for rapid development
- [Framework Comparison](../comparison.md) -- Detailed feature comparison
- [Migration from DRF](from-drf.md) -- If you have existing DRF code too

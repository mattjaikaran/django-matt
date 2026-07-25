# Migrating from FastAPI to django-matt

Side-by-side reference for developers moving from FastAPI. FastAPI code on the left, django-matt equivalent on the right.

**Contents**

1. [Installation](#1-installation)
2. [App Setup](#2-app-setup)
3. [Route Decorators](#3-route-decorators)
4. [Pydantic Models](#4-pydantic-models)
5. [Request Handling](#5-request-handling)
6. [Dependency Injection](#6-dependency-injection)
7. [Authentication](#7-authentication)
8. [Middleware](#8-middleware)
9. [Background Tasks](#9-background-tasks)
10. [Testing](#10-testing)
11. [ORM](#11-orm)

---

## 1. Installation

**FastAPI**

```bash
pip install fastapi uvicorn[standard] sqlalchemy alembic pydantic-settings python-jose passlib
```

```python
# main.py — app created in Python, no framework config file
from fastapi import FastAPI
app = FastAPI()
```

**django-matt**

```bash
# Remove FastAPI deps, add django-matt
uv remove fastapi uvicorn sqlalchemy alembic
uv add django-matt

# Scaffold a new project (or add to existing Django project)
python manage.py startapi myproject --template saas --auth jwt --docker
```

```python
# settings.py — standard Django settings file
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    ...
    "django_matt",
]

# django-matt config block (all optional — sensible defaults apply)
DJANGO_MATT = {
    "CAMEL_CASE_API": True,       # camelCase JSON responses
    "DI_AUTO_WIRE": True,         # auto-wire injectable classes
}

DJANGO_MATT_JWT = {
    "SECRET_KEY": env("SECRET_KEY"),
    "ACCESS_TOKEN_LIFETIME": 3600,     # seconds
    "REFRESH_TOKEN_LIFETIME": 604800,
}
```

**ASGI entry point** — replace uvicorn's `main:app` target:

```bash
# FastAPI
uvicorn main:app --reload

# django-matt (gunicorn + uvicorn worker, or plain uvicorn)
uvicorn config.asgi:application --reload
# production:
gunicorn config.asgi:application --worker-class uvicorn.workers.UvicornWorker
```

---

## 2. App Setup

**FastAPI**

```python
# main.py
from fastapi import FastAPI
from routers import users, posts, items

app = FastAPI(title="My API", version="1.0.0")

app.include_router(users.router, prefix="/api/v1")
app.include_router(posts.router, prefix="/api/v1")
app.include_router(items.router, prefix="/api/v1")
```

**django-matt**

```python
# myapp/api.py
from django_matt import DjangoMattAPI
from .controllers import UserController, PostController, ItemController

api = DjangoMattAPI(title="My API", version="1.0.0")

api.register_controller(UserController)
api.register_controller(PostController)
api.register_controller(ItemController)

# Or register all at once
api.register_controllers(UserController, PostController, ItemController)
```

```python
# config/urls.py
from django.urls import path, include
from myapp.api import api

urlpatterns = [
    path("api/v1/", include(api.urls)),
    path("admin/", admin.site.urls),
]
```

**Directory layout comparison**

```
# FastAPI                          # django-matt
main.py                            manage.py
routers/                           config/settings.py
  users.py                         config/urls.py
  posts.py                         config/asgi.py
models.py (SQLAlchemy)             myapp/
schemas.py (Pydantic)                models.py       (Django ORM)
crud.py                              schemas.py      (Pydantic — same)
deps.py                              api.py          (DjangoMattAPI + controllers)
core/security.py (DIY JWT)           admin.py        (free admin panel)
alembic/                             tests.py
```

---

## 3. Route Decorators

**FastAPI** — function-based, decorators on module-level functions:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/posts", tags=["Posts"])

@router.get("/")
async def list_posts(): ...

@router.post("/", status_code=201)
async def create_post(): ...

@router.get("/{post_id}")
async def get_post(post_id: int): ...

@router.put("/{post_id}")
async def update_post(post_id: int): ...

@router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: int): ...
```

**django-matt** — class-based controllers, same decorator names:

```python
from django_matt import DjangoMattAPI, APIController

api = DjangoMattAPI()

@api.controller("/posts", tags=["Posts"])
class PostController(APIController):

    @api.get("/")
    async def list_posts(self): ...

    @api.post("/", status_code=201)
    async def create_post(self, data: PostCreateSchema): ...

    @api.get("/{post_id}")
    async def get_post(self, post_id: int): ...

    @api.put("/{post_id}")
    async def update_post(self, post_id: int, data: PostUpdateSchema): ...

    @api.delete("/{post_id}")
    async def delete_post(self, post_id: int): ...
```

Route path syntax (`{param}`) is identical. `status_code`, `response_model`, `tags`, `summary`, and `deprecated` keyword arguments work the same way.

---

## 4. Pydantic Models

Pydantic v2 schemas are largely compatible. Two differences to know:

**`class Config` vs `model_config`** — both work in django-matt, but `model_config` (Pydantic v2 style) is preferred:

```python
# FastAPI (Pydantic v2)
from pydantic import BaseModel, ConfigDict

class UserResponse(BaseModel):
    id: int
    email: str

    model_config = ConfigDict(from_attributes=True)

# django-matt — Schema alias (from_attributes=True already set)
from django_matt import Schema

class UserSchema(Schema):
    id: int
    email: str
    # from_attributes=True is the default — no boilerplate needed
```

**`ModelSchema`** — auto-generates fields from a Django model:

```python
# FastAPI — you repeat every field manually
class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    author_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# django-matt — declare the model and field list once
from django_matt import ModelSchema

class PostSchema(ModelSchema):
    class Meta:
        model = Post
        fields = ["id", "title", "content", "author_id", "created_at"]
        # or: exclude = ["internal_field"]
```

**Validators** — Pydantic v2 validators work without changes:

```python
from pydantic import field_validator

class UserCreateSchema(Schema):
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
```

---

## 5. Request Handling

**FastAPI** — `Body()`, `Query()`, `Path()`, `Header()` as parameter defaults:

```python
from fastapi import Body, Query, Path, Header, Request

@router.get("/items")
async def list_items(
    q: str = Query(default=None, description="Search query"),
    limit: int = Query(default=20, le=100),
    skip: int = Query(default=0),
):
    ...

@router.get("/items/{item_id}")
async def get_item(
    item_id: int = Path(description="Item primary key"),
    x_api_key: str = Header(alias="X-API-Key"),
):
    ...

@router.post("/items")
async def create_item(
    data: ItemCreate = Body(embed=True),
    request: Request = None,
):
    client_ip = request.client.host
    ...
```

**django-matt** — same pattern, same imports from `fastapi` still work, but django-matt re-exports them:

```python
from django_matt.core import Query, Path, Header, Body

@api.get("/items")
async def list_items(
    self,
    q: str | None = Query(default=None, description="Search query"),
    limit: int = Query(default=20, le=100),
    skip: int = Query(default=0),
):
    ...

@api.get("/items/{item_id}")
async def get_item(
    self,
    item_id: int = Path(description="Item primary key"),
    x_api_key: str = Header(alias="X-API-Key"),
):
    ...

@api.post("/items")
@jwt_required
async def create_item(self, request, data: ItemCreateSchema):
    client_ip = request.META.get("REMOTE_ADDR")
    ...
```

The request object is a standard Django `HttpRequest`. Access headers via `request.headers`, body via `request.body`, user via `request.user`.

---

## 6. Dependency Injection

**FastAPI** — `Depends()` as a parameter default:

```python
from fastapi import Depends

# Database session dependency (boilerplate every FastAPI project needs)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Auth dependency
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_jwt(token)
    return await db.get(User, payload["sub"])

# Usage
@router.get("/profile")
async def profile(user: User = Depends(get_current_user)):
    return user
```

**django-matt** — `@injectable` + `Depends()` or `@inject`:

```python
from django_matt.di import injectable, Depends, Singleton, container

# No database session dependency — Django ORM manages connections automatically.
# No manual token decoding — jwt_required middleware does it.

# Custom service
@injectable(lifetime=Singleton)
class EmailService:
    async def send(self, to: str, subject: str, body: str) -> None:
        ...

# Option A: Depends() parameter (familiar to FastAPI devs)
@api.post("/notify")
@jwt_required
async def notify(
    request,
    data: NotifySchema,
    email: EmailService = Depends(),
):
    await email.send(request.user.email, data.subject, data.body)
    return {"sent": True}

# Option B: @inject decorator (more explicit)
from django_matt.di import inject

@api.post("/report")
@jwt_required
@inject
async def report(request, data: ReportSchema, email: EmailService):
    await email.send(request.user.email, "Report", data.summary)
    return {"sent": True}
```

**Key difference:** No `get_db` / database session dependency. Django ORM handles connection pooling automatically. The biggest DI use case in FastAPI (session management) disappears entirely.

DI container lifetimes:

| FastAPI pattern | django-matt equivalent |
|----------------|----------------------|
| Module-level singleton | `@injectable(lifetime=Singleton)` |
| `yield` dependency (per-request) | `@injectable(lifetime=Scoped)` |
| New instance each call | `@injectable(lifetime=Transient)` |

---

## 7. Authentication

**FastAPI** — build everything yourself:

```python
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, HTTPBearer

pwd_context = CryptContext(schemes=["bcrypt"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
bearer_scheme = HTTPBearer()

SECRET_KEY = "your-secret"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta) -> str:
    payload = {**data, "exp": datetime.utcnow() + expires_delta}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=401)
    return user

# Every protected route
@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return user
```

**django-matt** — declarative, zero boilerplate:

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",   # decodes token once, sets request.user
]

DJANGO_MATT_JWT = {
    "SECRET_KEY": env("SECRET_KEY"),
    "ACCESS_TOKEN_LIFETIME": 3600,
    "REFRESH_TOKEN_LIFETIME": 604800,
    "ALGORITHM": "HS256",
}

# api.py — register built-in auth endpoints (login, register, refresh, logout, me)
from django_matt.auth import AuthController
api.register_controller(AuthController)

# Protect routes
from django_matt.auth import jwt_required, jwt_optional, with_roles

@api.get("/me")
@jwt_required                          # 401 if no valid token
async def me(request):
    return UserSchema.from_orm(request.user)

@api.get("/dashboard")
@jwt_optional                          # request.user is AnonymousUser if no token
async def dashboard(request):
    ...

@api.delete("/admin/user/{user_id}")
@jwt_required
@with_roles("admin")                   # 403 if not admin
async def delete_user(request, user_id: int):
    ...
```

**Also built in** (not available in FastAPI without third-party packages):

```python
# OAuth (Google, GitHub, Apple, Microsoft)
from django_matt.auth import OAuthController
api.register_controller(OAuthController)

# SAML / OIDC SSO
from django_matt.auth.sso import SSOController
api.register_controller(SSOController)

# Passkeys / WebAuthn
from django_matt.auth.passkeys import PasskeyController
api.register_controller(PasskeyController)

# Magic links (passwordless)
from django_matt.auth import MagicLinkController
api.register_controller(MagicLinkController)

# API keys with per-key rate limits
from django_matt.auth.api_keys import APIKeyController
api.register_controller(APIKeyController)
```

---

## 8. Middleware

**FastAPI** — Starlette middleware stack:

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.perf_counter() - start)
    return response
```

**django-matt** — Django `MIDDLEWARE` list + optional route-scoped interceptors:

```python
# settings.py — global middleware (applied to every request)
MIDDLEWARE = [
    "django_matt.middleware.SecurityHeadersMiddleware",
    "django_matt.middleware.CORSMiddleware",
    "django_matt.middleware.RequestIDMiddleware",
    "django_matt.middleware.TimingMiddleware",         # adds X-Process-Time header
    "django_matt.middleware.LoggingMiddleware",
    "django_matt.auth.JWTAuthenticationMiddleware",
    "django.middleware.common.CommonMiddleware",
    ...
]

# CORS config lives in settings, not in middleware instantiation
CORS_ALLOWED_ORIGINS = ["https://myapp.com"]
CORS_ALLOW_ALL_ORIGINS = False
```

**Route-scoped middleware** — interceptors run only on specific controllers or endpoints:

```python
from django_matt.interceptors import intercept, Interceptor
from django_matt.core import Request, Response

class RateLimitInterceptor(Interceptor):
    async def before(self, request: Request) -> None:
        if await rate_limit_exceeded(request.user):
            raise TooManyRequestsError()

    async def after(self, request: Request, response: Response) -> Response:
        response.headers["X-RateLimit-Remaining"] = "99"
        return response

# Apply to an entire controller
@intercept(RateLimitInterceptor)
@api.controller("/api/heavy", tags=["Heavy"])
class HeavyController(APIController):
    ...

# Or apply to a single endpoint
@api.get("/expensive")
@intercept(RateLimitInterceptor)
async def expensive_endpoint(self): ...
```

---

## 9. Background Tasks

**FastAPI** — `BackgroundTasks` injected per request (in-process, no queue):

```python
from fastapi import BackgroundTasks

def send_welcome_email(email: str) -> None:
    # runs after response is sent, still in the same process
    smtp.send(email, "Welcome!", "...")

@router.post("/register")
async def register(data: RegisterSchema, background_tasks: BackgroundTasks):
    user = await create_user(data)
    background_tasks.add_task(send_welcome_email, user.email)
    return {"id": user.id}
```

**django-matt** — `@task` decorator from `tasks_native` (persistent queue, retries, scheduling):

```python
from django_matt.tasks_native import task

@task(max_retries=3, retry_delay=60)
async def send_welcome_email(email: str) -> None:
    await smtp.send(email, "Welcome!", "...")

@api.post("/register")
async def register(self, data: RegisterSchema):
    user = await User.objects.acreate(**data.model_dump())
    await send_welcome_email.enqueue(user.email)   # enqueue returns immediately
    return UserSchema.from_orm(user)
```

**Scheduled tasks** (cron-style — not available in FastAPI at all):

```python
@task(schedule="0 9 * * *")    # every day at 09:00
async def daily_digest() -> None:
    users = User.objects.filter(digest_enabled=True)
    async for user in users:
        await send_digest_email.enqueue(user.email)
```

**Task management CLI:**

```bash
python manage.py matt_tasks list           # registered tasks
python manage.py matt_tasks status         # queue depth and worker status
python manage.py matt_tasks run send_welcome_email '{"email": "a@b.com"}'
```

---

## 10. Testing

**FastAPI** — `httpx.AsyncClient` wrapping the ASGI app:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_create_post(app, auth_token):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/posts/",
            json={"title": "Hello", "content": "World"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Hello"
```

**django-matt** — `AsyncAPITestClient` with built-in auth helpers:

```python
import pytest
from django_matt.testing import AsyncAPITestClient, assert_created, assert_ok
from django_matt.testing import UserFactory, PostFactory

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
async def client(api):
    return AsyncAPITestClient(api)

@pytest.fixture
async def user():
    return await UserFactory.acreate()

async def test_create_post(client, user):
    await client.force_authenticate(user)   # no manual token needed

    response = await client.post(
        "/posts/",
        json={"title": "Hello", "content": "World"},
    )
    assert_created(response)                # asserts 201 + returns parsed JSON
    assert response.json()["title"] == "Hello"

async def test_list_posts(client, user):
    await PostFactory.acreate_batch(3, author=user)
    await client.force_authenticate(user)

    response = await client.get("/posts/")
    assert_ok(response)
    assert len(response.json()) == 3

async def test_unauthenticated():
    client = AsyncAPITestClient(api)
    response = await client.get("/me/")
    assert response.status_code == 401
```

**Factories** — no factory-boy or Faker needed:

```python
from django_matt.testing import UserFactory, fake

# Async factory
user = await UserFactory.acreate(email="custom@example.com")
users = await UserFactory.acreate_batch(10)

# Built-in data generators
email = fake.email()
name = fake.name()
uuid = fake.uuid4()
```

**pytest configuration** (`pyproject.toml`):

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
asyncio_mode = "auto"
```

---

## 11. ORM

**FastAPI + SQLAlchemy** — manual session management, explicit async engine:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

# Every handler needs get_db
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# CRUD
async def get_user(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(email=data.email)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def list_users(db: AsyncSession, skip: int = 0, limit: int = 20):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

# Relationships
result = await db.execute(
    select(Post).options(selectinload(Post.author)).where(Post.id == post_id)
)
```

**django-matt (Django ORM)** — no session management, async ORM built in:

```python
from django.db import models

class User(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)

# Async ORM — prefix sync methods with 'a'
user = await User.objects.aget(id=user_id)               # raises DoesNotExist if missing
user = await User.objects.filter(email=email).afirst()   # returns None if missing
user = await User.objects.acreate(email=data.email)
await user.asave()
await user.adelete()

# Filtering and ordering
posts = Post.objects.filter(author=user).order_by("-created_at")
async for post in posts:
    ...

# Aggregation
count = await Post.objects.filter(author=user).acount()

# Relationships — use select_related / prefetch_related
posts = await Post.objects.select_related("author").filter(author=user).all()
# ModelSchema auto-optimizes with select_related/prefetch_related based on schema fields

# Sync ORM in async context — wrap with sync_to_async
from asgiref.sync import sync_to_async

count = await sync_to_async(Post.objects.filter(author=user).count)()
```

**ORM method mapping:**

| SQLAlchemy (async) | Django ORM (async) |
|-------------------|-------------------|
| `await db.get(User, id)` | `await User.objects.aget(id=id)` |
| `await db.execute(select(User))` | `User.objects.all()` (async iterable) |
| `result.scalar_one_or_none()` | `await qs.afirst()` |
| `db.add(obj); await db.commit()` | `await User.objects.acreate(...)` |
| `await db.refresh(obj)` | `await obj.arefresh_from_db()` |
| `await db.delete(obj); await db.commit()` | `await obj.adelete()` |
| `select(...).where(...)` | `.filter(...)` |
| `select(...).options(selectinload(...))` | `.select_related(...)` / `.prefetch_related(...)` |
| `select(...).offset(n).limit(m)` | `qs[n:n+m]` |
| Alembic `revision --autogenerate` | `python manage.py makemigrations` |
| Alembic `upgrade head` | `python manage.py migrate` |

---

## Quick Reference: Import Mapping

```python
# FastAPI                                    # django-matt
from fastapi import FastAPI                  from django_matt import DjangoMattAPI
from fastapi import APIRouter                from django_matt import APIRouter
from fastapi import HTTPException            from django_matt.core.errors import NotFoundError
from fastapi import Depends                  from django_matt.di import Depends
from fastapi import BackgroundTasks          from django_matt.tasks_native import task
from fastapi import Query, Path, Header      from django_matt.core import Query, Path, Header
from fastapi.security import OAuth2PasswordBearer  # replaced by @jwt_required
from pydantic import BaseModel               from django_matt import Schema
                                             from django_matt import ModelSchema  # new
from httpx import AsyncClient                from django_matt.testing import AsyncAPITestClient
# sqlalchemy session dependency              # not needed — Django ORM manages connections
```

---

## Next Steps

- [Authentication Guide](../auth/overview.md) — JWT, OAuth, SSO, Passkeys, Magic Links
- [CRUD ViewSets](../features/views.md) — zero-boilerplate ViewSet pattern
- [Dependency Injection](../di/overview.md) — container lifetimes, `@injectable`, `@inject`
- [Interceptors](../interceptors/overview.md) — route-scoped middleware
- [Native Tasks](../tasks/native.md) — persistent background tasks and scheduling
- [Framework Comparison](../comparison.md) — full feature matrix
- [Migrating from DRF](../migration/from-drf.md) — if you have existing DRF code

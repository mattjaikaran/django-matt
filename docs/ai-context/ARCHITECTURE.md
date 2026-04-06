# Django Matt Architecture

> Include this file in AI model context when working with django-matt projects.

## What is Django Matt?

A standalone Django meta-framework that replaces Django Ninja, DRF, and their ecosystems. One package provides: routing, controllers, schemas, auth (JWT/OAuth/SSO/Passkeys), views, permissions, OpenAPI docs, type generation, and 30+ modules.

## Core Stack

- **Python 3.12+** / **Django 5.2+** / **Pydantic v2**
- **Async-first** — all controllers and views are async by default
- **orjson** — base dependency, used everywhere for JSON (not optional)
- Package manager: **uv** (not pip)

## Module Map

```
django_matt/
├── api.py              # MattAPI — the entry point (like FastAPI() or NinjaAPI())
├── core/
│   ├── router.py       # Router, route decorators: get, post, put, patch, delete
│   ├── controller.py   # Controller, APIController, CRUDController base classes
│   ├── schema.py       # ModelSchema (Django model → Pydantic), Schema base
│   └── errors.py       # APIError hierarchy, ErrorHandler, ErrorMiddleware
├── auth/
│   ├── jwt.py          # JWT config, token creation/validation
│   ├── jwt_builtin.py  # Built-in JWT encode/decode (no PyJWT dependency)
│   ├── middleware.py    # JWTAuthenticationMiddleware
│   ├── decorators.py   # @jwt_required, @jwt_optional, @with_roles, @with_permission
│   ├── rbac/           # Role-Based Access Control with hierarchy
│   ├── oauth/          # OAuth providers (Google, GitHub, Apple, etc.)
│   ├── sso/            # SSO providers (SAML, OIDC)
│   ├── passkeys/       # WebAuthn/Passkeys
│   ├── magic_link.py   # Passwordless magic link auth
│   └── api_keys.py     # API key auth with usage tracking
├── views/
│   ├── base.py         # APIView — generic typed view
│   ├── viewset.py      # APIViewSet, ViewSet — composable CRUD
│   ├── list.py         # ListView
│   ├── create.py       # CreateView
│   ├── read.py         # ReadView / RetrieveView
│   ├── update.py       # UpdateView / PatchView
│   ├── delete.py       # DeleteView
│   └── hooks.py        # Lifecycle hooks (before_create, after_create, etc.)
├── permissions/        # IsAuthenticated, IsAdmin, IsOwner, HasRole, decorators
├── openapi/            # Swagger UI + ReDoc generation
├── di/                 # Dependency injection container (Depends() pattern)
├── interceptors/       # Route-scoped middleware (before/after hooks, not global)
├── streaming/          # SSE responses, NDJSON streaming, heartbeat helpers
├── events/             # Async event bus (pub/sub with InMemory/Redis backends)
├── exceptions/         # Exception filters (structured error handling per-route or global)
├── serialization/      # Group-based field visibility (role-based API responses)
├── secrets/            # Multi-backend secrets (env, Vault, AWS SM, GCP SM, dotenv)
├── introspection/      # Health checks, infra reporting, readiness/liveness probes
├── rpc/                # Typed HTTP client gen (Python + TypeScript from OpenAPI)
├── modules/            # Plugin system with dependency resolution and lifecycle hooks
├── cqrs/               # Command/Query buses, domain events, bus middleware
├── slim.py             # Slim mode config (full/slim/minimal/auto module loading)
├── loader.py           # Lazy module loading (LazyModuleProxy, DeferredLoader)
└── ... (20+ more modules)
```

## How It Works

### 1. API Entry Point

```python
# config/api.py
from django_matt import MattAPI

api = MattAPI(
    title="My API",
    version="1.0.0",
    description="My API built with Django Matt",
)
```

### 2. Controllers (Class-Based Endpoints)

```python
from django_matt import APIController, get, post, put, delete
from django_matt.auth import jwt_required

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    """
    Controllers group related endpoints. The prefix comes from
    @api.controller("/prefix"), NOT from a class attribute.
    """

    @get("/")
    async def list_users(self, request):
        users = [u async for u in User.objects.all()]
        return [UserSchema.from_orm(u) for u in users]

    @post("/")
    @jwt_required
    async def create_user(self, request, body: UserCreateSchema):
        # body is auto-parsed from JSON via Pydantic
        user = await User.objects.acreate(**body.model_dump())
        return UserSchema.from_orm(user)

    @get("/{id}")
    async def get_user(self, request, id: int):
        user = await User.objects.aget(id=id)
        return UserSchema.from_orm(user)
```

### 3. Router (Function-Based Endpoints)

```python
from django_matt import APIRouter

router = APIRouter()

@router.get("api/items/")
async def list_items(request):
    return {"items": []}

# In urls.py
urlpatterns = router.get_urls()
```

### 4. ViewSets (Declarative CRUD)

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema
    default_request_schema = ProductCreateSchema
    prefix = "products"

    list = ListView()
    create = CreateView()
    read = ReadView()         # NOT "retrieve" in class def — ReadView is the class name
    update = UpdateView()
    delete = DeleteView()

    # Lifecycle hooks (optional)
    async def before_create(self, request, data):
        data["created_by_id"] = request.user.id
        return data
```

### 5. Schemas (Pydantic v2)

```python
from django_matt import ModelSchema, Schema

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "email", "username", "date_joined"]

class UserCreateSchema(Schema):
    email: str
    username: str
    password: str
```

### 6. URL Registration

```python
# config/urls.py
from django.urls import path
from config.api import api

urlpatterns = [
    path("api/", api.urls),
]

# Register controllers — NO prefix argument!
api.register_controller(UserController)
api.register_controller(ProductController)
```

## Key Architecture Decisions

### Async-First
- All controller methods should be `async def`
- Use async ORM: `.aget()`, `.acreate()`, `.asave()`, `.adelete()`, `.aexists()`
- For querysets: `[item async for item in Model.objects.filter(...)]`
- NEVER call sync ORM in async context — use `sync_to_async()` for sync-only code

### orjson is Always Available
```python
import orjson  # Always works — base dependency

# Use orjson.loads() instead of json.loads()
data = orjson.loads(request.body)

# Use orjson.dumps() for responses
content = orjson.dumps(data)
```

### Built-in JWT (No PyJWT)
```python
from django_matt.auth.jwt_builtin import encode_jwt, decode_jwt

# HS256 with Django SECRET_KEY by default
# RS256/ES256 with cryptography package (jwt-asymmetric extra)
```

### Controller Method Wrapping
Controllers use a single-pass `_setup_methods()` at `__init__` that:
1. Caches `get_type_hints()` once (not per-request)
2. Pre-computes Pydantic body params
3. Pre-computes DI params
4. Wraps each method with error handling + DI resolution
5. Uses `_method=method` default arg binding (avoids closure capture bugs)

### Schema Performance
- `from_orm_fast()` uses `model_construct()` for list serialization (skips re-validation)
- `optimize_queryset()` auto-detects FK/M2M fields from schema for `select_related`/`prefetch_related`

## Settings

```python
# settings.py

DJANGO_MATT = {
    "DI_AUTO_WIRE": False,          # Enable dependency injection
    "DEFAULT_PERMISSION_CLASSES": [],
}

DJANGO_MATT_JWT = {
    "SECRET_KEY": None,             # Defaults to Django SECRET_KEY
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

DJANGO_MATT_ERRORS = {
    "DEBUG": DEBUG,
    "INCLUDE_TRACEBACK": DEBUG,
    "INCLUDE_SNIPPET": DEBUG,
}
```

## Dependencies

### Base (always installed)
django, pydantic, orjson, pyyaml, watchdog, rich, typer, email-validator, aiofiles

### Optional Extras
```bash
uv add "django-matt[jwt-asymmetric]"  # RSA/EC JWT (cryptography)
uv add "django-matt[oauth]"           # OAuth providers (authlib)
uv add "django-matt[passkeys]"        # WebAuthn (webauthn)
uv add "django-matt[performance]"     # ujson, msgpack, redis
uv add "django-matt[billing]"         # Stripe
uv add "django-matt[postgres]"        # psycopg3 with pool
uv add "django-matt[server]"          # uvicorn + gunicorn
uv add "django-matt[all]"             # Everything
```

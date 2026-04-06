# Django Matt Quick Reference

> Cheat sheet for AI models working with django-matt projects.

## Project Setup

```bash
# Create new project
uv init myproject && cd myproject
uv add django django-matt

# With extras
uv add "django-matt[all]"

# Generate scaffold
python manage.py startapi myproject --template saas --auth jwt --docker
```

## Imports

```python
# Core
from django_matt import MattAPI, APIController, get, post, put, patch, delete
from django_matt import ModelSchema, Schema
from django_matt import APIRouter

# Views
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

# Auth
from django_matt.auth import jwt_required, jwt_optional, create_token_pair, with_roles, with_permission
from django_matt.auth.schemas import LoginRequest, TokenPair

# Permissions
from django_matt.permissions import IsAuthenticated, IsAdmin, IsOwner, HasRole

# Errors
from django_matt.core.errors import APIError, NotFoundAPIError, ValidationAPIError, PermissionAPIError

# Performance
from django_matt import FastJsonResponse, StreamingJsonResponse
import orjson  # Always available (base dep)

# DI
from django_matt.di import Depends
```

## API Setup Pattern

```python
# config/api.py
from django_matt import MattAPI
api = MattAPI(title="My API", version="1.0.0")

# config/urls.py
from django.urls import path
from config.api import api

# Import controllers so they register with @api.controller()
import myapp.controllers  # noqa: F401

urlpatterns = [
    path("api/", api.urls),
]
```

## Controller Template

```python
from django_matt import APIController, get, post, put, delete
from django_matt.auth import jwt_required
from django_matt.core.errors import NotFoundAPIError

@api.controller("/items", tags=["Items"])
class ItemController(APIController):

    @get("/")
    async def list_items(self, request):
        items = [i async for i in Item.objects.all()]
        return [ItemSchema.from_orm(i) for i in items]

    @get("/{id}")
    async def get_item(self, request, id: int):
        try:
            item = await Item.objects.aget(id=id)
        except Item.DoesNotExist:
            raise NotFoundAPIError(message="Item not found")
        return ItemSchema.from_orm(item)

    @post("/")
    @jwt_required
    async def create_item(self, request, body: ItemCreateSchema):
        item = await Item.objects.acreate(**body.model_dump())
        return ItemSchema.from_orm(item)

    @put("/{id}")
    @jwt_required
    async def update_item(self, request, id: int, body: ItemUpdateSchema):
        item = await Item.objects.aget(id=id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(item, k, v)
        await item.asave()
        return ItemSchema.from_orm(item)

    @delete("/{id}")
    @jwt_required
    async def delete_item(self, request, id: int):
        item = await Item.objects.aget(id=id)
        await item.adelete()
        return {"deleted": True}
```

## Schema Template

```python
from django_matt import ModelSchema, Schema

class ItemSchema(ModelSchema):
    class Config:
        model = Item
        include = ["id", "name", "description", "price", "created_at"]

class ItemCreateSchema(Schema):
    name: str
    description: str = ""
    price: float

class ItemUpdateSchema(Schema):
    name: str | None = None
    description: str | None = None
    price: float | None = None
```

## ViewSet Template

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

class ItemViewSet(APIViewSet):
    api = api
    model = Item
    default_response_schema = ItemSchema
    default_request_schema = ItemCreateSchema
    prefix = "items"

    list = ListView()
    create = CreateView()
    read = ReadView()
    update = UpdateView()
    delete = DeleteView()
```

## Auth Decorators

| Decorator | Purpose |
|-----------|---------|
| `@jwt_required` | Require valid JWT token |
| `@jwt_optional` | Parse JWT if present, allow anonymous |
| `@with_roles("admin")` | Require specific role(s) |
| `@with_permission("items.create")` | Require specific permission |
| `@api_key_required` | Require valid API key |

## Settings Reference

```python
# JWT
DJANGO_MATT_JWT = {
    "SECRET_KEY": "your-key",            # default: Django SECRET_KEY
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# General
DJANGO_MATT = {
    "DI_AUTO_WIRE": False,
}

# Errors
DJANGO_MATT_ERRORS = {
    "DEBUG": True,
    "INCLUDE_TRACEBACK": True,
}
```

## Middleware Stack

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_matt.auth.middleware.JWTAuthenticationMiddleware",  # JWT auth
    "django_matt.core.errors.ErrorMiddleware",                  # Error handling
    "django.contrib.messages.middleware.MessageMiddleware",
]
```

## Async ORM Quick Reference

| Sync | Async |
|------|-------|
| `.get()` | `.aget()` |
| `.create()` | `.acreate()` |
| `.save()` | `.asave()` |
| `.delete()` | `.adelete()` |
| `.exists()` | `.aexists()` |
| `.count()` | `.acount()` |
| `.first()` | `.afirst()` |
| `.update()` | `.aupdate()` |
| `list(qs)` | `[x async for x in qs]` |

## Testing

```bash
# Run all tests
uv run pytest tests/ -x -q

# Run specific file
uv run pytest tests/test_auth.py -v

# With coverage
uv run pytest tests/ --cov=django_matt

# Lint
uv run ruff check django_matt/
```

## New Module Imports

```python
# Interceptors — route-scoped middleware (before/after request hooks)
from django_matt.interceptors import Interceptor, InterceptorChain, intercept, intercept_controller
from django_matt.interceptors import LoggingInterceptor, TimingInterceptor, CachingInterceptor, RateLimitInterceptor, RetryInterceptor, TransformInterceptor

# Streaming — SSE and streaming responses
from django_matt.streaming import sse_response, SSEEvent, event, heartbeat, with_heartbeat
from django_matt.streaming import stream_response, stream_json, stream_text
from django_matt.streaming import sse_endpoint, streaming  # decorators

# Events — async event bus for decoupled communication
from django_matt.events import Event, EventBus, get_event_bus, on, autodiscover
from django_matt.events import InMemoryBackend, RedisBackend, EventMiddleware, collect_event

# Exceptions — exception filters (structured error handling)
from django_matt.exceptions import ExceptionFilter, ExceptionFilterChain, catch, catch_all, exception_filter, register_global_filter
from django_matt.exceptions import ValidationExceptionFilter, NotFoundExceptionFilter, DatabaseExceptionFilter

# Serialization — group-based field visibility
from django_matt.serialization import Grouped, Public, Secret, SerializationContext, filter_schema, schema_for_groups, serialize_for
from django_matt.serialization import SerializationContextMiddleware

# Secrets — multi-backend secret management
from django_matt.secrets import SecretsManager, get_secrets_manager, SecretField, secret
from django_matt.secrets import EnvBackend, DotenvBackend, VaultBackend, AWSSecretsManagerBackend, GCPSecretManagerBackend, EncryptedFileBackend
from django_matt.secrets import RotationPolicy, on_rotation

# Introspection — health checks and infrastructure reporting
from django_matt.introspection import registry, generate_report, get_health_urls, HealthCheckMiddleware
from django_matt.introspection import check_database, check_redis, check_cache, check_celery, check_email, check_storage

# RPC — typed HTTP client generation
from django_matt.rpc import RPCClient, TypedRPCClient, RPCProxy
from django_matt.rpc import BearerAuth, APIKeyAuth, BasicAuth, CompositeAuth
from django_matt.rpc import generate_python_client, generate_typescript_client

# Modules — modular plugin system with dependency resolution
from django_matt.modules import MattModule, ModuleRegistry, get_registry, load_modules, shutdown_modules
from django_matt.modules import module, requires_module, optional_module, on_module_loaded, on_all_loaded

# CQRS — command/query separation
from django_matt.cqrs import Command, CommandBus, CommandHandler, command_handler, get_command_bus
from django_matt.cqrs import Query, QueryBus, QueryHandler, query_handler, get_query_bus
from django_matt.cqrs import DomainEvent, EventCollector, emits
from django_matt.cqrs import LoggingMiddleware, ValidationMiddleware, TransactionMiddleware, CachingMiddleware

# Slim mode — control which modules load
from django_matt.slim import SlimConfig, get_slim_config, is_module_enabled, ModuleRegistry as SlimModuleRegistry

# Loader — lazy/deferred module loading
from django_matt.loader import lazy_import, LazyModuleProxy, DeferredLoader
```

## CLI Commands

```bash
# Project scaffold
python manage.py startapi myproject --template b2b --auth jwt

# CRUD generation
python manage.py generate_crud myapp.Product --full

# Type sync
python manage.py sync_types --target typescript --output frontend/types

# AI context generation
python manage.py generate_ai_context --format all
```

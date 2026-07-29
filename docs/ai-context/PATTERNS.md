# Django Matt — Correct Patterns

> Reference this file when writing code with django-matt. Every pattern here is verified against the actual source code.

## Controller Patterns

### Defining a Controller
```python
from django_matt import APIController, get, post, put, patch, delete
from django_matt.auth import jwt_required, with_roles

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    """prefix comes from @api.controller(), NOT from class attribute."""

    @get("/")
    async def list_users(self, request):
        """Always async. Use async ORM."""
        users = [u async for u in User.objects.all()]
        return [UserSchema.from_orm(u) for u in users]

    @post("/")
    @jwt_required
    async def create_user(self, request, body: UserCreateSchema):
        """body param auto-parsed from JSON via Pydantic."""
        user = await User.objects.acreate(**body.model_dump())
        return UserSchema.from_orm(user)

    @get("/{id}")
    async def get_user(self, request, id: int):
        try:
            user = await User.objects.aget(id=id)
        except User.DoesNotExist:
            raise NotFoundAPIError(message="User not found")
        return UserSchema.from_orm(user)

    @put("/{id}")
    @jwt_required
    async def update_user(self, request, id: int, body: UserUpdateSchema):
        user = await User.objects.aget(id=id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await user.asave()
        return UserSchema.from_orm(user)

    @delete("/{id}")
    @jwt_required
    @with_roles("admin")
    async def delete_user(self, request, id: int):
        user = await User.objects.aget(id=id)
        await user.adelete()
        return {"deleted": True}
```

### Registering Controllers
```python
# In urls.py — register_controller takes ONE arg: the class. NO prefix.
api.register_controller(UserController)
api.register_controller(ProductController)
api.register_controller(OrderController)

urlpatterns = [
    path("api/", api.urls),
]
```

### Custom Error Handling
```python
class MyController(APIController):
    auto_error_handling = True  # default

    def handle_exception(self, exc, request=None):
        """Override for custom error handling."""
        if isinstance(exc, SpecialError):
            return JsonResponse({"error": "custom"}, status=400)
        return super().handle_exception(exc, request)
```

## ViewSet Patterns

### Basic CRUD ViewSet
```python
from django_matt.views import (
    APIViewSet, ListView, CreateView, ReadView,
    UpdateView, PatchView, DeleteView,
)

class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema
    default_request_schema = ProductCreateSchema
    prefix = "products"  # ViewSets use prefix as class attr

    list = ListView()
    create = CreateView()
    read = ReadView()     # The method name is "read", class is ReadView
    update = UpdateView()
    delete = DeleteView()
```

### ViewSet with Lifecycle Hooks
```python
class OrderViewSet(APIViewSet):
    api = api
    model = Order
    prefix = "orders"
    default_response_schema = OrderSchema

    list = ListView()
    create = CreateView()
    read = ReadView()

    async def before_create(self, request, data):
        """Modify data before creation."""
        data["created_by_id"] = request.user.id
        data["status"] = "pending"
        return data

    async def after_create(self, request, instance):
        """Side effects after creation."""
        await notify_admin(instance)
        return instance

    async def before_list(self, request, queryset):
        """Filter queryset based on user."""
        return queryset.filter(created_by=request.user)
```

## Schema Patterns

### ModelSchema from Django Model
```python
from django_matt import ModelSchema

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "email", "username", "date_joined"]

class UserCreateSchema(ModelSchema):
    class Config:
        model = User
        include = ["email", "username", "password"]

class UserUpdateSchema(ModelSchema):
    class Config:
        model = User
        include = ["email", "username"]
        optional = ["email", "username"]  # All fields optional for PATCH
```

### Standalone Schema (No Model)
```python
from django_matt import Schema

class LoginRequest(Schema):
    email: str
    password: str

class TokenResponse(Schema):
    access: str
    refresh: str
```

### Fast Serialization for Lists
```python
# For single objects — normal validation
schema = UserSchema.from_orm(user)

# For lists — use model_construct() (skips re-validation, 3-5x faster)
schemas = [UserSchema.model_construct(**{
    field: getattr(user, field)
    for field in UserSchema.model_fields
}) for user in users]
```

## Authentication Patterns

### JWT Auth
```python
from django_matt.auth import jwt_required, jwt_optional, create_token_pair
from django_matt.auth.schemas import LoginRequest, TokenPair

@api.controller("/auth")
class AuthController(APIController):

    @post("/login")
    async def login(self, request, body: LoginRequest):
        user = await authenticate_user(body.email, body.password)
        if not user:
            raise APIError("Invalid credentials", status_code=401)
        tokens = create_token_pair(user)
        return tokens

    @post("/refresh")
    async def refresh(self, request, body: RefreshRequest):
        tokens = refresh_token_pair(body.refresh)
        return tokens

    @get("/me")
    @jwt_required
    async def me(self, request):
        return UserSchema.from_orm(request.user)

    @get("/profile")
    @jwt_optional
    async def profile(self, request):
        if request.user.is_authenticated:
            return UserSchema.from_orm(request.user)
        return {"anonymous": True}
```

### RBAC (Role-Based Access Control)
```python
from django_matt.auth import with_roles, with_permission

@get("/admin")
@jwt_required
@with_roles("admin", "superadmin")
async def admin_panel(self, request):
    ...

@delete("/{id}")
@jwt_required
@with_permission("users.delete")
async def delete_user(self, request, id: int):
    ...
```

### Permission Classes
```python
from django_matt.permissions import IsAuthenticated, IsAdmin, IsOwner

class SecureController(APIController):
    permission_classes = [IsAuthenticated]

class AdminController(APIController):
    permission_classes = [IsAdmin]
```

## Async ORM Patterns

### Correct Async ORM Usage
```python
# Single object
user = await User.objects.aget(id=id)

# Exists check
exists = await User.objects.filter(email=email).aexists()

# Create
user = await User.objects.acreate(email=email, username=username)

# Update
user.name = "new name"
await user.asave()

# Delete
await user.adelete()

# List (async iteration)
users = [u async for u in User.objects.filter(is_active=True)]

# Count
count = await User.objects.acount()

# First
user = await User.objects.filter(email=email).afirst()
```

### WRONG — Never Do This in Async
```python
# WRONG: sync ORM in async context
user = User.objects.get(id=id)           # Use .aget()
users = list(User.objects.all())          # Use async for
exists = User.objects.filter(...).exists() # Use .aexists()
user.save()                               # Use .asave()
user.delete()                             # Use .adelete()
User.objects.create(...)                  # Use .acreate()
await User.objects.all()                  # QuerySets aren't awaitable! Use async for
```

## Error Handling Patterns

### Built-in Error Types
```python
from django_matt.core.errors import (
    APIError,           # Base — any status code
    NotFoundAPIError,   # 404
    ValidationAPIError, # 422
    PermissionAPIError, # 403
)

# Raise in any controller method
raise NotFoundAPIError(message="User not found", resource_type="User", resource_id=str(id))
raise ValidationAPIError(message="Invalid data", errors=[{"field": "email", "message": "Required"}])
raise PermissionAPIError(message="Admin only", required_permission="admin")
raise APIError(message="Rate limited", status_code=429, code="rate_limited")
```

## Testing Patterns

### Test Client
```python
import pytest
from django.test import AsyncClient

@pytest.mark.django_db
async def test_list_users():
    client = AsyncClient()
    response = await client.get("/api/users/")
    assert response.status_code == 200

@pytest.mark.django_db
async def test_create_user_authenticated():
    client = AsyncClient()
    user = await User.objects.acreate(username="admin", email="admin@test.com")
    # Use force_authenticate, NOT authenticate
    client.force_login(user)
    response = await client.post(
        "/api/users/",
        data={"email": "new@test.com", "username": "newuser"},
        content_type="application/json",
    )
    assert response.status_code == 201
```

## Dependency Injection (Optional)

```python
# settings.py
DJANGO_MATT = {"DI_AUTO_WIRE": True}

# service.py
class UserService:
    async def get_user(self, id: int) -> User:
        return await User.objects.aget(id=id)

# controller.py
from django_matt.di import Depends

@get("/{id}")
async def get_user(self, request, id: int, service: UserService = Depends()):
    return await service.get_user(id)
```

## URL Patterns

### Standard Setup
```python
# config/urls.py
from django.contrib import admin
from django.urls import path
from config.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
```

### With OpenAPI Docs
```python
from django_matt.openapi import get_swagger_ui, get_redoc

urlpatterns = [
    path("api/", api.urls),
    path("docs/", get_swagger_ui(api)),
    path("redoc/", get_redoc(api)),
]
```

## Interceptor Patterns

### Route-Scoped Interceptors (Instead of Global Middleware)
```python
from django_matt.interceptors import Interceptor, intercept, intercept_controller
from django_matt.interceptors import LoggingInterceptor, TimingInterceptor

# Apply to a single endpoint
@get("/slow")
@intercept(TimingInterceptor(), LoggingInterceptor())
async def slow_endpoint(self, request):
    ...

# Apply to an entire controller
@intercept_controller(LoggingInterceptor(), TimingInterceptor())
@api.controller("/admin", tags=["Admin"])
class AdminController(APIController):
    ...
```

### Custom Interceptor
```python
from django_matt.interceptors import Interceptor

class AuditInterceptor(Interceptor):
    order = 10  # lower = runs first

    async def before_request(self, request, **kwargs):
        request._audit_start = time.monotonic()
        return None  # return None to continue, return HttpResponse to short-circuit

    async def after_response(self, request, response, **kwargs):
        elapsed = time.monotonic() - request._audit_start
        logger.info(f"Request took {elapsed:.3f}s")
        return response

    async def on_error(self, request, exc, **kwargs):
        logger.error(f"Request failed: {exc}")
        return None  # return None to re-raise, return HttpResponse to handle
```

## Streaming Patterns

### SSE for AI/LLM Responses
```python
from django_matt.streaming import sse_response, SSEEvent, event, sse_endpoint

@api.controller("/ai", tags=["AI"])
class AIStreamController(APIController):

    @post("/chat")
    @jwt_required
    async def stream_chat(self, request, body: dict):
        async def generate():
            llm = get_provider("openai")
            async for chunk in llm.stream([Message.user(body["message"])]):
                yield SSEEvent(data={"token": chunk.content}, event="token")
            yield SSEEvent(data={"done": True}, event="done")

        return sse_response(generate())

    # Or use the decorator shorthand
    @post("/stream")
    @jwt_required
    @sse_endpoint
    async def stream(self, request, body: dict):
        llm = get_provider("openai")
        async for chunk in llm.stream([Message.user(body["message"])]):
            yield SSEEvent(data={"token": chunk.content})
```

### NDJSON Streaming
```python
from django_matt.streaming import stream_json

@get("/export")
@jwt_required
async def export_data(self, request):
    async def generate():
        async for item in Item.objects.all():
            yield ItemSchema.from_orm(item).model_dump()

    return stream_json(generate())
```

## Event Bus Patterns

### Event-Driven Decoupling
```python
from django_matt.events import Event, get_event_bus, on

# Define events as Pydantic models
class OrderPlaced(Event):
    order_id: int
    user_id: int
    total: float

# Subscribe with decorator
@on("OrderPlaced")
async def send_confirmation_email(event: OrderPlaced):
    await send_email(user_id=event.user_id, template="order_confirmation")

@on("OrderPlaced")
async def update_inventory(event: OrderPlaced):
    await reduce_stock(order_id=event.order_id)

# Emit from a controller
@post("/orders")
@jwt_required
async def create_order(self, request, body: OrderCreateSchema):
    order = await Order.objects.acreate(**body.model_dump())
    bus = get_event_bus()
    await bus.emit(OrderPlaced(order_id=order.id, user_id=request.user.id, total=order.total))
    return OrderSchema.from_orm(order)
```

### Wildcard Subscriptions
```python
# Subscribe to all order events
@on("Order*")
async def log_order_activity(event: Event):
    logger.info(f"Order event: {event.event_type}")
```

## CQRS Patterns

### Command/Query Separation
```python
from django_matt.cqrs import Command, Query, command_handler, query_handler, get_command_bus, get_query_bus

# Commands (write operations) — frozen Pydantic models
class CreateOrder(Command):
    user_id: int
    items: list[dict]

class CancelOrder(Command):
    order_id: int
    reason: str

# Command handlers — exactly one per command
@command_handler(CreateOrder)
class CreateOrderHandler:
    async def execute(self, command: CreateOrder) -> int:
        order = await Order.objects.acreate(user_id=command.user_id)
        return order.id

# Queries (read operations)
class GetUserOrders(Query):
    user_id: int
    status: str | None = None

@query_handler(GetUserOrders)
class GetUserOrdersHandler:
    async def execute(self, query: GetUserOrders) -> list:
        qs = Order.objects.filter(user_id=query.user_id)
        if query.status:
            qs = qs.filter(status=query.status)
        return [o async for o in qs]

# Dispatch from controller
@post("/orders")
@jwt_required
async def create_order(self, request, body: OrderCreateSchema):
    bus = get_command_bus()
    order_id = await bus.dispatch(CreateOrder(user_id=request.user.id, items=body.items))
    return {"order_id": order_id}

@get("/orders")
@jwt_required
async def list_orders(self, request):
    bus = get_query_bus()
    orders = await bus.dispatch(GetUserOrders(user_id=request.user.id))
    return [OrderSchema.from_orm(o) for o in orders]
```

## Serialization Group Patterns

### Role-Based Field Visibility
```python
from django_matt.serialization import Grouped, Public, Secret, serialize_for, schema_for_groups

class UserSchema(Schema):
    id: int
    email: str = Grouped("admin", "self")     # only visible to admin or self
    username: str                               # always visible (no group = public)
    ssn: str = Secret()                        # only "admin" and "internal" groups
    role: str = Grouped("admin")

# Filter at endpoint level
@get("/users")
@serialize_for(groups=["public"])
async def list_users(self, request):
    users = [u async for u in User.objects.all()]
    return [UserSchema.from_orm(u) for u in users]

# Dynamic groups based on request (e.g., user role)
@get("/users/{id}")
@serialize_for(groups_from="user.role")  # reads request.user.role
async def get_user(self, request, id: int):
    user = await User.objects.aget(id=id)
    return UserSchema.from_orm(user)

# Generate a schema class with only visible fields
AdminUserSchema = schema_for_groups(UserSchema, "admin")
```

## Exception Filter Patterns

### Structured Exception Handling
```python
from django_matt.exceptions import ExceptionFilter, catch, register_global_filter
from django.http import JsonResponse

# Class-based filter
class StripeExceptionFilter(ExceptionFilter):
    exception_types = (StripeError,)
    order = 10

    async def catch(self, exc, request):
        return JsonResponse(
            {"error": "payment_failed", "message": str(exc)},
            status=402,
        )

register_global_filter(StripeExceptionFilter())

# Decorator-based filter on a single endpoint
@post("/charge")
@catch(StripeError, handler=lambda exc, req: JsonResponse({"error": str(exc)}, status=402))
async def charge(self, request, body: ChargeSchema):
    ...
```

## Native Task Patterns (Stage 17A)

### Basic Task with Retry

```python
from django_matt.tasks_native import task, retry
from pydantic import BaseModel

class EmailPayload(BaseModel):
    user_id: int
    template: str

@task(
    queue="email",
    retry=retry.exponential(max_retries=3, base_delay=2.0),
    timeout=30,
)
async def send_email(payload: EmailPayload) -> bool:
    user = await User.objects.aget(id=payload.user_id)
    return await deliver_email(user, payload.template)

# Enqueue — payload validated at call time, NOT at execution time
await send_email.delay(EmailPayload(user_id=1, template="welcome"))
```

### Retry Policies

```python
from django_matt.tasks_native import retry

# Exponential backoff: 2s, 4s, 8s, ...
retry.exponential(max_retries=5, base_delay=2.0, max_delay=120.0)

# Linear: 5s, 10s, 15s, ...
retry.linear(max_retries=3, step=5.0)

# Fixed: always 10s
retry.fixed(max_retries=3, delay=10.0)
```

### Periodic Tasks

```python
from django_matt.tasks_native import periodic_task
from django_matt.tasks_native.scheduling import crontab, every

@periodic_task(schedule=crontab(hour=9, minute=0))     # Daily at 9 AM
async def morning_digest():
    ...

@periodic_task(schedule=crontab(day_of_week=1, hour=9))  # Mondays at 9 AM
async def weekly_report():
    ...

@periodic_task(schedule=every(minutes=15))             # Interval
async def refresh_cache():
    ...
```

## Slim Mode Patterns

### Control Module Loading
```python
# settings.py — only load what you need
DJANGO_MATT = {
    "SLIM_MODE": {
        "mode": "slim",                          # "full", "slim", "minimal", "auto"
        "enabled_modules": ["auth", "billing"],   # only these + core
        "disabled_modules": [],
        "lazy_imports": True,                     # defer heavy modules
    }
}

# Or use "auto" mode to detect from settings
DJANGO_MATT = {
    "SLIM_MODE": {"mode": "auto"},
    "JWT_AUTH": {"SECRET_KEY": "..."},  # auto-detects auth module needed
    "BILLING": {"PROVIDER": "stripe"},  # auto-detects billing module needed
}
```


## Project Structure Patterns

### Modular App Layout (Required)

Every Django Matt project uses package-based apps. NEVER use Django's flat `models.py`/`views.py` files.

```
myapp/
├── models/          # One model per file, ~40 lines each
│   ├── __init__.py  # re-exports: from .post import Post
│   ├── post.py
│   └── comment.py
├── schemas/         # Pydantic schemas, one per model
│   ├── __init__.py
│   ├── post_schema.py     # PostSchema, CreatePostSchema, UpdatePostSchema
│   └── comment_schema.py
├── controllers/     # Thin HTTP adapters — one per resource
│   ├── __init__.py
│   ├── post_controller.py
│   └── comment_controller.py
├── services/        # Business logic — one CRUDService per model
│   ├── __init__.py
│   ├── post_service.py
│   └── comment_service.py
├── admin/           # Django admin configs
│   ├── __init__.py
│   ├── post_admin.py
│   └── comment_admin.py
└── tests/           # pytest + Factory Boy
    ├── conftest.py
    ├── test_post.py
    └── factories/
        ├── __init__.py
        ├── post_factory.py
        └── comment_factory.py
```

### Service Layer Pattern (Mandatory)

Controllers delegate all logic to services. Controllers handle HTTP; services handle domain logic.

```python
# services/post_service.py
from django_matt.services import CRUDService, ConflictError

class PostService(CRUDService["Post"]):
    model = Post

    def get_queryset(self):
        return super().get_queryset().select_related("created_by")

    async def list_published(self, *, page: int = 1, page_size: int = 20):
        return await self.list(
            page=page, page_size=page_size,
            status=Post.Status.PUBLISHED, ordering="-published_at",
        )

    async def publish(self, pk: int, user) -> Post:
        post = await self.get(pk)
        if post.status == Post.Status.PUBLISHED:
            raise ConflictError(f"Post {pk} is already published")
        return await self.update(pk, {
            "status": Post.Status.PUBLISHED,
            "published_at": timezone.now(),
        }, user=user)

    async def get_by_slug(self, slug: str) -> Post:
        return await self.get_by(slug=slug, status=Post.Status.PUBLISHED)
```

```python
# controllers/post_controller.py
@api.controller("/posts", tags=["Blog"])
class PostController(APIController):
    def __init__(self):
        self.service = PostService()

    @get("/")
    async def list_posts(self, request, page: int = 1):
        items, total = await self.service.list_published(page=page)
        return {"items": items, "total": total, "page": page}

    @get("/{slug}")
    async def get_post(self, request, slug: str):
        return await self.service.get_by_slug(slug)

    @post("/{id}/publish")
    async def publish_post(self, request, id: int):
        return await self.service.publish(id, user=request.user)
```

### Module Exports Pattern

Always export in `__init__.py`:
```python
# models/__init__.py
from .post import Post
from .comment import Comment

__all__ = ["Post", "Comment"]
```

```python
# controllers/__init__.py
from .post_controller import PostController
from .comment_controller import CommentController

__all__ = ["PostController", "CommentController"]
```

### Naming Conventions

| What | Pattern | Example |
|------|---------|---------|
| Model file | `{model}.py` | `post.py` |
| Schema file | `{model}_schema.py` | `post_schema.py` |
| Controller file | `{model}_controller.py` | `post_controller.py` |
| Service file | `{model}_service.py` | `post_service.py` |
| Admin file | `{model}_admin.py` | `post_admin.py` |
| Test file | `test_{model}.py` | `test_post.py` |
| Factory file | `{model}_factory.py` | `post_factory.py` |

| Class type | Pattern | Example |
|------|---------|---------|
| Model | PascalCase | `Post` |
| Schema | PascalCase + Schema | `PostSchema`, `CreatePostSchema` |
| Controller | PascalCase + Controller | `PostController` |
| Service | PascalCase + Service | `PostService` |

### URL Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Collection | Plural noun | `/posts` |
| Single resource | `/{resource_id}` | `/posts/{post_id}` |
| Sub-resource action | Verb or noun | `/posts/{id}/publish` |
| Nested | `/{parent}/{parent_id}/{child}` | `/users/{user_id}/posts` |

### Two-Step Workflow

```bash
# 1. Scaffold the app structure
python manage.py startapp blog --models Post Comment Tag

# 2. Edit models to add real fields

# 3. Migrate
python manage.py makemigrations blog && python manage.py migrate

# 4. Regenerate everything from real models
python manage.py generate_crud blog.Post --full
```

## Secrets Management Patterns

### Multi-Backend Secret Loading
```python
from django_matt.secrets import get_secrets_manager, EnvBackend, VaultBackend

# Configure in settings
DJANGO_MATT_SECRETS = {
    "backends": [
        {"backend": "env"},                          # check env vars first
        {"backend": "vault", "url": "https://..."},  # fall back to Vault
    ]
}

# Or programmatically
manager = get_secrets_manager()
db_password = await manager.get("DB_PASSWORD")
```

## Introspection / Health Check Patterns

### Add Health Endpoints
```python
# urls.py
from django_matt.introspection import get_health_urls

urlpatterns = [
    path("api/", api.urls),
    *get_health_urls(),  # adds /health/, /health/ready/, /health/live/
]

# Or use middleware for /health short-circuit
MIDDLEWARE = [
    "django_matt.introspection.HealthCheckMiddleware",
    ...
]
```

# Core API Reference

The core module provides the fundamental building blocks for Django Matt applications.

## DjangoMattAPI

The main API class for creating Django Matt applications.

```python
from django_matt import DjangoMattAPI

api = DjangoMattAPI(
    title="My API",
    version="1.0.0",
    description="API description",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | `"Django Matt API"` | API title for OpenAPI docs |
| `version` | `str` | `"1.0.0"` | API version |
| `description` | `str` | `""` | API description |
| `prefix` | `str` | `""` | URL prefix for all routes |
| `tags` | `list[str]` | `None` | Default tags for routes |
| `docs_url` | `str \| None` | `"/docs"` | Swagger UI URL (None to disable) |
| `redoc_url` | `str \| None` | `"/redoc"` | ReDoc URL (None to disable) |
| `openapi_url` | `str \| None` | `"/openapi.json"` | OpenAPI schema URL |
| `terms_of_service` | `str \| None` | `None` | ToS URL for OpenAPI |
| `contact` | `dict` | `None` | Contact info for OpenAPI |
| `license_info` | `dict` | `None` | License info for OpenAPI |
| `servers` | `list[dict]` | `None` | Server list for OpenAPI |
| `auth` | `Any` | `None` | Default authentication |
| `csrf` | `bool` | `False` | Enable CSRF protection |

### Methods

#### `@api.get(path, **kwargs)`

Register a GET endpoint.

```python
@api.get("/users")
async def list_users(request):
    return []

@api.get("/users/{user_id}", response=UserSchema)
async def get_user(request, user_id: int):
    return await User.objects.aget(id=user_id)
```

#### `@api.post(path, **kwargs)`

Register a POST endpoint.

```python
@api.post("/users", response={201: UserSchema})
async def create_user(request, data: UserCreateSchema):
    user = await User.objects.acreate(**data.model_dump())
    return 201, user
```

#### `@api.put(path, **kwargs)`

Register a PUT endpoint.

#### `@api.patch(path, **kwargs)`

Register a PATCH endpoint.

#### `@api.delete(path, **kwargs)`

Register a DELETE endpoint.

#### `register_controller(controller_class)`

Register a controller class.

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get

class UserController(APIController):
    prefix = "/users"
    tags = ["Users"]

    @get("/")
    async def list(self, request):
        return []

api.register_controller(UserController)
```

#### `include_router(router, prefix="")`

Include routes from another router.

```python
users_router = APIRouter(prefix="/users")
api.include_router(users_router)
```

#### `exception_handler(exc_class)`

Register a custom exception handler.

```python
@api.exception_handler(CustomError)
def handle_custom_error(request, exc):
    return JsonResponse({"error": str(exc)}, status=400)
```

---

## APIRouter

Modular router for grouping related endpoints.

```python
from django_matt import APIRouter

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/")
async def list_users(request):
    return []
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prefix` | `str` | `""` | URL prefix for all routes |
| `tags` | `list[str]` | `None` | Default tags for routes |

---

## Controllers

### APIController

Base class for API controllers.

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get, post
from django_matt.permissions import IsAuthenticated

class ProductController(APIController):
    prefix = "/products"
    tags = ["Products"]
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.service = ProductService()
        super().__init__()

    @get("/")
    async def list(self, request):
        return [p async for p in Product.objects.all()]

    @get("/<int:id>")
    async def retrieve(self, request, id: int):
        return await Product.objects.aget(id=id)

api.register_controller(ProductController)
```

### Class Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `prefix` | `str` | URL prefix |
| `tags` | `list[str]` | OpenAPI tags |
| `permission_classes` | `list[Permission]` | Permission classes for all endpoints |

### Methods

| Method | Description |
|--------|-------------|
| `get_queryset()` | Override to customize the base queryset |
| `get_object(pk)` | Get a single object by primary key |
| `check_permissions(request)` | Check if request has permission |

### CRUDController

Controller with built-in CRUD operations (`list`, `retrieve`, `create`, `update`, `partial_update`, `delete`, `bulk_create`, `bulk_update`, `exists`, `count`).

```python
from django_matt.core.controller import CRUDController

class ProductController(CRUDController):
    prefix = "/products"
    tags = ["Products"]
    model = Product
    schema = ProductSchema
    create_schema = ProductCreateSchema
    update_schema = ProductUpdateSchema

api.register_controller(ProductController)
```

---

## Schemas

### ModelSchema / Schema

`ModelSchema` is the base schema class for django-matt. `Schema` is a legacy alias for `ModelSchema`. Both auto-generate Pydantic fields from a Django model when a `class Config` is provided.

```python
from django_matt.core.schema import ModelSchema

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "email", "first_name", "last_name", "created_at"]
```

#### `from_orm_fast(instance)` — Skip Re-Validation

For already-trusted ORM data (e.g., objects returned by a queryset), re-running full Pydantic validation is unnecessary overhead. `from_orm_fast()` uses `model_construct()` to bypass the validator pass:

```python
# Standard ORM serialization (full validation — slower):
schema = UserSchema.from_orm(user_instance)

# Fast ORM serialization (no re-validation — faster for list serialization):
schema = UserSchema.from_orm_fast(user_instance)
# Internally: UserSchema.model_construct(**extracted_fields)

# Bulk async serialization (for querysets):
schemas = await UserSchema.afrom_queryset(User.objects.all())
```

All built-in views (`ListView`, `ReadView`, etc.) call `from_orm_fast()` automatically. Only use `from_orm()` when you need to run validators on ORM data (e.g., for custom constraint checks).

### Config Options

| Option | Type | Description |
|--------|------|-------------|
| `model` | `Model` | Django model class |
| `include` | `list[str] \| "__all__"` | Fields to include (`None` = all) |
| `exclude` | `set[str]` | Fields to exclude |
| `optional` | `set[str] \| "__all__"` | Fields to make `Optional` |
| `depth` | `int` | FK depth (FKs default to int PK) |
| `model_fk_use_pks` | `bool` | Use `author_id` column name instead of `author` |

### Schema Functions

#### `create_schema_from_model()`

Dynamically create a schema from a model.

```python
from django_matt.core.schema import create_schema_from_model

UserSchema = create_schema_from_model(
    User,
    name="UserSchema",
    include=["id", "email", "first_name", "last_name"],
)

# With optional and excluded fields
UserDetailSchema = create_schema_from_model(
    User,
    name="UserDetailSchema",
    include=None,           # all fields
    exclude=["password"],
    optional=["last_name"],
)
```

#### `model_validator()`

Field-level validator decorator for `ModelSchema` subclasses (wraps Pydantic's `field_validator`):

```python
from django_matt.core.schema import ModelSchema, model_validator

class UserCreateSchema(ModelSchema):
    class Config:
        model = User
        include = ["email", "username"]

    @model_validator("email")
    def validate_email(cls, v):
        if not v.endswith("@company.com"):
            raise ValueError("Must be a company email")
        return v
```

---

## Errors

### Exception Classes

| Exception | Status Code | Description |
|-----------|-------------|-------------|
| `APIError` | 500 | Base exception class |
| `NotFoundAPIError` | 404 | Resource not found |
| `ValidationAPIError` | 422 | Validation failed |
| `AuthenticationAPIError` | 401 | Authentication required |
| `PermissionAPIError` | 403 | Permission denied |
| `RateLimitAPIError` | 429 | Rate limit exceeded |
| `ConfigurationError` | 500 | Framework misconfiguration |

`PermissionDeniedAPIError` is an alias for `PermissionAPIError`.

### Usage

```python
from django_matt.core.errors import (
    NotFoundAPIError,
    ValidationAPIError,
    AuthenticationAPIError,
    PermissionAPIError,
)

@get("/<int:user_id>")
async def get_user(self, request, user_id: int):
    try:
        user = await User.objects.aget(id=user_id)
    except User.DoesNotExist:
        raise NotFoundAPIError(f"User {user_id} not found")
    return user

@post("/")
async def create_user(self, request, data: UserCreateSchema):
    if await User.objects.filter(email=data.email).aexists():
        raise ValidationAPIError(
            "Email already exists",
            errors=[{"field": "email", "message": "Already in use"}],
        )
    ...
```

### Error Response Format

All errors use this JSON envelope:

```json
{
    "status": 404,
    "detail": "User 42 not found",
    "code": "not_found",
    "hint": null,
    "extra": null
}
```

### Custom Exceptions

```python
from django_matt.core.errors import APIError

class InsufficientFundsError(APIError):
    def __init__(self, required: float, available: float):
        super().__init__(
            message=f"Need {required}, have {available}",
            status_code=402,
            code="insufficient_funds",
            context={"required": required, "available": available},
        )
```

### ErrorHandler

Subclass `ErrorHandler` to add custom capture logic:

```python
from django_matt.core.errors import ErrorHandler, APIError

class CustomErrorHandler(ErrorHandler):
    def capture_exception(self, exc, request=None):
        if isinstance(exc, MyCustomException):
            raise APIError(
                message=str(exc),
                status_code=400,
                code="custom_error",
            ) from exc
        return super().capture_exception(exc, request)
```

---

## Route Decorators

Available from `django_matt.core.router`:

```python
from django_matt.core.router import get, post, put, patch, delete
```

### Decorator Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | URL path (can include `{param}` placeholders) |
| `response` | `type \| dict` | Response schema or status-schema mapping |
| `tags` | `list[str]` | OpenAPI tags |
| `summary` | `str` | OpenAPI summary |
| `description` | `str` | OpenAPI description |
| `deprecated` | `bool` | Mark as deprecated in docs |
| `operation_id` | `str` | Custom OpenAPI operation ID |

### Response Types

```python
# Single response type
@api.get("/user", response=UserSchema)
async def get_user(request): ...

# Multiple status codes
@api.post("/users", response={201: UserSchema, 400: ErrorSchema})
async def create_user(request, data: UserCreate):
    if error:
        return 400, ErrorSchema(message="Error")
    return 201, user

# List response
@api.get("/users", response=list[UserSchema])
async def list_users(request): ...
```

---

## Version Detection

Django Matt automatically detects the Django version for feature compatibility.

```python
from django_matt.core import DJANGO_VERSION, DJANGO_5_2_PLUS, DJANGO_6_0_PLUS

if DJANGO_5_2_PLUS:
    # Use Django 5.2+ features like connection pooling
    pass

if DJANGO_6_0_PLUS:
    # Use Django 6.0+ features
    pass
```

### Constants

| Constant | Type | Description |
|----------|------|-------------|
| `DJANGO_VERSION` | `tuple[int, int]` | Current Django version as tuple, e.g., `(5, 2)` |
| `DJANGO_5_2_PLUS` | `bool` | `True` if Django >= 5.2 |
| `DJANGO_6_0_PLUS` | `bool` | `True` if Django >= 6.0 |

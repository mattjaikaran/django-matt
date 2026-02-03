# Core API Reference

The core module provides the fundamental building blocks for Django Matt applications.

## MattAPI

The main API class for creating Django Matt applications.

```python
from django_matt import MattAPI

api = MattAPI(
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

#### `@api.controller(prefix, **kwargs)`

Register a controller class.

```python
@api.controller("/users", tags=["Users"])
class UserController(APIController):
    ...
```

#### `register_controller(cls, prefix="")`

Register a controller class programmatically.

```python
api.register_controller(UserController, prefix="/users")
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
from django_matt import APIController, MattAPI

api = MattAPI()

@api.controller("/products", tags=["Products"])
class ProductController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list(self):
        return await Product.objects.all()

    @api.get("/{id}")
    async def retrieve(self, id: int):
        return await Product.objects.aget(id=id)
```

### Class Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `permission_classes` | `list[Permission]` | Permission classes for all endpoints |
| `tags` | `list[str]` | OpenAPI tags |
| `prefix` | `str` | URL prefix |

### Methods

| Method | Description |
|--------|-------------|
| `get_queryset()` | Override to customize the base queryset |
| `get_object(pk)` | Get a single object by primary key |
| `check_permissions(request)` | Check if request has permission |

### CRUDController

Controller with built-in CRUD operations.

```python
from django_matt import CRUDController

@api.controller("/products")
class ProductController(CRUDController):
    model = Product
    schema = ProductSchema
    create_schema = ProductCreateSchema
    update_schema = ProductUpdateSchema
```

---

## Schemas

### Schema

Base schema class (alias for `pydantic.BaseModel`).

```python
from django_matt import Schema

class UserSchema(Schema):
    id: int
    email: str
    name: str
```

### ModelSchema

Schema that automatically generates fields from Django models.

```python
from django_matt import ModelSchema
from myapp.models import User

class UserSchema(ModelSchema):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'created_at']
        # Or use exclude
        # exclude = ['password']

class UserDetailSchema(ModelSchema):
    class Meta:
        model = User
        fields = '__all__'  # All fields except relations
```

### Meta Options

| Option | Type | Description |
|--------|------|-------------|
| `model` | `Model` | Django model class |
| `fields` | `list[str] \| "__all__"` | Fields to include |
| `exclude` | `list[str]` | Fields to exclude |
| `optional_fields` | `list[str]` | Fields that are optional |

### Schema Functions

#### `create_schema_from_model()`

Dynamically create a schema from a model.

```python
from django_matt import create_schema_from_model

UserSchema = create_schema_from_model(
    User,
    fields=['id', 'email', 'username'],
    name='UserSchema',
)
```

#### `model_validator()`

Decorator for custom model validation.

```python
from django_matt import ModelSchema, model_validator

class UserCreateSchema(ModelSchema):
    class Meta:
        model = User
        fields = ['email', 'username']

    @model_validator(mode='after')
    def validate_unique_email(self):
        if User.objects.filter(email=self.email).exists():
            raise ValueError('Email already exists')
        return self
```

---

## Errors

### Exception Classes

| Exception | Status Code | Description |
|-----------|-------------|-------------|
| `APIError` | 500 | Base exception class |
| `NotFoundError` | 404 | Resource not found |
| `ValidationError` | 400 | Validation failed |
| `UnauthorizedError` | 401 | Authentication required |
| `ForbiddenError` | 403 | Permission denied |
| `ConflictError` | 409 | Resource conflict |
| `RateLimitError` | 429 | Rate limit exceeded |

### Usage

```python
from django_matt.core.errors import NotFoundError, ValidationError

@api.get("/users/{user_id}")
async def get_user(request, user_id: int):
    try:
        user = await User.objects.aget(id=user_id)
    except User.DoesNotExist:
        raise NotFoundError(f"User {user_id} not found")
    return user

@api.post("/users")
async def create_user(request, data: UserCreateSchema):
    if await User.objects.filter(email=data.email).aexists():
        raise ValidationError("Email already exists", field="email")
    ...
```

### Custom Exceptions

```python
from django_matt.core.errors import APIError

class InsufficientFundsError(APIError):
    status_code = 402
    default_message = "Insufficient funds"

    def __init__(self, required: float, available: float):
        super().__init__(f"Need {required}, have {available}")
        self.required = required
        self.available = available
```

### ErrorHandler

Customize error response format.

```python
from django_matt.core.errors import ErrorHandler

class CustomErrorHandler(ErrorHandler):
    def format_error(self, error: APIError) -> dict:
        return {
            "success": False,
            "error": {
                "code": error.status_code,
                "message": str(error),
                "type": type(error).__name__,
            }
        }

# Use in API
api = MattAPI(error_handler=CustomErrorHandler())
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

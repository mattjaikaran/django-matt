# Complete API Reference

This document provides a comprehensive reference for all public APIs in django-matt.

## Quick Navigation

| Module | Description |
|--------|-------------|
| [MattAPI](#mattapi) | Main API entry point |
| [Controllers](#controllers) | Class-based API handlers |
| [Schemas](#schemas) | Pydantic data validation |
| [Views](#views) | Composable CRUD views |
| [Authentication](#authentication) | JWT, OAuth, Passkeys, SSO |
| [Permissions](#permissions) | Access control |
| [Errors](#errors) | Exception handling |

---

## MattAPI

The main entry point for creating API applications.

### Constructor

```python
from django_matt import MattAPI

api = MattAPI(
    title="My API",           # OpenAPI title
    version="1.0.0",          # API version
    description="My API",     # OpenAPI description
    docs_url="/docs",         # Swagger UI URL (None to disable)
    redoc_url="/redoc",       # ReDoc URL (None to disable)
    openapi_url="/openapi.json",  # OpenAPI schema URL
)
```

### Route Decorators

```python
# Basic routes
@api.get("/items")
async def list_items(request):
    return {"items": []}

@api.post("/items")
async def create_item(request, data: ItemSchema):
    return {"id": 1, **data.dict()}

@api.get("/items/{id}")
async def get_item(request, id: int):
    return {"id": id}

@api.put("/items/{id}")
async def update_item(request, id: int, data: ItemSchema):
    return {"id": id, **data.dict()}

@api.patch("/items/{id}")
async def partial_update(request, id: int, data: ItemPatchSchema):
    return {"id": id}

@api.delete("/items/{id}")
async def delete_item(request, id: int):
    return {"success": True}
```

### Route Options

```python
@api.get(
    "/items",
    tags=["Items"],              # OpenAPI tags
    summary="List all items",    # OpenAPI summary
    description="...",           # OpenAPI description
    response={200: List[ItemSchema]},  # Response schema
    deprecated=False,            # Mark as deprecated
    operation_id="listItems",    # Custom operation ID
    include_in_schema=True,      # Include in OpenAPI
)
async def list_items(request):
    ...
```

### Registering Controllers

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get

class UserController(APIController):
    prefix = "/users"
    tags = ["Users"]

    @get("/")
    async def list(self, request):
        return {"users": []}

api.register_controller(UserController)
```

---

## Controllers

### APIController

Base class for grouping related endpoints.

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get, post
from django_matt.core.errors import NotFoundAPIError
from django_matt.permissions import IsAuthenticated

class ProductController(APIController):
    prefix = "/products"
    tags = ["Products"]
    # Class-level permissions
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.service = ProductService()
        super().__init__()

    @get("/")
    async def list(self, request):
        """List all products."""
        products = await self.service.get_all()
        return {"products": products}

    @get("/<int:id>")
    async def detail(self, request, id: int):
        """Get product by ID."""
        product = await self.service.get(id)
        if not product:
            raise NotFoundAPIError("Product not found")
        return product

    @post("/")
    async def create(self, request, data: ProductCreate):
        """Create a new product."""
        product = await self.service.create(data)
        return product

api.register_controller(ProductController)
```

### CRUDController

Controller with built-in CRUD operations.

```python
from django_matt.core.controller import CRUDController
from django_matt.core.router import post

class ProductController(CRUDController):
    prefix = "/products"
    tags = ["Products"]
    model = Product
    schema = ProductSchema
    create_schema = ProductCreate
    update_schema = ProductUpdate

    # Customize queryset
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_staff:
            qs = qs.filter(is_active=True)
        return qs

    # Add custom endpoints
    @post("/<int:id>/publish")
    async def publish(self, request, id: int):
        product = await self.get_object(id)
        product.is_published = True
        await product.asave()
        return {"status": "published"}

api.register_controller(ProductController)
```

#### CRUDController Options

| Option | Type | Description |
|--------|------|-------------|
| `model` | `Model` | Django model class |
| `schema` | `Schema` | Response schema |
| `create_schema` | `Schema` | Create request schema |
| `update_schema` | `Schema` | Update request schema |
| `lookup_field` | `str` | Field for object lookup (default: `"pk"`) |
| `pagination_class` | `Pagination` | Custom pagination |
| `filter_backends` | `list` | Filter backends |

---

## Schemas

### ModelSchema / Schema

`ModelSchema` is the base schema class. Use it to get `from_orm_fast()` for high-performance list serialization:

```python
from django_matt.core.schema import ModelSchema

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "email", "first_name", "last_name"]

# Fast ORM serialization (uses model_construct — skips re-validation):
schema = UserSchema.from_orm_fast(user_orm_instance)

# Standard ORM serialization (full validation):
schema = UserSchema.from_orm(user_orm_instance)

# Bulk async serialization (used internally by ListView):
schemas = await UserSchema.afrom_queryset(User.objects.all())
```

`from_orm_fast()` is called automatically by all built-in views (`ListView`, `ReadView`, etc.) for performance.

### ModelSchema

Auto-generate Pydantic schemas from Django models. Use `class Config` (not `class Meta`) with `include` (not `fields`):

```python
from django_matt.core.schema import ModelSchema
from myapp.models import User

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "email", "first_name", "last_name", "created_at"]

class UserCreateSchema(ModelSchema):
    class Config:
        model = User
        include = ["email", "first_name", "last_name", "password"]

class UserUpdateSchema(ModelSchema):
    class Config:
        model = User
        include = ["first_name", "last_name", "email"]
        optional = "__all__"  # All fields optional for partial updates
```

### Schema Functions

```python
from django_matt.core.schema import create_schema_from_model

# Generate schema dynamically
UserSchema = create_schema_from_model(
    User,
    name="UserSchema",
    include=["id", "email", "first_name", "last_name"],
)

# With excluded and optional fields
UserSchema = create_schema_from_model(
    User,
    name="UserSchema",
    include=None,                    # include all fields
    exclude=["password", "is_staff"],
    optional=["last_name"],
)
```

### Validation

```python
from pydantic import BaseModel, field_validator, model_validator

class UserCreate(BaseModel):
    email: str
    password: str
    password_confirm: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.lower()

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.password != self.password_confirm:
            raise ValueError("Passwords don't match")
        return self
```

---

## Views

Composable CRUD views for rapid API development.

### ListView

`ListView` is a descriptor instance assigned on an `APIViewSet` subclass:

```python
from django_matt.views import APIViewSet, ListView

class UserViewSet(APIViewSet):
    model = User
    prefix = "users"
    tags = ["Users"]
    default_response_schema = UserSchema

    list_users = ListView(
        filter_fields=["is_active", "role"],
        search_fields=["email", "first_name", "last_name"],
        page_size=20,
    )
```

### CreateView

```python
from django_matt.views import APIViewSet, CreateView

class UserViewSet(APIViewSet):
    model = User
    prefix = "users"
    default_response_schema = UserSchema

    create_user = CreateView(request_schema=UserCreate)

    async def before_create(self, request, data):
        data["created_by_id"] = request.user.id
        return data

    async def after_create(self, request, instance):
        await send_welcome_email(instance)
        return instance
```

### ReadView

```python
from django_matt.views import APIViewSet, ReadView

class UserViewSet(APIViewSet):
    model = User
    prefix = "users"
    default_response_schema = UserSchema
    lookup_field = "id"   # default
    lookup_type = "int"   # default

    read_user = ReadView()
```

### UpdateView

```python
from django_matt.views import APIViewSet, UpdateView

class UserViewSet(APIViewSet):
    model = User
    prefix = "users"
    default_response_schema = UserSchema

    update_user = UpdateView(request_schema=UserUpdate)

    async def perform_update(self, request, instance, data):
        for key, value in data.items():
            setattr(instance, key, value)
        await instance.asave()
        return instance
```

### DeleteView

```python
from django_matt.views import APIViewSet, DeleteView

class UserViewSet(APIViewSet):
    model = User
    prefix = "users"

    delete_user = DeleteView()

    async def perform_delete(self, request, instance):
        # Soft delete
        instance.is_active = False
        await instance.asave()
```

### APIViewSet

Combine views into a complete CRUD API:

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

class UserViewSet(APIViewSet):
    prefix = "users"
    tags = ["Users"]
    model = User
    default_response_schema = UserSchema

    list_users = ListView()
    create_user = CreateView(request_schema=UserCreate)
    read_user = ReadView()
    update_user = UpdateView(request_schema=UserUpdate)
    delete_user = DeleteView()

# Register URL patterns
urlpatterns = [
    path("api/", include(UserViewSet.as_urls())),
]
```

---

## Authentication

### JWT Authentication

```python
from django_matt.auth import jwt_required, jwt_optional, create_token_pair

# Protect endpoints
@api.get("/profile")
@jwt_required
async def profile(request):
    return {"user": request.user.email}

# Optional auth
@api.get("/items")
@jwt_optional
async def items(request):
    if request.user.is_authenticated:
        return {"items": get_user_items(request.user)}
    return {"items": get_public_items()}

# Generate tokens
from django_matt.auth import create_token_pair

async def login(request, credentials: LoginSchema):
    from asgiref.sync import sync_to_async
    user = await sync_to_async(authenticate)(**credentials.model_dump())
    if user:
        tokens = create_token_pair(user)
        return {
            "access": tokens.access_token,
            "refresh": tokens.refresh_token,
        }
    raise AuthenticationAPIError("Invalid credentials")
```

### JWT Settings

```python
# settings.py
DJANGO_MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ALGORITHM": "HS256",
    "SECRET_KEY": SECRET_KEY,  # Defaults to Django's SECRET_KEY
    "AUTH_HEADER_TYPES": ["Bearer"],
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "sub",
}
```

### OAuth

```python
from django_matt.auth.oauth import OAuthController, GoogleOAuthProvider

# Register OAuth controller
api.register_controller(OAuthController)

# Configure providers in settings
MATT_OAUTH = {
    "google": {
        "client_id": "...",
        "client_secret": "...",
        "scopes": ["email", "profile"],
    },
    "github": {
        "client_id": "...",
        "client_secret": "...",
    },
}
```

### Passkeys

```python
from django_matt.auth.passkeys import PasskeyController

# Register passkey controller
api.register_controller(PasskeyController)

# Endpoints provided:
# POST /auth/passkeys/register/options - Get registration options
# POST /auth/passkeys/register/verify - Verify registration
# POST /auth/passkeys/authenticate/options - Get auth options
# POST /auth/passkeys/authenticate/verify - Verify authentication
```

---

## Permissions

### Built-in Permission Classes

```python
from django_matt.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAdmin,
    IsStaff,
    IsOwner,
    HasRole,
    HasPermission,
)

class AdminController(APIController):
    prefix = "/admin"
    tags = ["Admin"]
    permission_classes = [IsAdmin]

class UserController(APIController):
    prefix = "/users"
    tags = ["Users"]
    permission_classes = [IsAuthenticated]

    @get("/<int:id>")
    @IsOwner(owner_field="id")  # User can only access their own
    async def detail(self, request, id: int):
        ...

api.register_controller(AdminController)
api.register_controller(UserController)
```

### Custom Permissions

```python
from django_matt.permissions import BasePermission

class IsProjectMember(BasePermission):
    async def has_permission(self, request, view):
        return request.user.is_authenticated

    async def has_object_permission(self, request, view, obj):
        return await obj.members.filter(id=request.user.id).aexists()
```

### Permission Decorators

```python
from django_matt.permissions import authenticated, requires_permission, requires_role

@api.get("/admin/stats")
@authenticated
@requires_role("admin")
async def admin_stats(request):
    ...

@api.post("/posts/{id}/publish")
@requires_permission("posts.publish")
async def publish_post(request, id: int):
    ...
```

---

## Errors

### Error Classes

```python
from django_matt.core.errors import (
    APIError,
    NotFoundAPIError,
    ValidationAPIError,
    AuthenticationAPIError,
    PermissionDeniedAPIError,
    RateLimitAPIError,
)

# Basic usage
raise NotFoundAPIError("User not found")

# With field-level validation errors (list of dicts)
raise ValidationAPIError(
    message="Validation failed",
    errors=[{"field": "email", "message": "Invalid email format"}],
)

# Custom error
raise APIError(
    message="Payment failed",
    status_code=402,
    code="payment_failed",
    context={"reason": "Card declined"},
)
```

### Error Response Format

All errors return JSON in this format:

```json
{
    "status": 404,
    "detail": "User not found",
    "code": "not_found",
    "hint": null,
    "extra": null
}
```

### Custom Error Handler

Subclass `ErrorHandler` and override `capture_exception()` to add custom behaviour:

```python
from django_matt.core.errors import ErrorHandler, APIError

class CustomErrorHandler(ErrorHandler):
    def capture_exception(self, exc, request=None):
        if isinstance(exc, MyCustomException):
            # Re-wrap as a structured APIError
            raise APIError(
                message=str(exc),
                status_code=400,
                code="custom_error",
            ) from exc
        return super().capture_exception(exc, request)
```

---

## Pagination

### PageNumberPagination

```python
from django_matt.pagination import PageNumberPagination

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"
```

Response format:
```json
{
    "items": [...],
    "count": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
}
```

### CursorPagination

```python
from django_matt.pagination import CursorPagination

class TimelinePagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"
    cursor_query_param = "cursor"
```

---

## Type Generation

### TypeScript

```python
# Generate TypeScript types
python manage.py sync_types --target typescript --output frontend/src/types

# Generated output example:
# frontend/src/types/user.ts
"""
export interface User {
  id: number;
  email: string;
  name: string;
  createdAt: string;
}

export interface UserCreate {
  email: string;
  name: string;
  password: string;
}
"""
```

### Zod Schemas

```python
# Generate Zod validation schemas
python manage.py sync_types --target typescript --zod --output frontend/src/schemas

# Generated output:
"""
import { z } from 'zod';

export const UserSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  name: z.string(),
  createdAt: z.string(),
});

export type User = z.infer<typeof UserSchema>;
"""
```

### Swift

```python
# Generate Swift types for iOS
python manage.py sync_types --target swift --output ios/Models

# Generated output:
"""
struct User: Codable {
    let id: Int
    let email: String
    let name: String
    let createdAt: String
}
"""
```

---

## Testing

### APITestClient

```python
from django_matt.testing import APITestClient
import pytest

@pytest.fixture
def client():
    return APITestClient()

@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user)
    return client

async def test_list_users(auth_client):
    response = await auth_client.get("/api/users")
    assert response.status_code == 200
    assert "users" in response.json()

async def test_create_user(auth_client):
    response = await auth_client.post("/api/users", json={
        "email": "test@example.com",
        "name": "Test User",
    })
    assert response.status_code == 201
```

### Test Assertions

```python
from django_matt.testing import assert_status, assert_json_equal, assert_created

async def test_create_product(auth_client):
    response = await auth_client.post("/api/products", json={
        "name": "Widget",
        "price": 9.99,
    })

    assert_status(response, 201)
    assert_created(response)
    assert_json_equal(response, "name", "Widget")
```

### Factories

```python
from django_matt.testing import UserFactory, OrganizationFactory

@pytest.fixture
def user():
    return UserFactory(email="test@example.com")

@pytest.fixture
def org_with_members():
    org = OrganizationFactory()
    UserFactory.create_batch(5, organization=org)
    return org
```

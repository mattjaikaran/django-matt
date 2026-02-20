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

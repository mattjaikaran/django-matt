# Migrating from Django Ninja

This guide helps you migrate from Django Ninja (and its ecosystem packages) to django-matt. Since django-matt was designed as a Django Ninja successor, most concepts map directly.

## Package Replacement

| Django Ninja Package | django-matt Module |
|---------------------|-------------------|
| `django-ninja` | `django_matt.core` |
| `django-ninja-extra` | `django_matt.core.controller` |
| `django-ninja-jwt` | `django_matt.auth` |
| `ninja-schema` | `django_matt.core.schema` |
| `django-ninja-crud` | `django_matt.views` |

## Installation

```bash
# Remove old packages
uv remove django-ninja django-ninja-extra django-ninja-jwt ninja-schema django-ninja-crud

# Install django-matt
uv add django-matt
```

## API Class

### Django Ninja

```python
from ninja import NinjaAPI

api = NinjaAPI(
    title="My API",
    version="1.0.0",
    description="My API description",
)
```

### django-matt

```python
from django_matt import MattAPI

api = MattAPI(
    title="My API",
    version="1.0.0",
    description="My API description",
)
```

The API classes are nearly identical. Main differences:
- `MattAPI` has built-in auth support
- Additional configuration options for billing, tenancy, etc.

## Route Decorators

### Django Ninja

```python
from ninja import Router

router = Router()

@router.get("/users")
def list_users(request):
    return []

@router.post("/users")
def create_user(request, data: UserSchema):
    return data

@router.get("/users/{user_id}")
def get_user(request, user_id: int):
    return {"id": user_id}
```

### django-matt

```python
from django_matt import APIRouter

router = APIRouter()

@router.get("/users")
async def list_users(request):
    return []

@router.post("/users")
async def create_user(request, data: UserSchema):
    return data

@router.get("/users/{user_id}")
async def get_user(request, user_id: int):
    return {"id": user_id}
```

**Key difference**: django-matt encourages `async def` but supports both.

## Schemas

### Django Ninja / ninja-schema

```python
from ninja import Schema, ModelSchema

class UserSchema(Schema):
    id: int
    email: str
    name: str


class UserModelSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ['id', 'email', 'username']
```

### django-matt

```python
from django_matt import Schema, ModelSchema

class UserSchema(Schema):
    id: int
    email: str
    name: str


class UserModelSchema(ModelSchema):
    class Meta:
        model = User
        fields = ['id', 'email', 'username']
```

**Key difference**: django-matt uses `Meta` class (like Django) instead of `Config` class. Both Pydantic v2 compatible.

## Controllers (from django-ninja-extra)

### Django Ninja Extra

```python
from ninja_extra import NinjaExtraAPI, api_controller, http_get, http_post
from ninja_extra.permissions import IsAuthenticated

api = NinjaExtraAPI()

@api_controller("/users", tags=["Users"])
class UserController:
    permissions = [IsAuthenticated]

    @http_get("/")
    def list_users(self):
        return []

    @http_get("/{user_id}")
    def get_user(self, user_id: int):
        return {"id": user_id}

    @http_post("/")
    def create_user(self, data: UserSchema):
        return data


api.register_controllers(UserController)
```

### django-matt

```python
from django_matt import MattAPI, APIController, IsAuthenticated

api = MattAPI()

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list_users(self):
        return []

    @api.get("/{user_id}")
    async def get_user(self, user_id: int):
        return {"id": user_id}

    @api.post("/")
    async def create_user(self, data: UserSchema):
        return data
```

**Key differences**:
- Use `@api.controller` decorator
- Inherit from `APIController`
- Use `@api.get`/`@api.post` instead of `@http_get`/`@http_post`
- Use `permission_classes` instead of `permissions`

## JWT Authentication (from django-ninja-jwt)

### Django Ninja JWT

```python
# settings.py
NINJA_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# api.py
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.authentication import JWTAuth

api = NinjaExtraAPI(auth=JWTAuth())
api.register_controllers(NinjaJWTDefaultController)
```

### django-matt

```python
# settings.py
DJANGO_MATT_JWT = {
    'SECRET_KEY': SECRET_KEY,
    'ACCESS_TOKEN_LIFETIME': 3600,  # 60 minutes in seconds
    'REFRESH_TOKEN_LIFETIME': 604800,  # 7 days in seconds
}

# api.py
from django_matt import MattAPI
from django_matt.auth import AuthController

api = MattAPI()
api.register_controller(AuthController, prefix="/auth")
```

The built-in `AuthController` provides:
- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

## CRUD Views (from django-ninja-crud)

### Django Ninja CRUD

```python
from ninja_crud import views, viewsets

class ProductViewSet(viewsets.APIViewSet):
    model = Product

    list_products = views.ListView()
    create_product = views.CreateView()
    read_product = views.ReadView()
    update_product = views.UpdateView()
    delete_product = views.DeleteView()
```

### django-matt

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema

    list = ListView()
    create = CreateView()
    read = ReadView()
    update = UpdateView()
    delete = DeleteView()
```

**Key differences**:
- Pass `api` instance to ViewSet
- Specify `default_response_schema`
- Simpler attribute names

## Dependency Injection

### Django Ninja Extra

```python
from ninja_extra import api_controller
from ninja_extra.permissions import IsAuthenticated
from injector import inject

@api_controller("/products")
class ProductController:
    def __init__(self, product_service: ProductService = inject()):
        self.product_service = product_service
```

### django-matt

```python
from django_matt import APIController, Depends
from django_matt.di import inject

@api.controller("/products")
class ProductController(APIController):
    @inject
    def __init__(self, product_service: ProductService = Depends(ProductService)):
        self.product_service = product_service
```

Or use dependency injection in methods:

```python
@api.controller("/products")
class ProductController(APIController):
    @api.get("/")
    async def list_products(
        self,
        service: ProductService = Depends(ProductService),
    ):
        return await service.list_all()
```

## Response Types

### Django Ninja

```python
from ninja import Schema

class ErrorSchema(Schema):
    message: str

@api.get("/users/{user_id}", response={200: UserSchema, 404: ErrorSchema})
def get_user(request, user_id: int):
    try:
        user = User.objects.get(id=user_id)
        return user
    except User.DoesNotExist:
        return 404, {"message": "User not found"}
```

### django-matt

```python
from django_matt.core.errors import NotFoundError

@api.get("/users/{user_id}", response=UserSchema)
async def get_user(request, user_id: int):
    try:
        user = await User.objects.aget(id=user_id)
        return user
    except User.DoesNotExist:
        raise NotFoundError("User not found")
```

django-matt uses exceptions for error responses, which are automatically converted to proper HTTP responses.

## Query Parameters

### Django Ninja

```python
from ninja import Query

@api.get("/search")
def search(request, q: str = Query(...), page: int = Query(1)):
    return {"q": q, "page": page}
```

### django-matt

```python
from typing import Annotated
from pydantic import Field

@api.get("/search")
async def search(
    request,
    q: Annotated[str, Field(description="Search query")],
    page: int = 1,
):
    return {"q": q, "page": page}
```

Both work similarly. django-matt uses standard Python/Pydantic patterns.

## File Uploads

### Django Ninja

```python
from ninja import UploadedFile, File

@api.post("/upload")
def upload(request, file: UploadedFile = File(...)):
    return {"name": file.name, "size": file.size}
```

### django-matt

```python
from django_matt.files import UploadedFile, File

@api.post("/upload")
async def upload(request, file: UploadedFile = File(...)):
    return {"name": file.name, "size": file.size}
```

Nearly identical API.

## Pagination

### Django Ninja

```python
from ninja.pagination import paginate, PageNumberPagination

@api.get("/users")
@paginate(PageNumberPagination)
def list_users(request):
    return User.objects.all()
```

### django-matt

```python
from django_matt.pagination import PageNumberPagination

@api.get("/users")
async def list_users(request, pagination: PageNumberPagination = Depends()):
    queryset = User.objects.all()
    return await pagination.paginate(queryset)
```

Or with ViewSet:

```python
class UserViewSet(APIViewSet):
    list = ListView(pagination_class=PageNumberPagination)
```

## Authentication Decorators

### Django Ninja

```python
from ninja.security import HttpBearer

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        # Verify token
        return user

@api.get("/protected", auth=AuthBearer())
def protected(request):
    return {"user": request.auth.email}
```

### django-matt

```python
from django_matt.auth import jwt_required, jwt_optional

@api.get("/protected")
@jwt_required
async def protected(request):
    return {"user": request.user.email}

@api.get("/maybe-protected")
@jwt_optional
async def maybe_protected(request):
    if request.user.is_authenticated:
        return {"user": request.user.email}
    return {"user": "anonymous"}
```

## Migration Checklist

- [ ] Replace imports from `ninja` with `django_matt`
- [ ] Replace `NinjaAPI` with `MattAPI`
- [ ] Replace `ninja_extra` controllers with `APIController`
- [ ] Replace `@http_get`/`@http_post` with `@api.get`/`@api.post`
- [ ] Update schema `Config` classes to `Meta` classes
- [ ] Replace `ninja_jwt` with built-in `AuthController`
- [ ] Update dependency injection syntax
- [ ] Convert sync views to async (recommended)
- [ ] Update error handling to use exceptions
- [ ] Test all endpoints

## Import Mapping Reference

```python
# Old imports
from ninja import NinjaAPI, Schema, ModelSchema, Router, Query, Path, Body
from ninja.security import HttpBearer
from ninja.pagination import paginate
from ninja_extra import NinjaExtraAPI, api_controller, http_get, http_post
from ninja_extra.permissions import IsAuthenticated
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.authentication import JWTAuth

# New imports
from django_matt import (
    MattAPI,
    Schema,
    ModelSchema,
    APIRouter,
    APIController,
    IsAuthenticated,
)
from django_matt.auth import jwt_required, AuthController
from django_matt.pagination import PageNumberPagination
```

## Next Steps

- [Core Concepts](../core/routing.md) - Learn the routing system
- [Controllers](../core/controllers.md) - Deep dive into controllers
- [Authentication](../auth/overview.md) - Configure authentication

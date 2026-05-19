# Migrating from Django Ninja (Legacy)

> **This is a legacy guide.** The current, authoritative version is [`docs/migrations/from-ninja.md`](../migrations/from-ninja.md). This file is preserved for historical reference.

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

---

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

The API classes are nearly identical. `MattAPI` adds built-in auth controller registration, billing, OpenAPI, and more.

---

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

**Key difference**: django-matt encourages `async def` but supports sync too. The router supports `get`, `post`, `put`, `patch`, `delete` decorators.

---

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

**Key differences:**
- `Meta` class (like Django convention) instead of `Config` class
- `fields` instead of `model_fields`
- Both are Pydantic v2 models under the hood
- `ModelSchema` provides `from_orm()` and `from_orm_fast()` (skips re-validation for list serialization)

---

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

**Key differences:**
- `@api.controller` decorator (no separate `register_controllers` call needed)
- Inherit from `APIController` (provides error handling, query optimization)
- `@api.get` / `@api.post` instead of `@http_get` / `@http_post`
- `permission_classes` instead of `permissions`
- Async by default
- Auto error handling: `DoesNotExist` -> 404, `ValidationError` -> 422

---

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
    'ACCESS_TOKEN_LIFETIME': 3600,     # seconds
    'REFRESH_TOKEN_LIFETIME': 604800,
}

MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",
]

# api.py
from django_matt import MattAPI
from django_matt.auth import AuthController

api = MattAPI()
api.register_controller(AuthController)
```

The built-in `AuthController` provides:
- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

Plus token blacklisting, password reset, and magic links out of the box.

---

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

**Key differences:**
- Pass `api` instance to ViewSet
- Specify `default_response_schema`
- Simpler attribute names (`list` instead of `list_products`)
- Built-in lifecycle hooks: `before_create`, `after_create`, `before_delete`, etc.
- Built-in soft delete support via `SoftDeleteMixin`
- Bulk operations: `BulkCreateView`, `BulkUpdateView`, `BulkDeleteView`

---

## Dependency Injection

### Django Ninja Extra

```python
from ninja_extra import api_controller
from injector import inject

@api_controller("/products")
class ProductController:
    def __init__(self, product_service: ProductService = inject()):
        self.product_service = product_service
```

### django-matt

```python
from django_matt import APIController, Depends

@api.controller("/products")
class ProductController(APIController):
    @api.get("/")
    async def list_products(
        self,
        service: ProductService = Depends(ProductService),
    ):
        return await service.list_all()
```

Or register in the DI container for auto-resolution:

```python
from django_matt.di import container, Singleton

container.register(ProductService, lifetime=Singleton)

# Now auto-injected in any controller method with the right type hint
```

Built-in dependencies: `CurrentUser`, `CurrentRequest`, `CurrentOrg` (multi-tenant).

---

## Response Types

### Django Ninja

```python
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

@api.get("/users/{user_id}", response_model=UserSchema)
async def get_user(request, user_id: int):
    try:
        user = await User.objects.aget(id=user_id)
        return user
    except User.DoesNotExist:
        raise NotFoundError("User not found")
```

django-matt uses exceptions for error responses. They are automatically converted to JSON with the correct status code. No need to define error response schemas per endpoint.

---

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

---

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

Nearly identical API. django-matt adds S3/R2/MinIO storage backends.

---

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

class UserViewSet(APIViewSet):
    list = ListView(pagination_class=PageNumberPagination)
```

Or in a standalone endpoint:

```python
@api.get("/users")
async def list_users(request, pagination: PageNumberPagination = Depends()):
    queryset = User.objects.all()
    return await pagination.paginate(queryset)
```

Available: `PageNumberPagination`, `LimitOffsetPagination`, `CursorPagination`.

---

## Authentication Decorators

### Django Ninja

```python
from ninja.security import HttpBearer

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
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

Additional decorators: `@admin_required`, `@superuser_required`, `@with_roles("admin")`, `@with_permission("can_edit")`, `@api_key_required`.

---

## Complete Before/After Example

### Before: Django Ninja + Ecosystem

```python
# api.py
from ninja_extra import NinjaExtraAPI, api_controller, http_get, http_post, http_put, http_delete
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.authentication import JWTAuth
from ninja import Schema, ModelSchema

api = NinjaExtraAPI(auth=JWTAuth())
api.register_controllers(NinjaJWTDefaultController)

class NoteSchema(ModelSchema):
    class Config:
        model = Note
        model_fields = ['id', 'title', 'content', 'created_at']

class NoteCreateSchema(Schema):
    title: str
    content: str

@api_controller("/notes", tags=["Notes"])
class NoteController:
    permissions = [IsAuthenticated]

    @http_get("/")
    def list_notes(self, request):
        notes = Note.objects.filter(owner=request.user)
        return [NoteSchema.from_orm(n) for n in notes]

    @http_post("/")
    def create_note(self, request, data: NoteCreateSchema):
        note = Note.objects.create(**data.dict(), owner=request.user)
        return NoteSchema.from_orm(note)

    @http_get("/{note_id}")
    def get_note(self, request, note_id: int):
        try:
            return Note.objects.get(id=note_id, owner=request.user)
        except Note.DoesNotExist:
            return 404, {"message": "Not found"}

    @http_delete("/{note_id}")
    def delete_note(self, request, note_id: int):
        Note.objects.filter(id=note_id, owner=request.user).delete()
        return {"deleted": True}

api.register_controllers(NoteController)
```

### After: django-matt

```python
# schemas.py
from django_matt import ModelSchema, Schema

class NoteSchema(ModelSchema):
    class Meta:
        model = Note
        fields = ['id', 'title', 'content', 'created_at']

class NoteCreateSchema(Schema):
    title: str
    content: str

# api.py
from django_matt import MattAPI, APIController, IsAuthenticated
from django_matt.auth import AuthController
from django_matt.core.errors import NotFoundError

api = MattAPI()
api.register_controller(AuthController)

@api.controller("/notes", tags=["Notes"])
class NoteController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/", response_model=list[NoteSchema])
    async def list_notes(self):
        notes = []
        async for note in Note.objects.filter(owner=self.request.user):
            notes.append(NoteSchema.from_orm(note))
        return notes

    @api.post("/", response_model=NoteSchema)
    async def create_note(self, data: NoteCreateSchema):
        note = await Note.objects.acreate(
            **data.model_dump(), owner=self.request.user
        )
        return NoteSchema.from_orm(note)

    @api.get("/{note_id}", response_model=NoteSchema)
    async def get_note(self, note_id: int):
        try:
            note = await Note.objects.aget(id=note_id, owner=self.request.user)
        except Note.DoesNotExist:
            raise NotFoundError("Note not found")
        return NoteSchema.from_orm(note)

    @api.delete("/{note_id}")
    async def delete_note(self, note_id: int):
        await Note.objects.filter(
            id=note_id, owner=self.request.user
        ).adelete()
        return {"deleted": True}
```

---

## Migration Checklist

- [ ] Replace `NinjaAPI` / `NinjaExtraAPI` with `MattAPI`
- [ ] Replace `ninja` imports with `django_matt` imports
- [ ] Replace `@api_controller` with `@api.controller` + `APIController` base class
- [ ] Replace `@http_get`/`@http_post` with `@api.get`/`@api.post`
- [ ] Update schema `Config` classes to `Meta` classes
- [ ] Replace `model_fields` with `fields`
- [ ] Replace `ninja_jwt` with built-in `AuthController`
- [ ] Update `permissions` to `permission_classes`
- [ ] Convert sync views to async (use `aget`, `asave`, `adelete`)
- [ ] Replace `return status_code, error_dict` with `raise` error exceptions
- [ ] Update dependency injection syntax to use `Depends()`
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
from django_matt.di import Depends
```

---

## Next Steps

- [Core Concepts](../core/routing.md) -- Routing system
- [Controllers](../core/controllers.md) -- Deep dive into controllers
- [Authentication](../auth/overview.md) -- JWT, OAuth, SSO, Passkeys
- [Migration from DRF](from-drf.md) -- If also using DRF
- [Framework Comparison](../comparison.md) -- See how django-matt compares

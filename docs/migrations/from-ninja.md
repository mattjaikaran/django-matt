# Migrating from Django Ninja to django-matt

django-matt was designed as a Django Ninja successor. The surface area is intentionally similar — most migrations are mechanical find-and-replace plus a few targeted changes. This guide covers the ecosystem packages too: `django-ninja-extra`, `django-ninja-jwt`, and `ninja-schema`.

> **Compatibility note**: Many `django-ninja-extra` patterns (`ControllerBase`, `api_controller`, `http_get`/`http_post`) are supported via compatibility shims. You may not need to change every file at once — see [Incremental Migration](#incremental-migration) at the bottom.

---

## Quick-reference: package mapping

| Remove | Replace with |
|---|---|
| `django-ninja` | `django-matt` |
| `django-ninja-extra` | `django_matt.core.controller` |
| `django-ninja-jwt` | `django_matt.auth` |
| `ninja-schema` | `django_matt.core.schema` |
| `django-ninja-crud` | `django_matt.views` |

---

## 1. Installation

```bash
# Remove old packages
uv remove django-ninja django-ninja-extra django-ninja-jwt ninja-schema django-ninja-crud

# Install django-matt
uv add django-matt
```

**`settings.py` changes:**

```python
# Before
INSTALLED_APPS = [
    ...
    "ninja_extra",
    "ninja_jwt",
]

NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# After
INSTALLED_APPS = [
    ...
    "django_matt",
]

DJANGO_MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": 3600,   # seconds
    "REFRESH_TOKEN_LIFETIME": 604800,
}

MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",  # add this
]
```

---

## 2. API setup

The top-level API object is a near-identical swap.

```python
# Before — Django Ninja
from ninja import NinjaAPI
api = NinjaAPI(title="My API", version="1.0.0")

# Before — django-ninja-extra
from ninja_extra import NinjaExtraAPI
api = NinjaExtraAPI(title="My API", version="1.0.0", auth=JWTAuth())

# After
from django_matt import DjangoMattAPI
api = DjangoMattAPI(title="My API", version="1.0.0")
```

`DjangoMattAPI` builds on both: global auth is handled via middleware instead of the `auth=` constructor argument, so you can drop it. Router registration is the same:

```python
# urls.py
from django.urls import path
from .api import api

urlpatterns = [
    path("api/", api.urls),
]
```

---

## 3. Controllers

`APIController` is the equivalent of `django-ninja-extra`'s `ControllerBase`. The class structure is nearly identical — the main differences are the decorator form and `permission_classes` vs `permissions`.

```python
# Before — django-ninja-extra
from ninja_extra import NinjaExtraAPI, api_controller, http_get, http_post, http_put, http_delete
from ninja_extra.permissions import IsAuthenticated

api = NinjaExtraAPI()

@api_controller("/users", tags=["Users"])
class UserController:
    permissions = [IsAuthenticated]

    @http_get("/")
    def list_users(self, request):
        return list(User.objects.values())

    @http_post("/")
    def create_user(self, request, data: UserCreateSchema):
        user = User.objects.create(**data.dict())
        return UserSchema.from_orm(user)

    @http_get("/{user_id}")
    def get_user(self, request, user_id: int):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return 404, {"message": "Not found"}

api.register_controllers(UserController)


# After — django-matt
from django_matt import DjangoMattAPI, APIController
from django_matt.permissions import IsAuthenticated
from django_matt.core.errors import NotFoundError

api = DjangoMattAPI()

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    permission_classes = [IsAuthenticated]    # <-- renamed

    @api.get("/")
    async def list_users(self):              # request via self.request
        return [u async for u in User.objects.all()]

    @api.post("/", response_model=UserSchema)
    async def create_user(self, data: UserCreateSchema):
        user = await User.objects.acreate(**data.model_dump())
        return UserSchema.from_orm(user)

    @api.get("/{user_id}", response_model=UserSchema)
    async def get_user(self, user_id: int):
        try:
            return await User.objects.aget(id=user_id)
        except User.DoesNotExist:
            raise NotFoundError("User not found")   # <-- raise, not return tuple
```

**What changed:**

| django-ninja-extra | django-matt |
|---|---|
| `@api_controller("/prefix", tags=[...])` | `@api.controller("/prefix", tags=[...])` |
| `class MyController:` | `class MyController(APIController):` |
| `permissions = [...]` | `permission_classes = [...]` |
| `@http_get`, `@http_post`, etc. | `@api.get`, `@api.post`, etc. |
| `request` as first arg | `self.request` (controller-style) |
| `return 404, {"message": ...}` | `raise NotFoundError(...)` |
| `api.register_controllers(Ctrl)` | handled by `@api.controller` decorator |
| sync by default | async by default (sync works too) |

---

## 4. Schemas

`ninja.Schema` is a thin wrapper around Pydantic. django-matt uses Pydantic v2 directly — `Schema` is just `pydantic.BaseModel` re-exported. The `ModelSchema` inner class changes from `Config` to `Meta`.

```python
# Before — ninja / ninja-schema
from ninja import Schema, ModelSchema

class UserSchema(Schema):
    id: int
    email: str
    username: str

class UserModelSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["id", "email", "username"]


# After — django-matt
from pydantic import BaseModel
from django_matt.core.schema import ModelSchema

class UserSchema(BaseModel):          # plain Pydantic — no wrapper needed
    id: int
    email: str
    username: str

class UserModelSchema(ModelSchema):
    class Meta:                       # Meta, not Config
        model = User
        fields = ["id", "email", "username"]   # fields, not model_fields
```

**Additional `ModelSchema` capabilities in django-matt:**

```python
# Fast list serialization — skips re-validation (significant perf win on large querysets)
users = [UserModelSchema.from_orm_fast(u) async for u in User.objects.all()]

# Exclude fields
class UserPublicSchema(ModelSchema):
    class Meta:
        model = User
        exclude = ["password", "last_login"]
```

---

## 5. Authentication

### Global / per-endpoint auth

```python
# Before — django-ninja-jwt
from ninja_jwt.authentication import JWTAuth
from ninja.security import HttpBearer

api = NinjaExtraAPI(auth=JWTAuth())   # global

class AuthBearer(HttpBearer):         # per-endpoint custom bearer
    def authenticate(self, request, token):
        ...

@api.get("/protected", auth=AuthBearer())
def protected(request):
    return {"user": request.auth.email}


# After — django-matt
# Global: handled by JWTAuthenticationMiddleware in settings.py (see Installation)

from django_matt.auth import jwt_required, jwt_optional

@api.get("/protected")
@jwt_required
async def protected(request):
    return {"user": request.user.email}   # request.user is always set

@api.get("/maybe-auth")
@jwt_optional
async def maybe_auth(request):
    if request.user.is_authenticated:
        return {"user": request.user.email}
    return {"user": "anonymous"}
```

### Built-in auth controller (replaces `NinjaJWTDefaultController`)

```python
# Before
from ninja_jwt.controller import NinjaJWTDefaultController
api.register_controllers(NinjaJWTDefaultController)
# provides: /token/pair, /token/refresh, /token/verify

# After
from django_matt.auth import AuthController
api.register_controller(AuthController)
# provides: POST /auth/login, POST /auth/register,
#           POST /auth/refresh, POST /auth/logout,
#           GET  /auth/me
# plus: token blacklisting, password reset, magic links
```

### Additional auth decorators

```python
from django_matt.auth import (
    jwt_required,          # 401 if no valid token
    jwt_optional,          # sets request.user, never 401
    admin_required,        # is_staff check
    superuser_required,    # is_superuser check
)
from django_matt.permissions.decorators import (
    requires_role,         # @requires_role("manager")
    requires_permission,   # @requires_permission("app.change_model")
)
```

---

## 6. Permissions

Permission classes map directly. The base class and interface are the same.

```python
# Before — ninja_extra.permissions
from ninja_extra.permissions import (
    IsAuthenticated,
    IsAdminUser,
    AllowAny,
)

# After — django_matt.permissions
from django_matt.permissions import (
    IsAuthenticated,
    IsAdmin,          # renamed from IsAdminUser
    AllowAny,
    IsStaff,
    IsSuperUser,
    IsOwner,          # object-level: checks obj.owner == request.user
    HasRole,          # HasRole(roles=["editor", "admin"])
    HasPermission,    # HasPermission("myapp.can_publish")
    IsAuthenticatedOrReadOnly,
    IsAdminOrReadOnly,
    # Multi-tenant aware:
    IsOrgMember,
    IsOrgAdmin,
    IsOrgOwner,
)
```

**Custom permission class** — same pattern, different import:

```python
# Before
from ninja_extra.permissions import BasePermission

class IsPremiumUser(BasePermission):
    def has_permission(self, request, controller=None):
        return request.user.is_authenticated and request.user.is_premium

# After
from django_matt.permissions.base import BasePermission

class IsPremiumUser(BasePermission):
    def has_permission(self, request, controller=None) -> bool:
        return request.user.is_authenticated and request.user.is_premium
```

---

## 7. Pagination

```python
# Before — ninja / ninja_extra
from ninja.pagination import paginate, PageNumberPagination as NinjaPagination

@api.get("/users")
@paginate(NinjaPagination)
def list_users(request):
    return User.objects.all()


# After — standalone endpoint
from django_matt.pagination import PageNumberPagination
from django_matt.di import Depends

@api.get("/users")
async def list_users(request, pagination: PageNumberPagination = Depends()):
    return await pagination.paginate(User.objects.all())


# After — inside a ViewSet (most common path)
from django_matt.views import APIViewSet, ListView
from django_matt.pagination import LimitOffsetPagination, CursorPagination

class UserViewSet(APIViewSet):
    api = api
    model = User
    list = ListView(pagination_class=LimitOffsetPagination)
```

**Available pagination classes:**

| Class | Query params | Use case |
|---|---|---|
| `PageNumberPagination` | `?page=1&page_size=20` | Simple, human-readable URLs |
| `LimitOffsetPagination` | `?limit=20&offset=40` | Offset-based, easy to reason about |
| `CursorPagination` | `?cursor=<opaque>` | Large datasets, consistent ordering |

All return a standard envelope: `{"count": N, "next": "...", "previous": "...", "results": [...]}`.

---

## 8. CRUD ViewSets

`django-ninja-crud` and django-matt share the composable-view concept. The attribute names are slightly different.

```python
# Before — django-ninja-crud
from ninja_crud import views, viewsets

class ProductViewSet(viewsets.APIViewSet):
    model = Product
    default_request_body = ProductCreateSchema
    default_response_body = ProductSchema

    list_products   = views.ListView()
    create_product  = views.CreateView()
    read_product    = views.ReadView()
    update_product  = views.UpdateView()
    delete_product  = views.DeleteView()


# After — django-matt
from django_matt.views import (
    APIViewSet,
    ListView, CreateView, ReadView, UpdateView, DeleteView,
)

class ProductViewSet(APIViewSet):
    api = api                                  # pass the api instance
    model = Product
    default_response_schema = ProductSchema    # renamed
    default_create_schema = ProductCreateSchema

    list   = ListView()
    create = CreateView()
    read   = ReadView()
    update = UpdateView()
    delete = DeleteView()
```

**Lifecycle hooks** (not in django-ninja-crud):

```python
class ProductViewSet(APIViewSet):
    api = api
    model = Product

    list   = ListView()
    create = CreateView()
    delete = DeleteView()

    async def before_create(self, data: dict) -> dict:
        data["created_by_id"] = self.request.user.id
        return data

    async def after_create(self, instance: Product) -> None:
        await notify_team(instance)

    async def before_delete(self, instance: Product) -> None:
        if instance.is_published:
            raise PermissionError("Cannot delete published products")
```

**Extras available in django-matt:**

```python
from django_matt.views import (
    BulkCreateView, BulkUpdateView, BulkDeleteView,  # bulk ops
    SoftDeleteMixin,                                  # sets deleted_at instead of DELETE
)
```

---

## 9. Router registration

```python
# Before — django-ninja-extra
api.register_controllers(UserController, ProductController)

# After — django-matt
# Option A: decorator (preferred — no separate call needed)
@api.controller("/users", tags=["Users"])
class UserController(APIController): ...

# Option B: explicit register (works the same way)
api.register_controller(UserController)
api.register_controller(ProductController)

# Routers still work if you want file-level organisation
from django_matt import APIRouter

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/")
async def list_products(request): ...

api.add_router(router)
```

---

## 10. Testing

`TestClient` from Django Ninja becomes `AsyncAPITestClient`. The async variant is preferred; the sync `APITestClient` is also available for non-async tests.

```python
# Before — django-ninja
from ninja.testing import TestClient

client = TestClient(router)
response = client.get("/users/")
assert response.status_code == 200


# After — django-matt (async, preferred)
import pytest
from django_matt.testing import AsyncAPITestClient

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_list_users(user_factory):
    user = await user_factory()
    client = AsyncAPITestClient()
    await client.force_authenticate(user)

    response = await client.get("/api/users/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


# After — django-matt (sync, when you don't need async)
from django_matt.testing import APITestClient

def test_list_users_sync(user):
    client = APITestClient()
    client.force_authenticate(user)
    response = client.get("/api/users/")
    assert response.status_code == 200
```

**Helper methods on `AsyncAPITestClient`:**

```python
client = AsyncAPITestClient()
await client.force_authenticate(user)          # sets Authorization header automatically

# Convenience wrappers that return (response, parsed_json) tuples:
response, data = await client.get_json("/api/users/")
response, data = await client.post_json("/api/users/", {"email": "a@b.com"})
response, data = await client.patch_json("/api/users/1/", {"name": "New"})
response, data = await client.delete_json("/api/users/1/")
```

---

## 11. Automated codemods

django-matt ships with tooling to help with mechanical parts of the migration.

### Type sync

After migration, keep TypeScript types in sync with your Django schemas:

```bash
python manage.py sync_types --target typescript --output frontend/types/api.ts
# Generates typed interfaces from all registered schemas + ViewSets
```

### Migration rewriters

The `migration_tools` module includes rewriters for common Django migration patterns (not Ninja-specific, but useful during large refactors):

```python
from django_matt.migration_tools.rewriters import RenameRewriter, NonNullableRewriter

# Auto-rewrite field renames across migration files
rewriter = RenameRewriter(app="myapp", old_name="old_field", new_name="new_field")
rewriter.apply()
```

### CRUD scaffolding

Generate controllers, schemas, services, admin, and tests for any model in one command:

```bash
python manage.py generate_crud myapp.Product --full
# Outputs: controller, schema, service, admin registration, pytest tests
```

### Route inspection

Verify your routes after migration:

```bash
python manage.py matt_routes            # list all registered routes
python manage.py matt_routes --format json | jq '.[] | select(.path | contains("/users"))'
```

---

## Import mapping reference

```python
# ─── Old imports ───────────────────────────────────────────────────────────
from ninja import NinjaAPI, Schema, ModelSchema, Router, Query, Path, Body
from ninja.security import HttpBearer
from ninja.pagination import paginate, PageNumberPagination
from ninja_extra import NinjaExtraAPI, api_controller, ControllerBase
from ninja_extra import http_get, http_post, http_put, http_patch, http_delete
from ninja_extra.permissions import IsAuthenticated, IsAdminUser, BasePermission
from ninja_extra.pagination import PageNumberPaginationExtra
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.authentication import JWTAuth

# ─── New imports ────────────────────────────────────────────────────────────
from django_matt import DjangoMattAPI, APIRouter, APIController
from pydantic import BaseModel as Schema                   # or: from django_matt import Schema
from django_matt.core.schema import ModelSchema
from django_matt.auth import (
    AuthController,
    jwt_required,
    jwt_optional,
    admin_required,
)
from django_matt.permissions import (
    IsAuthenticated,
    IsAdmin,           # was IsAdminUser
    AllowAny,
    IsOwner,
    HasRole,
    HasPermission,
)
from django_matt.permissions.base import BasePermission
from django_matt.pagination import (
    PageNumberPagination,
    LimitOffsetPagination,
    CursorPagination,
)
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
from django_matt.di import Depends
from django_matt.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from django_matt.testing import AsyncAPITestClient, APITestClient
```

---

## Incremental migration

You do not need to migrate everything at once. `DjangoMattAPI` and `NinjaExtraAPI` can co-exist in the same Django project, mounted at different URL prefixes:

```python
# urls.py — run both during transition
from myapp.api_ninja import api as ninja_api      # existing
from myapp.api_matt import api as matt_api         # new

urlpatterns = [
    path("api/v1/", ninja_api.urls),   # old — keep running
    path("api/v2/", matt_api.urls),    # new — migrate to
]
```

Recommended approach:

1. New endpoints go on `api/v2/` using django-matt from day one.
2. Convert existing controllers one at a time when you need to touch them.
3. Move `api/v1/` controllers over once all clients have switched.
4. Remove the Ninja packages when `api/v1/` is empty.

---

## Migration checklist

- [ ] Remove `django-ninja`, `django-ninja-extra`, `django-ninja-jwt`, `ninja-schema` from `pyproject.toml`
- [ ] Add `django-matt` via `uv add django-matt`
- [ ] Swap `INSTALLED_APPS` entries, add `DJANGO_MATT_JWT` config
- [ ] Add `JWTAuthenticationMiddleware` to `MIDDLEWARE`
- [ ] Replace `NinjaAPI` / `NinjaExtraAPI` with `DjangoMattAPI`
- [ ] Replace `@api_controller` + bare class with `@api.controller` + `APIController` subclass
- [ ] Replace `@http_get` / `@http_post` etc. with `@api.get` / `@api.post` etc.
- [ ] Rename `permissions` → `permission_classes` on controllers
- [ ] Update `ModelSchema` inner class: `Config` → `Meta`, `model_fields` → `fields`
- [ ] Replace `NinjaJWTDefaultController` with `AuthController`
- [ ] Replace `return status_code, error_dict` with `raise XxxError(...)`
- [ ] Convert sync ORM calls to async (`get` → `aget`, `save` → `asave`, `delete` → `adelete`)
- [ ] Replace `TestClient` with `AsyncAPITestClient`
- [ ] Run `python manage.py sync_types` to regenerate frontend types
- [ ] Run full test suite: `uv run pytest tests/ -x -q`

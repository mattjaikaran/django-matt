# Controllers

django-matt gives you multiple ways to build API endpoints — pick the approach that fits your use case.

## Ways to Build Controllers

| Approach | Best for | Boilerplate |
|----------|----------|-------------|
| **Function-based** | Quick endpoints, simple logic | Minimal |
| **APIController** | Grouped endpoints, middleware, DI | Low |
| **CRUDController** | Full CRUD around a Django model | None |
| **APIViewSet** | Composable, testable CRUD | Low |
| **Service layer** | Business logic separation | Medium |

### 1. Function-based (quick endpoints)

```python
from django_matt import DjangoMattAPI
from pydantic import BaseModel

api = DjangoMattAPI()

class HelloResponse(BaseModel):
    message: str

@api.get("/hello", response=HelloResponse)
async def hello(request):
    return {"message": "Hello, World!"}
```

### 2. Class-based APIController

Group endpoints under a shared prefix with unified middleware, permissions, and tags:

```python
from django_matt import DjangoMattAPI
from django_matt.core.controller import APIController
from django_matt.core.router import get, post, put, delete
from django_matt.permissions import IsAuthenticated

api = DjangoMattAPI()

class UserController(APIController):
    """User management endpoints."""

    prefix = "/users"
    tags = ["Users"]
    permission_classes = [IsAuthenticated]

    @get("/")
    async def list_users(self, request):
        users = [u async for u in User.objects.all()]
        return {"users": [u.email for u in users]}

    @get("/<int:user_id>")
    async def get_user(self, request, user_id: int):
        user = await User.objects.aget(id=user_id)
        return {"user": user.email}

    @post("/")
    async def create_user(self, request, data: UserCreate):
        user = await User.objects.acreate(**data.model_dump())
        return {"user": user.email}

    @delete("/<int:user_id>")
    async def delete_user(self, request, user_id: int):
        await User.objects.filter(id=user_id).adelete()
        return {"deleted": True}


api.register_controller(UserController)

# In urls.py:
# urlpatterns = [path("api/", include(api.urls))]
```

## CRUDController

Pre-built CRUD operations with async ORM support and automatic query optimization. Extends `APIController` with `list`, `retrieve`, `create`, `update`, `partial_update`, `delete`, `bulk_create`, `bulk_update`, `exists`, and `count` methods:

```python
from django_matt import DjangoMattAPI
from django_matt.core.controller import CRUDController
from django_matt.core.router import get, post
from django_matt.permissions import IsAuthenticated

api = DjangoMattAPI()

class ProductController(CRUDController):
    prefix = "/products"
    tags = ["Products"]
    model = Product
    schema = ProductSchema
    permission_classes = [IsAuthenticated]

    # Query optimization (auto-detected from model FK/M2M by default)
    auto_optimize = True
    select_related_fields = ["category", "brand"]
    prefetch_related_fields = ["tags", "images"]

    # Pagination settings
    default_limit = 20
    max_limit = 100

    # Use built-in CRUD methods in your route handlers
    @get("/")
    async def list_products(self, request):
        return await self.list(request)

    @post("/")
    async def create_product(self, request, data: ProductCreateSchema):
        return await self.create(request, data)


api.register_controller(ProductController)
```

### Built-in Methods

CRUDController provides these async methods that you call from your route handlers:

| Method | Signature | Description |
|--------|-----------|-------------|
| `list(request)` | `async` | List with limit/offset pagination |
| `retrieve(request, id)` | `async` | Get single resource by `lookup_field` |
| `create(request, data)` | `async` | Create new resource from Pydantic model |
| `update(request, id, data)` | `async` | Full update |
| `partial_update(request, id, data)` | `async` | Partial update (PATCH semantics) |
| `delete(request, id)` | `async` | Delete resource |
| `bulk_create(request, items)` | `async` | Create multiple instances |
| `bulk_update(request, items, fields)` | `async` | Update multiple instances |
| `exists(request, id)` | `async` | Check if resource exists |
| `count(request)` | `async` | Count resources |

The `list()` method returns `{"items": [...], "count": total, "limit": n, "offset": n}`.

### Query Optimization

CRUDController automatically optimizes queries by detecting FK and M2M fields from the model at `__init__` time:

```python
class OrderController(CRUDController):
    model = Order

    # Auto-detect relations (default behavior)
    auto_optimize = True

    # Or manually specify to override auto-detection
    select_related_fields = ["customer", "shipping_address"]
    prefetch_related_fields = ["items", "items__product"]

    # Include reverse FK relations in prefetch (disabled by default)
    include_reverse_relations = False

    # Debug optimization
    def inspect_optimization(self):
        info = self.get_query_optimization_info()
        print(f"select_related: {info['select_related_fields']}")
        print(f"prefetch_related: {info['prefetch_related_fields']}")
```

### Customizing Behavior

Override `get_queryset()` to scope the base queryset. Use `sync_to_async()` for any sync ORM calls inside async handlers:

```python
class ProductController(CRUDController):
    model = Product

    def get_queryset(self):
        """Filter to active products."""
        return self.model.objects.filter(is_active=True)

    @get("/")
    async def list_products(self, request):
        # Add extra fields before delegating to built-in list()
        result = await self.list(request)
        result["metadata"] = {"source": "db"}
        return result

    @post("/")
    async def create_product(self, request, data: ProductCreateSchema):
        # Mutate data before creation
        data_dict = data.model_dump()
        data_dict["created_by_id"] = request.user.id
        instance = await self.model.objects.acreate(**data_dict)
        return self._model_to_dict(instance)
```

### 4. APIViewSet (composable CRUD)

Pick and choose which CRUD operations you need by composing individual view classes:

```python
from django_matt import DjangoMattAPI
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

api = DjangoMattAPI()

class ProductViewSet(APIViewSet):
    api = api
    model = Product
    list = ListView()
    create = CreateView()
    read = ReadView()
    update = UpdateView()
    delete = DeleteView()
    # Auto-generates: GET /, POST /, GET /{id}, PATCH /{id}, DELETE /{id}
```

Each view component (`ListView`, `CreateView`, etc.) can be customized independently:

```python
class ProductViewSet(APIViewSet):
    api = api
    model = Product

    list = ListView(
        pagination_class=CursorPagination,
        filter_backends=[DjangoFilterBackend, SearchBackend],
    )
    read = ReadView(serializer_class=ProductDetailSchema)
```

### 5. Service Layer (separate business logic)

Keep controllers thin — delegate business logic to services:

```python
from django_matt.services import CRUDService

class ProductService(CRUDService["Product"]):
    model = Product

    def get_queryset(self):
        return super().get_queryset().select_related("category")

    async def get_featured(self) -> list[Product]:
        return [p async for p in self.get_queryset().filter(featured=True)]

# Controller: thin HTTP adapter
class ProductController(APIController):
    prefix = "/products"

    def __init__(self):
        self.service = ProductService()
        super().__init__()

    @api.get("/")
    async def list_products(self, request):
        items, total = await self.service.list()
        return {"items": items, "total": total}

    @api.post("/")
    async def create_product(self, request, data: ProductCreateSchema):
        return await self.service.create(data.model_dump(), user=request.user)
```

## CRUDController

### Prefix and Tags

Set `prefix` and `tags` as class attributes:

```python
class UserController(APIController):
    prefix = "/api/v1/users"
    tags = ["Users", "V1"]
```

### Permission Classes

`permission_classes` is a list of permission class instances or types resolved at init time. All classes in the list must pass (AND logic):

```python
from django_matt.permissions import IsAuthenticated, IsAdmin

class AdminController(APIController):
    prefix = "/admin"
    tags = ["Admin"]
    permission_classes = [IsAuthenticated, IsAdmin]
```

### Per-Method Permissions

Use `@guard()` on individual methods to override the controller-level `permission_classes`:

```python
from django_matt.permissions import IsAuthenticated
from django_matt.auth.decorators import guard, jwt_required

class UserController(APIController):
    prefix = "/users"
    permission_classes = [IsAuthenticated]

    @get("/")
    async def list_users(self, request):
        # Inherits controller permission_classes
        ...

    @get("/me")
    @jwt_required
    async def get_me(self, request):
        # JWT auth required
        ...
```

## Error Handling

`APIController.handle_exception()` automatically converts common exceptions to JSON responses:

- `APIError` subclasses → their `status_code` and `code`
- Pydantic `ValidationError` → 422
- Django `DoesNotExist` → 404
- All others → 500 via `ErrorHandler`

Override `handle_exception()` on your controller class to customize:

```python
class ProductController(APIController):
    prefix = "/products"

    def handle_exception(self, exc, request=None):
        if isinstance(exc, MyCustomError):
            from django.http import JsonResponse
            return JsonResponse({"detail": str(exc)}, status=400)
        return super().handle_exception(exc, request)
```

## Dependency Injection

Controllers support DI via the `Depends()` marker when `DJANGO_MATT["DI_AUTO_WIRE"] = True`:

```python
from django_matt.di.depends import Depends

class UserService:
    async def get_profile(self, user_id: int):
        return await User.objects.aget(id=user_id)

class UserController(APIController):
    prefix = "/users"

    @get("/me")
    async def get_me(self, request, svc: UserService = Depends(UserService)):
        return await svc.get_profile(request.user.id)
```

## Django Version Compatibility

CRUDController uses Django 4.1+ async ORM methods (`aget`, `acreate`, `asave`, `adelete`, `acount`, `aexists`, `abulk_create`, `abulk_update`). Version constants are available for conditional code:

```python
from django_matt.core import DJANGO_5_2_PLUS, DJANGO_6_0_PLUS

if DJANGO_5_2_PLUS:
    print("Using Django 5.2+ features")
```

| Feature | Django 4.1+ | Django 5.2+ | Django 6.0+ |
|---------|-------------|-------------|-------------|
| Async ORM | ✅ | ✅ | ✅ |
| Connection pooling | ❌ | ✅ | ✅ |
| Health checks | ❌ | ✅ | ✅ |

# Views System

The django-matt views system provides a powerful, composable approach to building CRUD APIs with minimal boilerplate. Inspired by Django REST Framework's ViewSets but designed for Django Ninja's async-first architecture.

## Overview

The views system consists of:

- **APIView** - Base class for all view operations
- **CRUD Views** - `ListView`, `CreateView`, `ReadView`, `UpdateView`, `DeleteView`
- **APIViewSet** - Compose views into a complete CRUD API
- **Lifecycle Hooks** - Execute custom logic before/after operations
- **Pagination** - Built-in support for multiple pagination styles
- **Filtering** - Query parameter filtering, search, and ordering
- **Permissions** - Declarative permission system

## Quick Start

```python
from django_matt import MattAPI
from django_matt.views import (
    APIViewSet,
    ListView,
    CreateView,
    ReadView,
    UpdateView,
    DeleteView,
)
from myapp.models import Product
from myapp.schemas import ProductSchema, ProductCreateSchema

api = MattAPI()


class ProductViewSet(APIViewSet):
    """Complete CRUD API for products."""

    model = Product
    prefix = "products"
    tags = ["Products"]
    default_response_schema = ProductSchema
    default_request_schema = ProductCreateSchema

    # Define CRUD operations
    list_products = ListView(
        pagination=True,
        page_size=20,
        filter_fields=["category", "is_active"],
        search_fields=["name", "description"],
    )
    create_product = CreateView()
    read_product = ReadView()
    update_product = UpdateView()
    delete_product = DeleteView()

    # Lifecycle hooks
    async def before_create(self, request, data):
        data["created_by_id"] = request.user.id
        return data

    async def after_create(self, request, instance):
        await notify_admin(f"New product: {instance.name}")
        return instance


# Register routes
urlpatterns = [
    path("api/", include(ProductViewSet.as_urls())),
]
```

This creates the following endpoints:

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/products/` | List products with pagination |
| POST | `/api/products/` | Create a new product |
| GET | `/api/products/{id}` | Get a single product |
| PUT | `/api/products/{id}` | Update a product |
| DELETE | `/api/products/{id}` | Delete a product |

## Comparison with DRF ViewSets

Django-matt views are conceptually similar to Django REST Framework ViewSets but with key differences:

### Similarities

- **Composable views**: Group related operations together
- **Permission classes**: Declarative permission system
- **Pagination**: Built-in pagination support
- **Filtering**: Query parameter filtering
- **Schemas**: Request/response validation

### Differences

| Feature | django-matt | Django REST Framework |
|---------|-------------|----------------------|
| **Async Support** | Native async/await | Sync by default |
| **Validation** | Pydantic schemas | Serializers |
| **Views** | Composable descriptors | Mixin classes |
| **Hooks** | Lifecycle decorators | Method overrides |
| **Type Hints** | Full type support | Limited |
| **Performance** | orjson, async DB | Standard JSON |

### Migration from DRF

```python
# Django REST Framework
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['category']
    search_fields = ['name']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# django-matt equivalent
class ProductViewSet(APIViewSet):
    model = Product
    default_response_schema = ProductSchema
    permission_classes = [IsAuthenticated]
    filter_fields = ["category"]
    search_fields = ["name"]

    list_products = ListView()
    create_product = CreateView()
    read_product = ReadView()
    update_product = UpdateView()
    delete_product = DeleteView()

    async def before_create(self, request, data):
        data["created_by_id"] = request.user.id
        return data
```

## Architecture

```
APIViewSet
    |
    +-- ListView         -> GET /
    +-- CreateView       -> POST /
    +-- ReadView         -> GET /{id}
    +-- UpdateView       -> PUT /{id}
    +-- PatchView        -> PATCH /{id}
    +-- DeleteView       -> DELETE /{id}
    |
    +-- Lifecycle Hooks
    |   +-- before_list / after_list
    |   +-- before_create / after_create
    |   +-- before_read / after_read
    |   +-- before_update / after_update
    |   +-- before_delete / after_delete
    |   +-- on_error
    |
    +-- Permissions
    +-- Pagination
    +-- Filtering
```

## Key Concepts

### Views as Descriptors

Each view (`ListView`, `CreateView`, etc.) is a Python descriptor that binds to the ViewSet when accessed. This enables:

- Configuration at the class level
- Access to ViewSet attributes (model, schemas, etc.)
- Automatic route generation

```python
class ProductViewSet(APIViewSet):
    model = Product

    # View descriptors - configure once, reuse everywhere
    list_products = ListView(page_size=50)
    featured = ListView(
        path="featured",
        filter_fields=["is_featured"],
    )
```

### Async-First Design

All handlers are async by default, enabling efficient I/O operations:

```python
async def handle(self, request: HttpRequest, **kwargs) -> dict:
    # Async database query
    queryset = await self.get_queryset(request).aiterator()

    # Async hook execution
    queryset = await self._run_hooks(HookType.BEFORE_LIST, request, queryset)

    return {"items": list(queryset)}
```

### Hook System

Lifecycle hooks allow you to inject custom logic without subclassing:

```python
from django_matt.views import before_create, after_create

@before_create(ProductViewSet)
async def validate_inventory(context, data):
    if data.get("quantity", 0) < 0:
        raise ValueError("Quantity cannot be negative")
    return data

@after_create(ProductViewSet)
async def sync_to_warehouse(context, instance):
    await warehouse_api.sync(instance)
    return instance
```

## Documentation Structure

- [Base APIView](api-view.md) - Foundation for all views
- [CRUD Views](crud-views.md) - List, Create, Read, Update, Delete
- [ViewSet](viewset.md) - Composing views together
- [Lifecycle Hooks](hooks.md) - Extending view behavior
- [View Decorators](decorators.md) - Conditional hooks and composition
- [Pagination](pagination.md) - Page number, limit/offset, cursor
- [Filtering](filtering.md) - Filter backends and FilterSets
- [Permissions](permissions.md) - Access control
- [Throttling](throttling.md) - Rate limiting

## Best Practices

### 1. Use ViewSets for Standard CRUD

For standard CRUD operations, use `APIViewSet`:

```python
class UserViewSet(APIViewSet):
    model = User
    default_response_schema = UserSchema

    list_users = ListView()
    create_user = CreateView()
    # ...
```

### 2. Customize with Hooks, Not Subclasses

Instead of subclassing views, use lifecycle hooks:

```python
# Prefer this
async def before_create(self, request, data):
    data["created_by_id"] = request.user.id
    return data

# Over this
class CustomCreateView(CreateView):
    async def handle(self, request, **kwargs):
        # Custom logic
        return await super().handle(request, **kwargs)
```

### 3. Keep Views Focused

Each view should handle one operation. Use multiple ListView instances for different queries:

```python
class ProductViewSet(APIViewSet):
    # Different list endpoints
    list_all = ListView()
    list_featured = ListView(path="featured", filter_fields=["is_featured"])
    list_by_category = ListView(path="category/{category_id}")
```

### 4. Use Typed Schemas

Always use Pydantic schemas for type safety and validation:

```python
from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str
    price: float
    category_id: int

class ProductViewSet(APIViewSet):
    default_request_schema = ProductCreate
```

# APIViewSet

The `APIViewSet` class is the primary way to compose views into a complete CRUD API. It provides configuration, lifecycle hooks, and automatic URL generation.

## Overview

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView

class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"
    tags = ["Products"]
    default_response_schema = ProductSchema

    list_products = ListView()
    create_product = CreateView()
    read_product = ReadView()
```

## Class Hierarchy

```
ViewSet (base class)
    |
    +-- Uses ViewSetMeta metaclass
    |   (collects view instances from class attributes)
    |
    +-- APIViewSet (adds hooks and API features)
        |
        +-- HooksMixin (lifecycle hook methods)
```

## Configuration Attributes

### Model and Schema

| Attribute | Type | Description |
|-----------|------|-------------|
| `model` | `type[Model]` | Django model this ViewSet operates on |
| `default_response_schema` | `type[BaseModel]` | Default response schema for all views |
| `default_request_schema` | `type[BaseModel]` | Default request schema for write views |

### URL and Documentation

| Attribute | Type | Description |
|-----------|------|-------------|
| `prefix` | `str` | URL prefix for all routes |
| `tags` | `list[str]` | OpenAPI tags for documentation |

### Permissions and Hooks

| Attribute | Type | Description |
|-----------|------|-------------|
| `authentication_classes` | `list` | Authentication backends |
| `permission_classes` | `list` | Permission classes |
| `enable_hooks` | `bool` | Enable/disable hooks (default: True) |

## Basic Usage

### Minimal ViewSet

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

class UserViewSet(APIViewSet):
    model = User
    default_response_schema = UserSchema

    list_users = ListView()
    create_user = CreateView()
    read_user = ReadView()
    update_user = UpdateView()
    delete_user = DeleteView()
```

### With Configuration

```python
class UserViewSet(APIViewSet):
    model = User
    prefix = "users"
    tags = ["Users", "Admin"]
    default_response_schema = UserSchema
    default_request_schema = UserCreateSchema
    permission_classes = [IsAuthenticated]

    list_users = ListView(
        pagination=True,
        page_size=25,
        filter_fields=["role", "is_active"],
        search_fields=["email", "first_name", "last_name"],
    )

    create_user = CreateView()

    read_user = ReadView(
        response_schema=UserDetailSchema,  # Override default
    )

    update_user = UpdateView(
        request_schema=UserUpdateSchema,
    )

    delete_user = DeleteView()
```

## URL Generation

### Using `as_urls()`

Generate Django URL patterns:

```python
# urls.py
from django.urls import path, include
from myapp.views import ProductViewSet, UserViewSet

urlpatterns = [
    path("api/products/", include(ProductViewSet.as_urls())),
    path("api/users/", include(UserViewSet.as_urls())),
]
```

Generated URLs:

```
/api/products/           -> list_products (GET)
/api/products/           -> create_product (POST)
/api/products/<id>       -> read_product (GET)
/api/products/<id>       -> update_product (PUT)
/api/products/<id>       -> delete_product (DELETE)
```

### Using `get_routes()`

Get route information for custom URL configuration:

```python
viewset = ProductViewSet()
routes = viewset.get_routes()

for route in routes:
    print(f"{route['methods']} {route['path']} -> {route['name']}")
    # GET  -> list_products
    # POST  -> create_product
    # GET {id} -> read_product
    # PUT {id} -> update_product
    # DELETE {id} -> delete_product
```

## Queryset Customization

### Override `get_queryset()`

Filter the base queryset for all views:

```python
class ProductViewSet(APIViewSet):
    model = Product

    def get_queryset(self, request=None):
        """Filter to user's organization."""
        qs = self.model.objects.all()

        if request and hasattr(request, "user"):
            qs = qs.filter(organization=request.user.organization)

        return qs.select_related("category").prefetch_related("tags")
```

### Per-View Queryset

Views can further filter the base queryset:

```python
class ProductViewSet(APIViewSet):
    model = Product

    # Base queryset
    def get_queryset(self, request=None):
        return self.model.objects.filter(is_deleted=False)

    # Active products only
    list_active = ListView(filter_fields=["is_active"])

    # All products including inactive (for admin)
    list_all = ListView(path="all")
```

## Lifecycle Hooks

APIViewSet includes `HooksMixin` which provides lifecycle hook methods:

### Class-Based Hooks

Define hooks as async methods on your ViewSet:

```python
class ProductViewSet(APIViewSet):
    model = Product

    list_products = ListView()
    create_product = CreateView()
    update_product = UpdateView()
    delete_product = DeleteView()

    # Hook methods
    async def before_list(self, request, queryset):
        """Filter queryset before listing."""
        return queryset.filter(is_visible=True)

    async def after_list(self, request, result):
        """Modify response after listing."""
        result["count"] = len(result["items"])
        return result

    async def before_create(self, request, data):
        """Modify data before creation."""
        data["created_by_id"] = request.user.id
        return data

    async def after_create(self, request, instance):
        """Actions after creation."""
        await send_notification(f"Product created: {instance.name}")
        return instance

    async def before_update(self, request, instance, data):
        """Validate before update."""
        if instance.is_locked:
            raise ValueError("Cannot update locked product")
        return instance, data

    async def after_update(self, request, instance):
        """Actions after update."""
        await invalidate_cache(f"product:{instance.id}")
        return instance

    async def before_delete(self, request, instance):
        """Validate before deletion."""
        if instance.has_orders:
            raise ValueError("Cannot delete product with orders")
        return instance

    async def after_delete(self, request, instance):
        """Cleanup after deletion."""
        await cleanup_files(instance.id)

    async def on_error(self, request, error):
        """Handle errors."""
        await log_error(error, request)
```

### Hook Signatures

| Hook | Signature | Returns |
|------|-----------|---------|
| `before_list` | `(request, queryset)` | Modified queryset |
| `after_list` | `(request, result)` | Modified result dict |
| `before_create` | `(request, data)` | Modified data dict |
| `after_create` | `(request, instance)` | Instance |
| `before_read` | `(request, lookup_value)` | Lookup value |
| `after_read` | `(request, instance)` | Instance |
| `before_update` | `(request, instance, data)` | Tuple (instance, data) |
| `after_update` | `(request, instance)` | Instance |
| `before_delete` | `(request, instance)` | Instance |
| `after_delete` | `(request, instance)` | None |
| `on_error` | `(request, error)` | None |

## Custom Operations

### Adding Custom Endpoints

Add custom views alongside CRUD operations:

```python
class ProductViewSet(APIViewSet):
    model = Product

    # Standard CRUD
    list_products = ListView()
    create_product = CreateView()
    read_product = ReadView()

    # Custom endpoints
    featured = ListView(
        path="featured",
        description="List featured products",
    )

    by_category = ListView(
        path="category/{category_id}",
        description="List products by category",
    )

    search = ListView(
        path="search",
        search_fields=["name", "description", "tags__name"],
        pagination=True,
    )
```

### Custom View Classes

Create and use custom view classes:

```python
from django_matt.views import APIView

class BulkUpdateView(APIView):
    path = "bulk-update"
    methods = ["POST"]

    async def handle(self, request, **kwargs):
        data = self.validate_request(request)
        updated = []

        for item in data.items:
            instance = await self.get_queryset(request).aget(id=item.id)
            for key, value in item.updates.items():
                setattr(instance, key, value)
            await instance.asave()
            updated.append(instance.id)

        return {"updated": updated}


class ProductViewSet(APIViewSet):
    model = Product

    list_products = ListView()
    bulk_update = BulkUpdateView(request_schema=BulkUpdateSchema)
```

## perform_* Methods

Override these methods for custom CRUD behavior:

### `perform_create`

```python
async def perform_create(self, data: dict, request: HttpRequest) -> Model:
    """
    Create a new model instance.

    Args:
        data: Validated data dictionary
        request: The HTTP request

    Returns:
        Created model instance
    """
    instance = self.model(**data)
    await instance.asave()
    return instance
```

Example override:

```python
class ProductViewSet(APIViewSet):
    model = Product

    async def perform_create(self, data: dict, request: HttpRequest) -> Product:
        # Generate slug
        data["slug"] = slugify(data["name"])

        # Set creator
        data["created_by"] = request.user

        # Create with related objects
        tags = data.pop("tags", [])
        instance = self.model(**data)
        await instance.asave()

        # Add many-to-many
        if tags:
            await instance.tags.aset(tags)

        return instance
```

### `perform_update`

```python
async def perform_update(
    self,
    instance: Model,
    data: dict,
    request: HttpRequest,
) -> Model:
    """
    Update a model instance.

    Args:
        instance: The model instance to update
        data: Validated data dictionary
        request: The HTTP request

    Returns:
        Updated model instance
    """
    for key, value in data.items():
        setattr(instance, key, value)
    await instance.asave()
    return instance
```

### `perform_delete`

```python
async def perform_delete(self, instance: Model, request: HttpRequest) -> None:
    """
    Delete a model instance.

    Args:
        instance: The model instance to delete
        request: The HTTP request
    """
    await instance.adelete()
```

Example soft delete:

```python
class ProductViewSet(APIViewSet):
    model = Product

    async def perform_delete(self, instance: Product, request: HttpRequest):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        await instance.asave()
```

## Complete Example

```python
from django_matt.views import (
    APIViewSet,
    ListView,
    CreateView,
    ReadView,
    UpdateView,
    DeleteView,
)
from django_matt.permissions import IsAuthenticated, IsAdmin
from django_matt.pagination import CursorPagination

from .models import Product
from .schemas import (
    ProductSchema,
    ProductDetailSchema,
    ProductCreateSchema,
    ProductUpdateSchema,
)


class ProductViewSet(APIViewSet):
    """
    Complete product management API.

    Provides CRUD operations with:
    - Pagination and filtering
    - Search across name and description
    - Lifecycle hooks for audit logging
    - Soft delete support
    """

    model = Product
    prefix = "products"
    tags = ["Products"]
    default_response_schema = ProductSchema
    permission_classes = [IsAuthenticated]

    # List with filtering and search
    list_products = ListView(
        pagination=True,
        page_size=25,
        filter_fields=["category_id", "is_active", "price__gte", "price__lte"],
        search_fields=["name", "description"],
        ordering_fields=["name", "price", "created_at"],
        ordering="-created_at",
    )

    # Create with validation
    create_product = CreateView(
        request_schema=ProductCreateSchema,
        response_schema=ProductDetailSchema,
    )

    # Read with full details
    read_product = ReadView(
        response_schema=ProductDetailSchema,
    )

    # Update
    update_product = UpdateView(
        request_schema=ProductUpdateSchema,
        response_schema=ProductDetailSchema,
    )

    # Soft delete
    delete_product = DeleteView()

    # Custom: Featured products
    featured = ListView(
        path="featured",
        description="List featured products",
        pagination_class=CursorPagination(ordering="-featured_at"),
    )

    # Custom: By category
    by_category = ListView(
        path="category/{category_id}",
        description="List products in category",
    )

    # Queryset
    def get_queryset(self, request=None):
        qs = self.model.objects.filter(is_deleted=False)
        return qs.select_related("category", "created_by")

    # Hooks
    async def before_create(self, request, data):
        data["created_by_id"] = request.user.id
        data["slug"] = slugify(data["name"])
        return data

    async def after_create(self, request, instance):
        await AuditLog.objects.acreate(
            action="create",
            model="Product",
            object_id=instance.id,
            user=request.user,
            data={"name": instance.name},
        )
        return instance

    async def after_update(self, request, instance):
        await cache.delete(f"product:{instance.id}")
        return instance

    async def perform_delete(self, instance, request):
        # Soft delete
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = request.user
        await instance.asave()

    async def on_error(self, request, error):
        await log_error(error, request=request, view="ProductViewSet")
```

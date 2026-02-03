# CRUD Views

Django-matt provides five composable view classes for standard CRUD operations. Each view handles one type of operation and can be configured independently.

## ListView

Lists resources with support for pagination, filtering, search, and ordering.

### Basic Usage

```python
from django_matt.views import ListView

class ProductViewSet(APIViewSet):
    model = Product

    list_products = ListView(
        response_schema=ProductSchema,
        pagination=True,
        page_size=20,
    )
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `pagination` | `bool` | `True` | Enable pagination |
| `pagination_class` | `BasePagination` | `None` | Custom pagination class |
| `page_size` | `int` | `20` | Default items per page |
| `max_page_size` | `int` | `100` | Maximum allowed page size |
| `ordering` | `str \| list[str]` | `None` | Default ordering field(s) |
| `ordering_fields` | `list[str]` | `None` | Allowed ordering fields |
| `filter_fields` | `list[str]` | `None` | Fields that can be filtered |
| `filter_backends` | `list[Backend]` | `None` | Filter backend instances |
| `filterset_class` | `type[FilterSet]` | `None` | FilterSet for complex filtering |
| `search_fields` | `list[str]` | `None` | Fields searchable via `?search=` |

### Response Format

```json
{
  "items": [...],
  "count": 10,
  "total": 150,
  "page": 1,
  "page_size": 20
}
```

### Full Example

```python
from django_matt.views import ListView
from django_matt.pagination import CursorPagination
from django_matt.filtering import DjangoFilterBackend, SearchBackend, OrderingBackend

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [DjangoFilterBackend(), SearchBackend(), OrderingBackend()]

    # Standard list with pagination
    list_products = ListView(
        response_schema=ProductSchema,
        pagination=True,
        page_size=25,
        max_page_size=100,
        filter_fields=["category", "is_active", "price__gte", "price__lte"],
        search_fields=["name", "description"],
        ordering_fields=["name", "price", "created_at"],
        ordering="-created_at",
    )

    # Featured products with cursor pagination
    list_featured = ListView(
        path="featured",
        response_schema=ProductSchema,
        pagination_class=CursorPagination(ordering="-created_at"),
        filter_fields=["is_featured"],
    )

    # No pagination for small datasets
    list_categories = ListView(
        path="categories",
        response_schema=CategorySchema,
        pagination=False,
    )
```

### Lifecycle Hooks

ListView supports `before_list` and `after_list` hooks:

```python
class ProductViewSet(APIViewSet):
    list_products = ListView()

    async def before_list(self, request, queryset):
        """Modify queryset before execution."""
        # Filter to user's organization
        return queryset.filter(organization=request.user.organization)

    async def after_list(self, request, result):
        """Modify response after serialization."""
        result["metadata"] = {"timestamp": datetime.now().isoformat()}
        return result
```

---

## CreateView

Creates a new resource from validated request data.

### Basic Usage

```python
from django_matt.views import CreateView

class ProductViewSet(APIViewSet):
    model = Product

    create_product = CreateView(
        request_schema=ProductCreateSchema,
        response_schema=ProductSchema,
    )
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | `str` | `""` | URL path (typically empty for POST /) |
| `request_schema` | `BaseModel` | ViewSet default | Request validation schema |
| `response_schema` | `BaseModel` | ViewSet default | Response serialization schema |

### Request Flow

1. Validate request body against `request_schema`
2. Execute `before_create` hooks (can modify data)
3. Call `perform_create()` to save the instance
4. Execute `after_create` hooks (can modify response)
5. Serialize and return the created instance

### Customizing Creation

Override `perform_create` on the ViewSet:

```python
class ProductViewSet(APIViewSet):
    model = Product

    create_product = CreateView()

    async def perform_create(self, data: dict, request: HttpRequest) -> Product:
        """Custom creation logic."""
        # Add computed fields
        data["slug"] = slugify(data["name"])
        data["created_by"] = request.user

        instance = self.model(**data)
        await instance.asave()
        return instance
```

### Lifecycle Hooks

```python
class ProductViewSet(APIViewSet):
    create_product = CreateView()

    async def before_create(self, request, data):
        """Validate and modify data before creation."""
        # Add user reference
        data["created_by_id"] = request.user.id

        # Business validation
        if data.get("price", 0) < 0:
            raise ValueError("Price cannot be negative")

        return data

    async def after_create(self, request, instance):
        """Post-creation actions."""
        # Send notification
        await notify_admin(f"New product: {instance.name}")

        # Trigger background task
        await sync_to_inventory.delay(instance.id)

        return instance
```

---

## ReadView

Retrieves a single resource by its primary key or lookup field.

### Basic Usage

```python
from django_matt.views import ReadView

class ProductViewSet(APIViewSet):
    model = Product

    read_product = ReadView(
        response_schema=ProductDetailSchema,
    )
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | `str` | `"{id}"` | URL path with lookup parameter |
| `lookup_field` | `str` | `"id"` | Model field for lookup |
| `response_schema` | `BaseModel` | ViewSet default | Response schema |

### Custom Lookup Fields

```python
class ProductViewSet(APIViewSet):
    model = Product

    # Lookup by ID (default)
    read_by_id = ReadView(path="{id}")

    # Lookup by slug
    read_by_slug = ReadView(
        path="slug/{slug}",
        lookup_field="slug",
    )

    # Lookup by SKU
    read_by_sku = ReadView(
        path="sku/{sku}",
        lookup_field="sku",
    )
```

### Lifecycle Hooks

```python
class ProductViewSet(APIViewSet):
    read_product = ReadView()

    async def before_read(self, request, lookup_value):
        """Modify lookup value if needed."""
        # Could transform slug to lowercase, etc.
        return lookup_value

    async def after_read(self, request, instance):
        """Modify instance or add related data."""
        # Track view count
        await instance.increment_views()

        return instance
```

### Aliases

`RetrieveView` is an alias for `ReadView`:

```python
from django_matt.views import RetrieveView

read_product = RetrieveView()  # Same as ReadView()
```

---

## UpdateView

Updates a resource with full replacement (PUT method).

### Basic Usage

```python
from django_matt.views import UpdateView

class ProductViewSet(APIViewSet):
    model = Product

    update_product = UpdateView(
        request_schema=ProductUpdateSchema,
        response_schema=ProductSchema,
    )
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | `str` | `"{id}"` | URL path with lookup parameter |
| `lookup_field` | `str` | `"id"` | Model field for lookup |
| `request_schema` | `BaseModel` | ViewSet default | Request validation schema |
| `response_schema` | `BaseModel` | ViewSet default | Response schema |

### Request Flow

1. Retrieve existing instance by lookup field
2. Validate request body against `request_schema`
3. Execute `before_update` hooks (receives instance and data)
4. Call `perform_update()` to save changes
5. Execute `after_update` hooks
6. Serialize and return updated instance

### Customizing Updates

```python
class ProductViewSet(APIViewSet):
    model = Product

    update_product = UpdateView()

    async def perform_update(
        self,
        instance: Product,
        data: dict,
        request: HttpRequest,
    ) -> Product:
        """Custom update logic."""
        # Track modification
        data["updated_at"] = timezone.now()
        data["updated_by"] = request.user

        for key, value in data.items():
            setattr(instance, key, value)

        await instance.asave()
        return instance
```

### Lifecycle Hooks

```python
class ProductViewSet(APIViewSet):
    update_product = UpdateView()

    async def before_update(self, request, instance, data):
        """Validate update and optionally modify data."""
        # Check ownership
        if instance.created_by != request.user:
            raise PermissionError("Can only update own products")

        # Track changes
        data["previous_price"] = instance.price

        return instance, data  # Return tuple

    async def after_update(self, request, instance):
        """Post-update actions."""
        # Invalidate cache
        await cache.delete(f"product:{instance.id}")

        # Notify subscribers
        if instance.price_changed:
            await notify_price_watchers(instance)

        return instance
```

---

## PatchView

Partially updates a resource (PATCH method). Only provided fields are updated.

### Basic Usage

```python
from django_matt.views import PatchView

class ProductViewSet(APIViewSet):
    model = Product

    patch_product = PatchView(
        request_schema=ProductPatchSchema,
        response_schema=ProductSchema,
    )
```

### Difference from UpdateView

| Aspect | UpdateView (PUT) | PatchView (PATCH) |
|--------|------------------|-------------------|
| Method | PUT | PATCH |
| Fields | All required | Only provided |
| Serialization | `exclude_unset=True` | `exclude_unset=True, exclude_none=True` |

### Schema Design for PATCH

Use optional fields for PATCH schemas:

```python
from pydantic import BaseModel

class ProductPatch(BaseModel):
    """All fields optional for partial updates."""
    name: str | None = None
    price: float | None = None
    description: str | None = None
    category_id: int | None = None
    is_active: bool | None = None
```

---

## DeleteView

Deletes a resource.

### Basic Usage

```python
from django_matt.views import DeleteView

class ProductViewSet(APIViewSet):
    model = Product

    delete_product = DeleteView()
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | `str` | `"{id}"` | URL path with lookup parameter |
| `lookup_field` | `str` | `"id"` | Model field for lookup |
| `return_deleted` | `bool` | `False` | Return deleted object data |

### Response Format

Default response:
```json
{"deleted": true}
```

With `return_deleted=True`:
```json
{
  "deleted": true,
  "data": {
    "id": 123,
    "name": "Product Name",
    ...
  }
}
```

### Soft Delete

Implement soft delete in `perform_delete`:

```python
class ProductViewSet(APIViewSet):
    model = Product

    delete_product = DeleteView()

    async def perform_delete(self, instance: Product, request: HttpRequest):
        """Soft delete instead of hard delete."""
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = request.user
        await instance.asave()

    def get_queryset(self, request):
        """Exclude soft-deleted items."""
        return self.model.objects.filter(is_deleted=False)
```

### Lifecycle Hooks

```python
class ProductViewSet(APIViewSet):
    delete_product = DeleteView()

    async def before_delete(self, request, instance):
        """Validation before deletion."""
        # Prevent deletion of active products
        if instance.has_active_orders:
            raise ValueError("Cannot delete product with active orders")

        # Archive related data
        await archive_product_images(instance)

        return instance

    async def after_delete(self, request, instance):
        """Cleanup after deletion."""
        # Clean up files
        await delete_product_files(instance.id)

        # Notify
        await notify_inventory_system(instance, "deleted")

        # Log audit
        await AuditLog.objects.acreate(
            action="delete",
            model="Product",
            object_id=instance.id,
            user=request.user,
        )
```

---

## Combining Views

Create a complete CRUD API by combining views:

```python
from django_matt.views import (
    APIViewSet,
    ListView,
    CreateView,
    ReadView,
    UpdateView,
    PatchView,
    DeleteView,
)

class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"
    tags = ["Products"]
    default_response_schema = ProductSchema

    # List and search
    list_products = ListView(
        pagination=True,
        page_size=20,
        filter_fields=["category", "is_active"],
        search_fields=["name", "description"],
        ordering="-created_at",
    )

    # Create
    create_product = CreateView(
        request_schema=ProductCreate,
    )

    # Read
    read_product = ReadView()

    # Full update
    update_product = UpdateView(
        request_schema=ProductUpdate,
    )

    # Partial update
    patch_product = PatchView(
        request_schema=ProductPatch,
    )

    # Delete with return
    delete_product = DeleteView(
        return_deleted=True,
    )

    # Custom endpoints
    featured = ListView(
        path="featured",
        filter_fields=["is_featured"],
    )

    by_category = ListView(
        path="category/{category_id}",
    )


# URL configuration
urlpatterns = [
    path("api/", include(ProductViewSet.as_urls())),
]
```

This generates:

- `GET /api/products/` - List products
- `POST /api/products/` - Create product
- `GET /api/products/{id}` - Get product
- `PUT /api/products/{id}` - Update product
- `PATCH /api/products/{id}` - Partial update
- `DELETE /api/products/{id}` - Delete product
- `GET /api/products/featured` - List featured
- `GET /api/products/category/{category_id}` - List by category

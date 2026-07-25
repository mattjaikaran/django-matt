# Views API Reference

Composable CRUD views for building REST APIs with minimal code.

## Performance Notes

### Auto Query Optimization

All views use `optimize_queryset()` internally. At view class instantiation time (not per-request), the view introspects `model._meta.get_fields()` and caches the result as a `frozenset` (`_valid_filter_fields`). This means:

- `select_related` / `prefetch_related` decisions happen once at startup
- Per-request filter field validation is an O(1) frozenset membership check
- No repeated `_meta` introspection per request

### Schema Serialization

Views serialize ORM results via `from_orm_fast()` (uses `model_construct()` — skips re-validation). For large list results this is significantly faster than full Pydantic validation.

### Rust-Accelerated List Endpoint

When Rust extensions are installed and `CAMEL_CASE_API = True`, `ListView` uses `serialize_dicts_to_json()` to serialize the entire items list in a single native pass (rename + JSON encoding combined).

## ViewSets

### APIViewSet

The main class for creating CRUD APIs using composable views.

::: django_matt.views.viewset.APIViewSet
    options:
      show_source: false
      heading_level: 4

### ViewSet

Alias for APIViewSet.

::: django_matt.views.viewset.ViewSet
    options:
      show_source: false
      heading_level: 4

---

## Base View

### APIView

Base class for all API views.

::: django_matt.views.base.APIView
    options:
      show_source: false
      heading_level: 4

---

## CRUD Views

### ListView

View for listing resources with pagination and filtering.

::: django_matt.views.list.ListView
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.views import APIViewSet, ListView

class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"
    default_response_schema = ProductSchema

    # Basic list
    list_products = ListView()

    # With custom path and filtering
    active_products = ListView(
        path="/active",
        get_queryset=lambda self, request: Product.objects.filter(is_active=True)
    )
```

---

### CreateView

View for creating new resources.

::: django_matt.views.create.CreateView
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.views import APIViewSet, CreateView

class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"
    default_request_schema = ProductCreateSchema
    default_response_schema = ProductSchema

    create_product = CreateView()

    # With custom logic
    create_draft = CreateView(
        path="/draft",
        pre_save=lambda self, request, instance: setattr(instance, 'status', 'draft')
    )
```

---

### ReadView

View for retrieving a single resource by ID.

::: django_matt.views.read.ReadView
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.views import APIViewSet, ReadView

class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"
    default_response_schema = ProductSchema

    read_product = ReadView()

    # With custom lookup field
    read_by_slug = ReadView(
        path="/by-slug/{slug}",
        lookup_field="slug"
    )
```

---

### RetrieveView

Alias for ReadView.

::: django_matt.views.read.RetrieveView
    options:
      show_source: false
      heading_level: 4

---

### UpdateView

View for fully updating a resource (PUT).

::: django_matt.views.update.UpdateView
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.views import APIViewSet, UpdateView

class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"
    default_request_schema = ProductUpdateSchema
    default_response_schema = ProductSchema

    update_product = UpdateView()
```

---

### PatchView

View for partially updating a resource (PATCH).

::: django_matt.views.update.PatchView
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.views import APIViewSet, PatchView

class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"
    default_request_schema = ProductPatchSchema
    default_response_schema = ProductSchema

    patch_product = PatchView()
```

---

### DeleteView

View for deleting a resource.

::: django_matt.views.delete.DeleteView
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.views import APIViewSet, DeleteView

class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"

    delete_product = DeleteView()

    # With soft delete
    soft_delete = DeleteView(
        pre_delete=lambda self, request, instance: setattr(instance, 'is_deleted', True),
        delete_instance=lambda self, request, instance: instance.save()
    )
```

---

## Complete Example

```python
from django_matt import DjangoMattAPI
from django_matt.views import (
    APIViewSet,
    ListView,
    CreateView,
    ReadView,
    UpdateView,
    DeleteView,
    PatchView,
)
from django_matt.permissions import IsAuthenticated, IsAdminOrReadOnly
from myapp.models import Product
from myapp.schemas import ProductSchema, ProductCreateSchema, ProductUpdateSchema

api = DjangoMattAPI()

class ProductViewSet(APIViewSet):
    """Complete CRUD API for products."""

    model = Product
    prefix = "products"
    default_response_schema = ProductSchema
    default_request_schema = ProductCreateSchema
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    # Standard CRUD operations
    list_products = ListView()
    create_product = CreateView()
    read_product = ReadView()
    update_product = UpdateView(request_schema=ProductUpdateSchema)
    patch_product = PatchView(request_schema=ProductUpdateSchema)
    delete_product = DeleteView()

    # Custom endpoints
    featured = ListView(
        path="/featured",
        get_queryset=lambda self, request: Product.objects.filter(is_featured=True)[:10]
    )
```

This creates the following endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/products/` | List all products |
| POST | `/products/` | Create a product |
| GET | `/products/{id}` | Get a product |
| PUT | `/products/{id}` | Update a product |
| PATCH | `/products/{id}` | Partially update a product |
| DELETE | `/products/{id}` | Delete a product |
| GET | `/products/featured` | List featured products |

# CRUD Views

Composable views for building REST APIs with minimal code.

## Overview

Django Matt provides declarative CRUD views inspired by django-ninja-crud:

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema

    list_products = ListView()
    create_product = CreateView(request_schema=ProductCreate)
    read_product = ReadView()
    update_product = UpdateView(request_schema=ProductUpdate)
    delete_product = DeleteView()
```

This creates:
- `GET /products/` - List products
- `POST /products/` - Create product
- `GET /products/{id}` - Get product
- `PUT /products/{id}` - Update product
- `DELETE /products/{id}` - Delete product

## ViewSet Configuration

```python
class ProductViewSet(APIViewSet):
    # Required
    api = api
    model = Product

    # Optional - schemas
    default_response_schema = ProductSchema
    default_request_schema = ProductCreateSchema

    # Optional - customization
    lookup_field = "id"  # or "pk", "slug", etc.
    permission_classes = [IsAuthenticated]

    # Define views
    list = ListView()
    create = CreateView()
    read = ReadView()
    update = UpdateView()
    delete = DeleteView()
```

## View Types

### ListView

```python
from django_matt.views import ListView

class ProductViewSet(APIViewSet):
    # Basic list
    list = ListView()

    # Custom queryset
    active = ListView(
        path="/active",
        get_queryset=lambda self, request: Product.objects.filter(is_active=True),
    )

    # With pagination
    paginated = ListView(
        pagination_class=PageNumberPagination,
    )
```

### CreateView

```python
from django_matt.views import CreateView

class ProductViewSet(APIViewSet):
    create = CreateView(
        request_schema=ProductCreate,
        response_schema=ProductSchema,
    )

    # With hooks
    create_with_user = CreateView(
        pre_save=lambda self, request, instance: setattr(instance, 'user', request.user),
        post_save=lambda self, request, instance: send_notification(instance),
    )
```

### ReadView

```python
from django_matt.views import ReadView

class ProductViewSet(APIViewSet):
    read = ReadView()

    # Custom lookup
    read_by_slug = ReadView(
        path="/by-slug/{slug}",
        lookup_field="slug",
    )
```

### UpdateView

```python
from django_matt.views import UpdateView, PatchView

class ProductViewSet(APIViewSet):
    # Full update (PUT)
    update = UpdateView(request_schema=ProductUpdate)

    # Partial update (PATCH)
    patch = PatchView(request_schema=ProductPatch)
```

### DeleteView

```python
from django_matt.views import DeleteView

class ProductViewSet(APIViewSet):
    delete = DeleteView()

    # Soft delete
    soft_delete = DeleteView(
        pre_delete=lambda self, request, instance: setattr(instance, 'is_deleted', True),
        delete_instance=lambda self, request, instance: instance.save(),
    )
```

## Hooks

All views support lifecycle hooks:

| Hook | When Called |
|------|-------------|
| `get_queryset` | Before fetching objects |
| `pre_save` | Before saving (create/update) |
| `post_save` | After saving (create/update) |
| `pre_delete` | Before deletion |
| `post_delete` | After deletion |

```python
class OrderViewSet(APIViewSet):
    create = CreateView(
        pre_save=lambda self, request, instance: (
            setattr(instance, 'user', request.user),
            setattr(instance, 'order_number', generate_order_number()),
        ),
        post_save=lambda self, request, instance: (
            send_order_confirmation(instance),
            update_inventory(instance),
        ),
    )
```

## Permissions

```python
from django_matt.permissions import IsAuthenticated, IsOwner

class ProductViewSet(APIViewSet):
    # ViewSet-level permissions
    permission_classes = [IsAuthenticated]

    # View-level permissions
    list = ListView()  # Inherits IsAuthenticated
    create = CreateView(permission_classes=[IsAuthenticated, IsAdmin])
    delete = DeleteView(permission_classes=[IsAuthenticated, IsOwner])
```

## Filtering and Pagination

```python
from django_matt.pagination import PageNumberPagination
from django_matt.filtering import DjangoFilterBackend

class ProductViewSet(APIViewSet):
    pagination_class = PageNumberPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category", "is_active", "price"]

    list = ListView()  # Supports ?category=1&is_active=true&page=2
```

## Custom Paths

```python
class ProductViewSet(APIViewSet):
    # Standard CRUD
    list = ListView(path="/")
    create = CreateView(path="/")
    read = ReadView(path="/{id}")

    # Custom endpoints
    featured = ListView(path="/featured")
    by_category = ListView(path="/category/{category_id}")
    archive = UpdateView(path="/{id}/archive")
```

## Response Customization

```python
class ProductViewSet(APIViewSet):
    list = ListView(
        response_schema=ProductListResponse,
        transform_response=lambda self, items, request: {
            "products": items,
            "meta": {"total": len(items)},
        },
    )
```

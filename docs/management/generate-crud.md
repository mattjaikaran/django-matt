# generate_crud Command

Generate CRUD controllers, schemas, services, admin, and tests for Django models.

## Synopsis

```bash
python manage.py generate_crud MODEL [OPTIONS]
```

## Description

The `generate_crud` command generates a complete CRUD (Create, Read, Update, Delete) implementation for a Django model, including:

- **Pydantic Schemas** - Request/response validation
- **API Controller** - Endpoints for all CRUD operations
- **Service Layer** - Business logic separation (default)
- **Django Admin** - Django Unfold admin configuration
- **Tests** - Pytest test cases

## Arguments

| Argument | Description |
|----------|-------------|
| `MODEL` | Model path in format `app_name.ModelName` |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir` | App directory | Output directory for generated files |
| `--prefix` | Model name plural | URL prefix for endpoints |
| `--components` | `controller schema` | Components to generate |
| `--permissions` | None | Permission classes to use |
| `--with-tests`, `-t` | `false` | Generate test file |
| `--pagination` | `true` | Include pagination in list endpoint |
| `--filtering` | `false` | Include filtering support |
| `--soft-delete` | `false` | Use soft delete instead of hard delete |
| `--no-service` | `false` | Skip service layer generation |
| `--with-admin` | `false` | Generate Django Unfold admin |
| `--full` | `false` | Generate all components |
| `--force` | `false` | Overwrite existing files |
| `--dry-run` | `false` | Preview without writing files |
| `--wizard`, `-w` | `false` | Interactive wizard mode |

## Examples

### Basic Usage

```bash
# Generate schemas and controller
python manage.py generate_crud myapp.Product
```

### Full Generation

```bash
# Generate everything: controller, schema, service, admin, tests
python manage.py generate_crud myapp.Product --full
```

### With Permissions

```bash
# Add authentication requirement
python manage.py generate_crud myapp.Product --permissions IsAuthenticated

# Multiple permissions
python manage.py generate_crud myapp.Product --permissions IsAuthenticated IsAdmin
```

### Custom Configuration

```bash
python manage.py generate_crud myapp.Product \
  --prefix api/v1/products \
  --with-tests \
  --with-admin \
  --soft-delete \
  --permissions IsAuthenticated
```

### Skip Service Layer

```bash
# For simple CRUD without business logic layer
python manage.py generate_crud myapp.Product --no-service
```

### Preview Changes

```bash
# See what would be generated without writing files
python manage.py generate_crud myapp.Product --full --dry-run
```

### Interactive Wizard

```bash
python manage.py generate_crud --wizard
```

The wizard guides you through:

1. **Select Model** - Choose from available models
2. **Select Components** - Controller, schema, service, admin, tests
3. **Configure Options** - Permissions, soft delete
4. **Review and Confirm** - Summary before generation

## Generated Files

### schemas.py

```python
from pydantic import BaseModel, Field
from datetime import datetime

class ProductSchema(BaseModel):
    """Response schema for Product."""
    id: int
    name: str
    description: str | None = None
    price: float
    created_at: datetime

    class Config:
        from_attributes = True

class ProductCreateSchema(BaseModel):
    """Schema for creating a Product."""
    name: str = Field(max_length=255)
    description: str | None = None
    price: float

class ProductUpdateSchema(BaseModel):
    """Schema for updating a Product."""
    name: str | None = None
    description: str | None = None
    price: float | None = None

class ProductListSchema(BaseModel):
    """Schema for list of Products."""
    items: list[ProductSchema]
    total: int
    page: int = 1
    page_size: int = 20
```

### controllers.py

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get, post, put, patch, delete
from django_matt.permissions import IsAuthenticated

from .schemas import (
    ProductSchema,
    ProductCreateSchema,
    ProductUpdateSchema,
    ProductListSchema,
)
from .services import ProductService


class ProductController(APIController):
    """CRUD controller for Product."""

    prefix = "/products"
    tags = ["Product"]
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.service = ProductService()

    @get("/")
    async def list_products(
        self,
        request,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> ProductListSchema:
        """List all Products."""
        items, total = await self.service.list(
            page=page,
            page_size=page_size,
            search=search,
        )
        return ProductListSchema(
            items=[ProductSchema.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    @get("/{id}")
    async def get_product(self, request, id: int) -> ProductSchema:
        """Get a single Product by ID."""
        item = await self.service.get(id)
        return ProductSchema.model_validate(item)

    @post("/")
    async def create_product(
        self,
        request,
        data: ProductCreateSchema,
    ) -> ProductSchema:
        """Create a new Product."""
        item = await self.service.create(data, user=request.user)
        return ProductSchema.model_validate(item)

    @put("/{id}")
    async def update_product(
        self,
        request,
        id: int,
        data: ProductUpdateSchema,
    ) -> ProductSchema:
        """Update a Product (full update)."""
        item = await self.service.update(id, data, partial=False)
        return ProductSchema.model_validate(item)

    @patch("/{id}")
    async def patch_product(
        self,
        request,
        id: int,
        data: ProductUpdateSchema,
    ) -> ProductSchema:
        """Partially update a Product."""
        item = await self.service.update(id, data, partial=True)
        return ProductSchema.model_validate(item)

    @delete("/{id}")
    async def delete_product(self, request, id: int) -> dict:
        """Delete a Product."""
        await self.service.delete(id)
        return {"success": True, "message": f"Product {id} deleted"}
```

### services.py

```python
"""
Service layer for Product business logic.

Keep controllers thin - they should only handle HTTP concerns
and delegate to services.
"""
from django.db import transaction
from django.http import Http404

from .models import Product
from .schemas import ProductCreateSchema, ProductUpdateSchema


class ProductService:
    """Service for Product operations."""

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        **filters,
    ) -> tuple[list[Product], int]:
        """List Products with optional filtering."""
        queryset = Product.objects.all()

        # Add search logic here
        # if search:
        #     queryset = queryset.filter(name__icontains=search)

        total = await queryset.acount()
        offset = (page - 1) * page_size
        items = [item async for item in queryset[offset:offset + page_size]]

        return items, total

    async def get(self, id: int) -> Product:
        """Get a single Product by ID."""
        try:
            return await Product.objects.aget(pk=id)
        except Product.DoesNotExist:
            raise Http404(f"Product {id} not found")

    async def create(
        self,
        data: ProductCreateSchema,
        user=None,
    ) -> Product:
        """Create a new Product."""
        create_data = data.model_dump()
        item = await Product.objects.acreate(**create_data)
        return item

    async def update(
        self,
        id: int,
        data: ProductUpdateSchema,
        partial: bool = False,
    ) -> Product:
        """Update a Product."""
        item = await self.get(id)
        update_data = data.model_dump(exclude_unset=partial)
        for key, value in update_data.items():
            if not partial or value is not None:
                setattr(item, key, value)
        await item.asave()
        return item

    async def delete(self, id: int) -> bool:
        """Delete a Product."""
        item = await self.get(id)
        await item.adelete()
        return True
```

### admin.py

```python
from django.contrib import admin
from django_matt.admin import MattModelAdmin, register_admin, export_as_csv, export_as_json

from .models import Product


@register_admin(Product)
class ProductAdmin(MattModelAdmin):
    """Admin configuration for Product."""

    list_display = ["id", "name", "price", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-id"]
    list_per_page = 25

    actions = [export_as_csv, export_as_json]
```

### tests.py

```python
import pytest
from django.test import AsyncClient

from .models import Product


@pytest.mark.django_db
class TestProductController:
    """Tests for Product CRUD endpoints."""

    base_url = "/api/products"

    @pytest.mark.asyncio
    async def test_list_products(self, async_client: AsyncClient):
        """Test listing Products."""
        response = await async_client.get(self.base_url)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_product(self, async_client: AsyncClient):
        """Test creating a Product."""
        payload = {
            "name": "Test Product",
            "price": 99.99,
        }
        response = await async_client.post(self.base_url, json=payload)
        assert response.status_code in [200, 201]

    # ... more tests
```

## Field Type Mappings

The generator automatically maps Django field types to Python/Pydantic types:

| Django Field | Python Type | Pydantic Type |
|--------------|-------------|---------------|
| CharField | `str` | `str` |
| TextField | `str` | `str` |
| IntegerField | `int` | `int` |
| FloatField | `float` | `float` |
| DecimalField | `float` | `float` |
| BooleanField | `bool` | `bool` |
| DateField | `date` | `date` |
| DateTimeField | `datetime` | `datetime` |
| UUIDField | `UUID` | `UUID` |
| EmailField | `str` | `EmailStr` |
| URLField | `str` | `HttpUrl` |
| ForeignKey | `int` | `int` |
| JSONField | `dict` | `dict` |

## Best Practices

### Use the Wizard for First-Time Users

```bash
python manage.py generate_crud --wizard
```

### Preview Before Generating

```bash
python manage.py generate_crud myapp.Product --full --dry-run
```

### Service Layer Convention

The service layer is generated by default. This promotes:

- **Separation of concerns** - Controllers handle HTTP, services handle business logic
- **Testability** - Services can be unit tested without HTTP
- **Reusability** - Services can be called from multiple controllers
- **Maintainability** - Business logic changes in one place

### Customize After Generation

Generated code is a starting point. Always:

1. Review the generated files
2. Add business-specific validation
3. Implement search and filtering logic in services
4. Add custom endpoints as needed
5. Write additional tests

### Register the Controller

After generation, register the controller in your API:

```python
# api/urls.py or api.py
from django_matt import APIRouter
from myapp.controllers import ProductController

router = APIRouter(prefix="api/")
router.register_controller(ProductController)

urlpatterns = router.get_urls()
```

## Troubleshooting

!!! warning "Model Not Found"
    Ensure the model is in `INSTALLED_APPS` and the app is properly configured:
    ```bash
    python manage.py generate_crud myapp.MyModel
    ```
    Format: `app_label.ModelName`

!!! warning "File Already Exists"
    Use `--force` to overwrite existing files:
    ```bash
    python manage.py generate_crud myapp.Product --force
    ```

!!! warning "Missing Dependencies"
    Ensure django-matt is properly installed:
    ```bash
    uv add django-matt
    ```

## See Also

- [CLI: matt crud](../cli/generate.md#matt-crud)
- [Controllers Documentation](../core/controllers.md)
- [Schemas Documentation](../core/schemas.md)
- [Permissions Documentation](../features/permissions.md)

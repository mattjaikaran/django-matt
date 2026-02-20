# Core Concepts

The core of django-matt provides the building blocks for your API: routing, controllers, schemas, and error handling.

## Overview

django-matt is built around these core concepts:

```mermaid
graph TB
    A[MattAPI] --> B[Routes]
    A --> C[Controllers]
    B --> D[Endpoints]
    C --> D
    D --> E[Schemas]
    D --> F[Responses]
    E --> G[Pydantic Validation]
    F --> H[JSON/XML/etc]
```

## Core Components

<div class="grid cards" markdown>

-   :material-routes: **API & Routing**

    ---

    Define endpoints with decorator-based routing.

    [:octicons-arrow-right-24: Routing](routing.md)

-   :material-view-dashboard: **Controllers**

    ---

    Organize endpoints into class-based controllers.

    [:octicons-arrow-right-24: Controllers](controllers.md)

-   :material-code-json: **Schemas**

    ---

    Define request/response schemas with Pydantic.

    [:octicons-arrow-right-24: Schemas](schemas.md)

-   :material-alert-circle: **Error Handling**

    ---

    Handle errors gracefully with built-in exceptions.

    [:octicons-arrow-right-24: Error Handling](errors.md)

</div>

## Quick Example

Here's a complete example using all core concepts:

```python
from django_matt import MattAPI, APIController, ModelSchema, IsAuthenticated
from django_matt.core.errors import NotFoundError
from pydantic import BaseModel
from myapp.models import Product

# Initialize API
api = MattAPI(title="Product API", version="1.0.0")


# Define schemas
class ProductSchema(ModelSchema):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'description']


class ProductCreateSchema(BaseModel):
    name: str
    price: float
    description: str = ""


# Define controller
@api.controller("/products", tags=["Products"])
class ProductController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/", response=list[ProductSchema])
    async def list_products(self):
        """List all products."""
        products = [p async for p in Product.objects.all()]
        return [ProductSchema.from_orm(p) for p in products]

    @api.get("/{product_id}", response=ProductSchema)
    async def get_product(self, product_id: int):
        """Get a single product."""
        try:
            product = await Product.objects.aget(id=product_id)
        except Product.DoesNotExist:
            raise NotFoundError(f"Product {product_id} not found")
        return ProductSchema.from_orm(product)

    @api.post("/", response=ProductSchema)
    async def create_product(self, data: ProductCreateSchema):
        """Create a new product."""
        product = await Product.objects.acreate(**data.model_dump())
        return ProductSchema.from_orm(product)
```

## Key Principles

### Async-First

django-matt is designed for async operations:

```python
# Recommended: async handlers
@api.get("/users")
async def list_users(request):
    users = [u async for u in User.objects.all()]
    return users

# Also supported: sync handlers
@api.get("/sync-users")
def list_users_sync(request):
    users = User.objects.all()
    return list(users)
```

### Type Safety

All request and response data is validated with Pydantic:

```python
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr  # Validated as email
    password: str    # Required string
    age: int | None = None  # Optional integer

@api.post("/users")
async def create_user(request, data: UserCreate):
    # data is automatically validated
    # Invalid requests return 422 with error details
    ...
```

### OpenAPI Integration

Every endpoint is automatically documented:

- Swagger UI at `/docs`
- ReDoc at `/redoc`
- OpenAPI JSON at `/openapi.json`

### Modular Design

Organize your API into logical modules:

```
api/
    __init__.py
    main.py           # MattAPI instance
    users/
        controllers.py
        schemas.py
    products/
        controllers.py
        schemas.py
```

## Next Steps

- [Routing](routing.md) - Learn about route decorators and parameters
- [Controllers](controllers.md) - Organize endpoints with controllers
- [Schemas](schemas.md) - Define validation schemas
- [Error Handling](errors.md) - Handle errors properly

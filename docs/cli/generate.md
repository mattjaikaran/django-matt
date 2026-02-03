# Code Generation Commands

Commands for scaffolding controllers, schemas, services, and complete CRUD operations.

## matt new

Generate new components for your Django Matt project.

```bash
matt new COMPONENT NAME [OPTIONS]
```

### Components

| Component | Description |
|-----------|-------------|
| `controller` | API controller with endpoints |
| `schema` | Pydantic schemas for request/response |
| `service` | Service layer for business logic |
| `test` | Test file for a component |
| `model` | Django model (basic scaffold) |

---

## matt new controller

Generate a new API controller.

```bash
matt new controller NAME [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Controller name (e.g., User, Product) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--app`, `-a` | Current directory | Target Django app |
| `--crud` | `false` | Generate full CRUD endpoints |

### Examples

```bash
# Basic controller
matt new controller User

# Controller with CRUD endpoints
matt new controller Product --crud

# In specific app
matt new controller Order --app orders
```

### Generated Output

```python
# user_controller.py
from django_matt.core.controller import APIController
from django_matt.core.router import get, post, put, delete


class UserController(APIController):
    """Controller for User operations."""

    prefix = "/users"
    tags = ["Users"]

    @get("/")
    async def list_users(self, request):
        """List all users."""
        pass

    @get("/{id}")
    async def get_user(self, request, id: int):
        """Get a specific user."""
        pass
```

---

## matt new schema

Generate Pydantic schemas for a resource.

```bash
matt new schema NAME [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Schema name (e.g., User, Product) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--app`, `-a` | Current directory | Target Django app |

### Examples

```bash
# Generate user schemas
matt new schema User

# In specific app
matt new schema Product --app products
```

### Generated Output

```python
# user_schemas.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base schema for User."""
    email: str
    name: str


class UserCreate(UserBase):
    """Schema for creating a User."""
    password: str


class UserUpdate(BaseModel):
    """Schema for updating a User."""
    email: Optional[str] = None
    name: Optional[str] = None


class User(UserBase):
    """Full User schema with all fields."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## matt new service

Generate a service layer for business logic.

```bash
matt new service NAME [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Service name (e.g., User, Product) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--app`, `-a` | Current directory | Target Django app |

### Examples

```bash
# Generate user service
matt new service User
```

### Generated Output

```python
# user_service.py
"""
Service layer for User business logic.

Keep controllers thin - they should only handle HTTP concerns
and delegate to services.
"""
from django.db import transaction
from django.http import Http404

from .models import User
from .schemas import UserCreateSchema, UserUpdateSchema


class UserService:
    """Service for User operations."""

    async def list(self, page: int = 1, page_size: int = 20, **filters):
        """List users with optional filtering."""
        queryset = User.objects.all()
        # Add your filter logic here
        total = await queryset.acount()
        offset = (page - 1) * page_size
        items = [item async for item in queryset[offset:offset + page_size]]
        return items, total

    async def get(self, id: int) -> User:
        """Get a single user by ID."""
        try:
            return await User.objects.aget(pk=id)
        except User.DoesNotExist:
            raise Http404(f"User {id} not found")

    async def create(self, data: UserCreateSchema, user=None) -> User:
        """Create a new user."""
        return await User.objects.acreate(**data.model_dump())

    async def update(self, id: int, data: UserUpdateSchema) -> User:
        """Update a user."""
        item = await self.get(id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await item.asave()
        return item

    async def delete(self, id: int) -> bool:
        """Delete a user."""
        item = await self.get(id)
        await item.adelete()
        return True
```

---

## matt new test

Generate test files for a component.

```bash
matt new test NAME [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Test name (e.g., User, Product) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--app`, `-a` | Current directory | Target Django app |
| `--type`, `-t` | `controller` | Type: `controller`, `service`, `unit` |

### Examples

```bash
# Controller tests
matt new test User

# Service tests
matt new test User --type service

# Unit tests
matt new test UserValidator --type unit
```

---

## matt crud

Generate complete CRUD operations for a Django model. This is the most powerful code generation command.

```bash
matt crud MODEL [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `MODEL` | Model path (e.g., `myapp.Product`) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | App directory | Output directory |
| `--prefix` | Model name plural | URL prefix |
| `--permissions`, `-p` | None | Permission classes to use |
| `--with-tests`, `-t` | `false` | Generate test files |
| `--with-admin` | `false` | Generate Django Unfold admin |
| `--no-service` | `false` | Skip service layer |
| `--soft-delete` | `false` | Use soft delete |
| `--full`, `-f` | `false` | Generate everything |
| `--dry-run` | `false` | Preview without writing |
| `--wizard`, `-w` | `false` | Interactive wizard mode |

### Examples

=== "Basic CRUD"

    ```bash
    matt crud myapp.Product
    ```

=== "Full Generation"

    ```bash
    matt crud myapp.Product --full
    ```

=== "With Options"

    ```bash
    matt crud myapp.Product \
      --permissions IsAuthenticated \
      --with-tests \
      --with-admin \
      --soft-delete
    ```

=== "Interactive Wizard"

    ```bash
    matt crud myapp.Product --wizard
    ```

### Generated Files

When using `--full`, the following files are generated:

```
myapp/
  schemas.py      # Pydantic schemas
  controllers.py  # API controller with CRUD endpoints
  services.py     # Business logic layer
  admin.py        # Django Unfold admin configuration
  tests.py        # Pytest test cases
```

### Interactive Wizard

The `--wizard` flag provides a guided experience:

```
CRUD Generator Wizard
Interactive setup for generating CRUD components

Step 1 of 4: Select a model
? Which model do you want to generate CRUD for?
  myapp.User
> myapp.Product
  myapp.Order

Step 2 of 4: Select components
? Which components do you want to generate?
  [x] Controller (API endpoints)
  [x] Schema (Pydantic models)
  [x] Service layer (business logic)
  [ ] Admin (Django Unfold)
  [ ] Tests

Step 3 of 4: Configure options
? What authentication should be required?
  None (public endpoints)
> IsAuthenticated (any logged-in user)
  IsAdmin (admin users only)
  Custom (specify later)

? Use soft delete? No

Step 4 of 4: Review and confirm
Summary:
  Model:       myapp.Product
  Components:  controller, schema, service
  Permissions: IsAuthenticated
  Soft Delete: No

? Generate CRUD with these settings? Yes
```

---

## matt new api

Create a new API project or app with full structure.

```bash
matt new api NAME [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Project/app name |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--template`, `-t` | `basic` | Template: `basic`, `crud`, `b2b` |
| `--auth`, `-a` | `jwt` | Auth type: `jwt`, `session`, `none` |
| `--docker` | `false` | Include Docker configuration |

### Examples

```bash
# Basic API
matt new api myproject

# B2B template with Docker
matt new api myproject --template b2b --docker

# No authentication
matt new api myproject --auth none
```

---

## matt new admin

Generate Django Unfold admin configuration for a model.

```bash
matt new admin MODEL [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `MODEL` | Model path (e.g., `myapp.Product`) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | `admin.py` | Output file |

### Examples

```bash
matt new admin myapp.Product
```

### Generated Output

```python
from django.contrib import admin
from django_matt.admin import MattModelAdmin, register_admin

from .models import Product


@register_admin(Product)
class ProductAdmin(MattModelAdmin):
    """Admin configuration for Product."""

    list_display = ["id", "name", "price", "created_at"]
    list_filter = ["created_at", "category"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-id"]
    list_per_page = 25

    actions = [export_as_csv, export_as_json]
```

---

## Best Practices

### Start with the Wizard

For new developers, the wizard provides guidance:

```bash
matt crud myapp.Model --wizard
```

### Use --dry-run First

Preview what will be generated:

```bash
matt crud myapp.Product --full --dry-run
```

### Service Layer Convention

The service layer is generated by default. Use it for:

- Complex business logic
- External API calls
- Transactions
- Event dispatching
- Notifications

Skip it only for simple CRUD:

```bash
matt crud myapp.SimpleModel --no-service
```

### Customize After Generation

Generated code is a starting point. Always:

1. Review generated files
2. Add business-specific logic
3. Customize validation rules
4. Add documentation

## Next Steps After Generation

```bash
# 1. Generate CRUD
matt crud myapp.Product --full

# 2. Review and customize generated files

# 3. Register controller in your API
# In myapp/urls.py or api.py:
from myapp.controllers import ProductController
api.register_controller(ProductController)

# 4. Run migrations (if new model)
matt db make
matt db migrate

# 5. Run tests
matt serve test
```

## See Also

- [Management: generate_crud](../management/generate-crud.md)
- [Management: startapi](../management/startapi.md)
- [Controllers Documentation](../core/controllers.md)
- [Schemas Documentation](../core/schemas.md)

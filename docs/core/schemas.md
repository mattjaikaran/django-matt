# Schemas

Django Matt uses Pydantic for request/response validation and serialization.

## ModelSchema

Automatically generate schemas from Django models. Use `class Config` (not `class Meta`) to configure model introspection:

```python
from django_matt.core.schema import ModelSchema
from myapp.models import User

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "email", "first_name", "last_name", "is_active"]

# Include all fields
class UserFullSchema(ModelSchema):
    class Config:
        model = User
        include = "__all__"

# Exclude specific fields
class UserPublicSchema(ModelSchema):
    class Config:
        model = User
        exclude = {"password", "is_superuser", "is_staff"}
```

### Config Options

| Option | Type | Description |
|--------|------|-------------|
| `model` | Django Model class | Required. The Django model to generate fields from. |
| `include` | `list[str]` or `"__all__"` | Fields to include. `None` (default) includes all. |
| `exclude` | `set[str]` | Fields to exclude. |
| `optional` | `set[str]` or `"__all__"` | Fields to make `Optional`. |
| `depth` | `int` | Declared but not yet functional for nested relations. FK fields always resolve to `int` (PK). |
| `model_fk_use_pks` | `bool` | When `True`, uses `author_id` column name instead of `author`. |

### Many-to-Many Fields

M2M fields are automatically included when listed in `include` (or when using `"__all__"`).
They are serialized as `Optional[list[int]]` (list of related PKs) and default to an empty list.

## Schema (Legacy Alias)

`Schema` is an alias for `ModelSchema` kept for backwards compatibility. Use `ModelSchema` in new code:

```python
from django_matt.core.schema import Schema  # same class as ModelSchema
```

For plain request/response schemas with no model binding, use Pydantic's `BaseModel` directly:

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""

class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
```

## Dynamic Schema Generation

### create_schema_from_model

Generate schemas programmatically. Use `include` (not `fields`):

```python
from django_matt.core.schema import create_schema_from_model
from myapp.models import Product

# Create a schema at runtime
ProductSchema = create_schema_from_model(
    Product,
    name="ProductSchema",
    include=["id", "name", "price", "description"],
)

# With optional and excluded fields
ProductDetailSchema = create_schema_from_model(
    Product,
    name="ProductDetailSchema",
    include=None,               # include all
    exclude=["internal_notes"],
    optional=["description"],
)
```

### create_model_from_schema

Create Django model classes from Pydantic schemas (primarily for testing/prototyping):

```python
from django_matt.core.schema import create_model_from_schema
from pydantic import BaseModel

class ProductData(BaseModel):
    name: str
    price: float
    description: str = ""

# Creates a Django model class (not saved to DB)
ProductModel = create_model_from_schema(ProductData, "Product")
```

## Validation

### Field Validation

Use standard Pydantic `field_validator`:

```python
from pydantic import BaseModel, Field, field_validator

class UserCreate(BaseModel):
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    password: str = Field(..., min_length=8)
    age: int = Field(..., ge=18, le=120)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower()
```

### Model-Level Validation

Use Pydantic's `model_validator` for cross-field validation:

```python
from pydantic import BaseModel, model_validator
from datetime import date

class DateRangeSchema(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
```

### Using django_matt's model_validator (for ModelSchema)

`django_matt.core.schema.model_validator` is a field-level decorator for `ModelSchema` subclasses that wraps Pydantic's `field_validator`:

```python
from django_matt.core.schema import ModelSchema, model_validator

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["email", "username"]

    @model_validator("email")
    def validate_email(cls, v):
        if not v.endswith("@company.com"):
            raise ValueError("Must be a company email")
        return v

    @model_validator("username", mode="before")
    def normalize_username(cls, v):
        return v.lower().strip()
```

## Nested Schemas

```python
class AddressSchema(Schema):
    street: str
    city: str
    country: str
    postal_code: str

class UserWithAddress(Schema):
    email: str
    name: str
    address: AddressSchema
    shipping_addresses: list[AddressSchema] = []
```

## Response Schemas

### Single Response

```python
from django_matt import Schema

class UserResponse(Schema):
    id: int
    email: str
    name: str

    @classmethod
    def from_user(cls, user):
        return cls(id=user.id, email=user.email, name=user.get_full_name())
```

### List Response

```python
class UserListResponse(Schema):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
```

### Paginated Response

```python
from typing import Generic, TypeVar
from django_matt import Schema

T = TypeVar("T")

class PaginatedResponse(Schema, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool

# Usage
class UserListResponse(PaginatedResponse[UserResponse]):
    pass
```

## Schema Usage in Controllers

Request body schemas are injected automatically. Response schemas can be returned directly as Pydantic model instances — the router calls `model_dump()` for serialization:

```python
from pydantic import BaseModel
from django_matt.core.controller import APIController
from django_matt.core.router import post

class CreateUserRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str

class UserController(APIController):
    prefix = "/users"

    @post("/")
    async def create_user(self, request, data: CreateUserRequest) -> UserResponse:
        user = await User.objects.acreate(
            email=data.email,
            password=make_password(data.password),
        )
        return UserResponse(id=user.id, email=user.email)
```

## Optional Fields

```python
from pydantic import BaseModel

class UserUpdate(BaseModel):
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    def get_update_data(self) -> dict:
        """Return only fields that were explicitly provided."""
        return self.model_dump(exclude_none=True)
```

## Computed Fields

```python
from pydantic import BaseModel, computed_field

class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

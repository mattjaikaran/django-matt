# Schemas

Django Matt uses Pydantic for request/response validation and serialization.

## ModelSchema

Automatically generate schemas from Django models:

```python
from django_matt import ModelSchema
from myapp.models import User

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "email", "first_name", "last_name", "is_active"]

# Or include all fields
class UserFullSchema(ModelSchema):
    class Config:
        model = User
        include = "__all__"

# Exclude specific fields
class UserPublicSchema(ModelSchema):
    class Config:
        model = User
        exclude = ["password", "is_superuser", "is_staff"]
```

### Config Options

| Option | Type | Description |
|--------|------|-------------|
| `model` | Django Model class | Required. The Django model to generate fields from. |
| `include` | list or `"__all__"` | Fields to include. If `None`, all fields are included. |
| `exclude` | set/list | Fields to exclude. |
| `optional` | set/list or `"__all__"` | Fields to make optional. |
| `depth` | int | Declared but **not yet functional** for nested relations. ForeignKey fields always resolve to their ID (int) regardless of depth. |

### Many-to-Many Fields

M2M fields are automatically included when listed in `include` (or when using `"__all__"`).
They are serialized as `list[int]` (list of related object PKs) and default to an empty list.

## Schema

Base class for custom schemas:

```python
from django_matt import Schema

class UserCreate(Schema):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""

class UserUpdate(Schema):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
```

## Dynamic Schema Generation

### create_schema_from_model

Generate schemas dynamically:

```python
from django_matt import create_schema_from_model
from myapp.models import Product

# Create a schema at runtime
ProductSchema = create_schema_from_model(
    Product,
    name="ProductSchema",
    fields=["id", "name", "price", "description"],
)

# With custom field configuration
ProductDetailSchema = create_schema_from_model(
    Product,
    name="ProductDetailSchema",
    fields="__all__",
    exclude=["internal_notes"],
)
```

### create_model_from_schema

Create Django models from schemas (for testing/prototyping):

```python
from django_matt import create_model_from_schema, Schema

class ProductData(Schema):
    name: str
    price: float
    description: str = ""

# Creates a Django model
ProductModel = create_model_from_schema(ProductData, "Product")
```

## Validation

### Field Validation

```python
from pydantic import Field, field_validator
from django_matt import Schema

class UserCreate(Schema):
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    password: str = Field(..., min_length=8)
    age: int = Field(..., ge=18, le=120)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower()
```

### Model Validation

```python
from pydantic import model_validator
from django_matt import Schema

class DateRangeSchema(Schema):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
```

### Using model_validator decorator

```python
from django_matt import Schema, model_validator

class OrderCreate(Schema):
    items: list[OrderItem]
    discount_code: str | None = None

@model_validator(OrderCreate)
def validate_order(values):
    if not values.get("items"):
        raise ValueError("Order must have at least one item")
    return values
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

## Schema Usage in Views

```python
from django_matt import api, Schema

class CreateUserRequest(Schema):
    email: str
    password: str

class UserResponse(Schema):
    id: int
    email: str

@api.post("/users", response=UserResponse)
async def create_user(request, data: CreateUserRequest) -> UserResponse:
    user = await User.objects.acreate(
        email=data.email,
        password=make_password(data.password),
    )
    return UserResponse(id=user.id, email=user.email)
```

## Optional Fields

```python
from typing import Optional
from django_matt import Schema

class UserUpdate(Schema):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    def get_update_data(self) -> dict:
        """Return only fields that were provided."""
        return {k: v for k, v in self.model_dump().items() if v is not None}
```

## Computed Fields

```python
from pydantic import computed_field
from django_matt import Schema

class UserResponse(Schema):
    id: int
    first_name: str
    last_name: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

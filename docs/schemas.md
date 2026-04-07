# Schemas

django-matt uses Pydantic v2 schemas for request validation, response serialization, and OpenAPI generation. The `ModelSchema` base class auto-generates Pydantic fields from Django model introspection.

## Base Classes

### ModelSchema

The primary schema class. Define a `Config` inner class pointing at a Django model, and fields are generated automatically.

```python
from django_matt.core.schema import ModelSchema

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "username", "email", "created_at"]

class UserCreateSchema(ModelSchema):
    class Config:
        model = User
        include = ["username", "email", "password"]
```

### Schema (legacy alias)

`Schema` is an alias for `ModelSchema` kept for backwards compatibility. Use `ModelSchema` in new code.

```python
from django_matt.core.schema import Schema  # same as ModelSchema
```

## Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | Django Model class | required | The Django model to introspect |
| `include` | `list[str]` or `"__all__"` | `None` (all) | Fields to include |
| `exclude` | `set[str]` | `set()` | Fields to exclude |
| `optional` | `set[str]` or `"__all__"` | `set()` | Fields to make Optional |
| `depth` | `int` | `0` | Depth for nested relation serialization |
| `model_fk_use_pks` | `bool` | `False` | Use `_id` column names for FK fields |

```python
class ProductSchema(ModelSchema):
    class Config:
        model = Product
        include = "__all__"
        exclude = {"internal_notes"}
        optional = {"description", "image_url"}
        depth = 0
        model_fk_use_pks = True  # author_id instead of author
```

## Field Mapping

Django model fields are mapped to Python types automatically:

| Django Field | Python Type |
|-------------|-------------|
| `AutoField`, `BigAutoField` | `int` |
| `CharField`, `TextField`, `SlugField`, `EmailField`, `URLField` | `str` |
| `IntegerField`, `BigIntegerField`, `SmallIntegerField` | `int` |
| `FloatField` | `float` |
| `DecimalField` | `Decimal` |
| `BooleanField` | `bool` |
| `DateField` | `datetime.date` |
| `DateTimeField` | `datetime.datetime` |
| `TimeField` | `datetime.time` |
| `UUIDField` | `uuid.UUID` |
| `JSONField` | `Any` |
| `BinaryField` | `bytes` |
| `FileField`, `ImageField` | `str` |
| `ForeignKey`, `OneToOneField` | `int` (PK) |
| `ManyToManyField` | `Optional[list[int]]` |

### Choices become Literal types

Fields with `choices` defined produce `Literal[...]` types, which appear as enums in OpenAPI:

```python
class Article(models.Model):
    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published")]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

# ArticleSchema will type `status` as Literal["draft", "published"]
```

### Custom field type registration

Register mappings for third-party or custom Django fields:

```python
from django_matt.core.schema import register_field_type, unregister_field_type

register_field_type(
    MoneyField,
    Decimal,
    openapi_schema={"type": "string", "format": "decimal"},
)

# Clean up (useful in tests)
unregister_field_type(MoneyField)
```

## model_config

`ModelSchema` ships with these Pydantic model_config defaults:

```python
model_config = {
    "from_attributes": True,      # enables .model_validate(orm_instance)
    "arbitrary_types_allowed": True,
}
```

Override per-schema by setting `model_config` as a dict on the class:

```python
class StrictUserSchema(ModelSchema):
    model_config = {"from_attributes": True, "strict": True}

    class Config:
        model = User
        include = ["id", "email"]
```

### camelCase API responses

Enable globally via settings or per-schema:

```python
# settings.py — all schemas use camelCase aliases
DJANGO_MATT = {"CAMEL_CASE_API": True}

# Per-schema override
class MySchema(ModelSchema):
    class Config:
        model = MyModel
        camel_case = False  # disable for this schema even if global is True
```

When enabled, `model_dump_response()` serializes using camelCase aliases (`createdAt` instead of `created_at`).

## from_orm and from_orm_fast

### from_orm — full validation

Runs the complete Pydantic validation pipeline. Use for single-object responses where correctness matters:

```python
user = await User.objects.aget(pk=1)
schema = UserSchema.from_orm(user)
```

### from_orm_fast — skip re-validation

Uses `model_construct()` internally. 3-5x faster than `from_orm()`. Use for list serialization where data comes from the database:

```python
schema = UserSchema.from_orm_fast(user)  # no Pydantic re-validation
```

### from_queryset / afrom_queryset

Serialize entire querysets using the fast path:

```python
users = UserSchema.from_queryset(User.objects.all())           # sync
users = await UserSchema.afrom_queryset(User.objects.all())    # async
```

## Applying Schema Data to Models

### apply_to_model

Update an existing model instance from schema data:

```python
update_data = UserUpdateSchema(email="new@example.com")
update_data.apply_to_model(user_instance, exclude_unset=True)
await user_instance.asave()
```

Parameters:
- `exclude_unset=True` — only apply fields the client explicitly sent
- `exclude_none=True` — skip None values
- `exclude={"field"}` — skip specific fields

### create_model_instance

Create a new (unsaved) Django model instance:

```python
data = UserCreateSchema(username="matt", email="matt@example.com")
user = data.create_model_instance(organization_id=org.id)
await user.asave()
```

## Custom Validators

Use `@model_validator` to add field-level validation:

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

## Dynamic Schema Creation

For programmatic use cases (code generation, admin), create schemas at runtime:

```python
from django_matt.core.schema import create_schema_from_model

ProductSchema = create_schema_from_model(
    Product,
    name="ProductSchema",
    include=["id", "name", "price"],
    optional=["description"],
)
```

## Request vs Response Schemas

A common pattern is separate schemas for input and output:

```python
class UserCreateSchema(ModelSchema):
    """Request schema — what the client sends."""
    class Config:
        model = User
        include = ["username", "email", "password"]

class UserUpdateSchema(ModelSchema):
    """Partial update — all fields optional."""
    class Config:
        model = User
        include = ["username", "email"]
        optional = "__all__"

class UserSchema(ModelSchema):
    """Response schema — what the API returns."""
    class Config:
        model = User
        include = ["id", "username", "email", "created_at"]
        # password is never exposed
```

## Nested Schemas

Override a field's annotation to use a nested schema:

```python
class AuthorSchema(ModelSchema):
    class Config:
        model = Author
        include = ["id", "name"]

class ArticleSchema(ModelSchema):
    author: AuthorSchema | None = None  # override auto-generated `int`

    class Config:
        model = Article
        include = ["id", "title", "author"]
```

## model_dump_response

When camelCase is enabled, always use `model_dump_response()` instead of `model_dump()` for API output:

```python
schema = UserSchema.from_orm(user)

# Respects CAMEL_CASE_API setting
data = schema.model_dump_response()
# {"id": 1, "userName": "matt", "createdAt": "2025-01-01T00:00:00"}
```

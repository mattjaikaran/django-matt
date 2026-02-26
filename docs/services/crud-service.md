# CRUDService API Reference

`CRUDService` provides full async CRUD for a single Django model. It inherits all read helpers from `BaseService` and adds write operations, bulk operations, and pagination.

## Import

```python
from django_matt.services import CRUDService
```

## Defining a Service

```python
from django_matt.services import CRUDService
from .models import Product

class ProductService(CRUDService["Product"]):
    model = Product  # required

    # Optional: override the base queryset
    def get_queryset(self):
        return super().get_queryset().select_related("category", "brand")
```

Instantiate once per controller in `__init__`:

```python
class ProductController(APIController):
    def __init__(self):
        self.service = ProductService()
        super().__init__()
```

---

## BaseService Methods

`CRUDService` inherits these read-only helpers from `BaseService`.

### get_queryset()

```python
def get_queryset(self) -> QuerySet[ModelT]
```

Returns `model.objects.all()` by default. Override to add `select_related`, filters, ordering, or tenant scoping. Every service method uses this as its base queryset.

```python
def get_queryset(self):
    return (
        super()
        .get_queryset()
        .select_related("user", "category")
        .filter(deleted_at__isnull=True)
        .order_by("-created_at")
    )
```

### get_active_queryset()

```python
def get_active_queryset(self) -> QuerySet[ModelT]
```

Calls `get_queryset()` and appends `.filter(is_active=True)` when the model has an `is_active` field. Falls back to the full queryset otherwise.

### get()

```python
async def get(self, pk: Any) -> ModelT
```

Fetch by primary key. Raises `NotFoundError` if the record does not exist.

```python
product = await service.get(42)
# NotFoundError: Product 42 not found
```

### get_or_none()

```python
async def get_or_none(self, pk: Any) -> ModelT | None
```

Same as `get()` but returns `None` instead of raising.

```python
product = await service.get_or_none(42)
if product is None:
    ...
```

### get_by()

```python
async def get_by(self, **lookup) -> ModelT
```

Fetch by arbitrary field lookup. Raises `NotFoundError` if missing.

```python
user = await service.get_by(email="alice@example.com")
token = await service.get_by(slug="my-article", published=True)
```

### exists()

```python
async def exists(self, **lookup) -> bool
```

Returns `True` if at least one record matches. Does not raise.

```python
taken = await service.exists(email="alice@example.com")
```

### count()

```python
async def count(self, **filters) -> int
```

Count records matching the given filters.

```python
active_count = await service.count(is_active=True)
pending = await service.count(status="pending", user=user)
```

---

## CRUDService Methods

### list()

```python
async def list(
    self,
    *,
    page: int = 1,
    page_size: int = 20,
    ordering: str | list[str] | None = None,
    **filters: Any,
) -> tuple[list[ModelT], int]
```

Paginated list with optional filtering and ordering. Returns `(items, total_count)`.

- `None` values in `**filters` are ignored, so you can pass query parameters directly without stripping `None`s in the caller.
- `ordering` accepts a field name string or a list of field name strings. Prefix with `-` for descending.

```python
# Basic pagination
items, total = await service.list(page=2, page_size=10)

# With filters (None values skipped automatically)
items, total = await service.list(status="active", user_id=request.user.id)

# With ordering
items, total = await service.list(ordering="-created_at")
items, total = await service.list(ordering=["-priority", "title"])

# Build a standard envelope
return {"items": items, "total": total, "page": 1, "page_size": 20}
```

### all()

```python
async def all(self, **filters: Any) -> list[ModelT]
```

Returns all matching records with no pagination. Use for small datasets or when you need the full set (e.g. dropdown options, exports).

```python
categories = await service.all()
featured = await service.all(featured=True)
```

### create()

```python
async def create(self, data: dict[str, Any], user=None) -> ModelT
```

Creates a record inside an atomic transaction. Calls `full_clean()` before saving.

- When `user` is provided and the model has a `created_by` field, it is populated automatically.
- Raises `ValidationError` (wrapping the underlying exception) if the database or model validation fails.

```python
product = await service.create(
    {"name": "Widget", "price": Decimal("9.99"), "sku": "WIDG-001"},
    user=request.user,
)

# From a Pydantic schema
product = await service.create(data.model_dump(), user=request.user)
```

### get_or_create()

```python
async def get_or_create(
    self,
    defaults: dict[str, Any] | None = None,
    user=None,
    **lookup: Any,
) -> tuple[ModelT, bool]
```

Fetches a record by `lookup` fields. Creates it with `{**lookup, **defaults}` if it does not exist. Returns `(instance, created)`.

```python
tag, created = await service.get_or_create(defaults={"color": "blue"}, slug="python")

category, _ = await service.get_or_create(name="Uncategorized")
```

### update()

```python
async def update(
    self,
    pk: Any,
    data: dict[str, Any],
    user=None,
    *,
    partial: bool = False,
) -> ModelT
```

Updates a record by primary key inside an atomic transaction.

- Raises `NotFoundError` if `pk` does not exist.
- When `user` is provided and the model has an `updated_by` field, it is set automatically.
- With `partial=True`, keys with `None` values are skipped (PATCH semantics).
- Raises `ValidationError` on database or model-level failures.

```python
# Full update (PUT)
updated = await service.update(pk, {"title": "New Title", "body": "..."}, user=request.user)

# Partial update (PATCH) — None values in data are ignored
patched = await service.update(
    pk,
    payload.model_dump(),   # may contain None for unset fields
    user=request.user,
    partial=True,
)
```

### update_fields()

```python
async def update_fields(self, pk: Any, user=None, **fields: Any) -> ModelT
```

Convenience wrapper around `update()`. Specify fields as keyword arguments instead of building a dict.

```python
await service.update_fields(pk, completed=True, user=request.user)
await service.update_fields(pk, status="published", published_at=now(), user=request.user)
```

### delete()

```python
async def delete(self, pk: Any, user=None, *, hard: bool = False) -> bool
```

Deletes a record. Returns `True` on success, raises `NotFoundError` if the record does not exist.

**Soft delete** (default): when the model has both `is_active` and `soft_delete()`, calls `soft_delete(user=user)` instead of removing the row. The record remains in the database but is excluded by `get_active_queryset()`.

**Hard delete**: pass `hard=True` to permanently delete regardless of whether soft delete is supported.

```python
# Soft delete (if model supports it)
await service.delete(pk, user=request.user)

# Always permanent
await service.delete(pk, hard=True)
```

---

## Bulk Operations

### bulk_create()

```python
async def bulk_create(
    self,
    items: list[dict[str, Any]],
    user=None,
    *,
    batch_size: int = 500,
    ignore_conflicts: bool = False,
) -> list[ModelT]
```

Creates many records in a single `INSERT`. Skips `full_clean()` — validate data before calling. Automatically sets `created_by` when the model supports it.

```python
created = await service.bulk_create([
    {"title": "Task A", "priority": 1},
    {"title": "Task B", "priority": 2},
    {"title": "Task C", "priority": 3},
], user=request.user)

# Import with conflict handling
imported = await service.bulk_create(rows, ignore_conflicts=True)
```

### bulk_update()

```python
async def bulk_update(
    self,
    instances: list[ModelT],
    fields: list[str],
    user=None,
    *,
    batch_size: int = 500,
) -> int
```

Updates many existing model instances in a single `UPDATE`. You must provide the list of field names to update. Returns the number of rows updated.

If `user` is provided and the model has an `updated_by` field, it is appended to `fields` automatically.

```python
# Mark a batch of todos complete
for todo in todos:
    todo.completed = True

count = await service.bulk_update(todos, fields=["completed"], user=request.user)
# count == len(todos)
```

### bulk_delete()

```python
async def bulk_delete(
    self,
    pks: list[Any],
    user=None,
    *,
    hard: bool = False,
) -> int
```

Deletes many records by primary key list in a single query. Soft-deletes by default when the model has `is_active`. Returns the number of affected rows.

```python
count = await service.bulk_delete([1, 2, 3], user=request.user)

# Hard delete
count = await service.bulk_delete(old_ids, hard=True)
```

---

## Error Classes

All service exceptions are importable from `django_matt.services`.

```python
from django_matt.services import ServiceError, NotFoundError, ValidationError, ConflictError
```

| Exception | `code` | When raised |
|-----------|--------|-------------|
| `ServiceError` | `"service_error"` | Base class; raise subclasses |
| `NotFoundError` | `"not_found"` | `get()`, `get_by()`, `update()`, `delete()` when record missing |
| `ValidationError` | `"validation_error"` | `create()`, `update()` on DB/model failures; has optional `.field` |
| `ConflictError` | `"conflict"` | Business-rule violations (duplicate slug, state machine conflicts) |

### ValidationError.field

When you raise `ValidationError` manually and can associate it with a specific field:

```python
from django_matt.services import ValidationError

raise ValidationError("Email is already in use.", field="email")
```

---

## Complete Example

```python
# products/services.py
from decimal import Decimal
from django_matt.services import CRUDService, ValidationError, ConflictError
from .models import Product

class ProductService(CRUDService["Product"]):
    model = Product

    def get_queryset(self):
        return super().get_queryset().select_related("category").prefetch_related("images")

    async def publish(self, pk: int, user) -> Product:
        product = await self.get(pk)
        if product.status == "published":
            raise ConflictError(f"Product {pk} is already published")
        return await self.update(pk, {"status": "published"}, user=user)

    async def apply_discount(self, pk: int, pct: Decimal, user) -> Product:
        if not (Decimal("0") < pct <= Decimal("100")):
            raise ValidationError("Discount must be between 0 and 100", field="discount_pct")
        product = await self.get(pk)
        new_price = product.price * (1 - pct / 100)
        return await self.update_fields(pk, price=new_price, user=user)


# products/controllers.py
from django_matt.core import APIController
from django_matt.permissions import IsAuthenticated
from django_matt.services import NotFoundError, ValidationError, ConflictError
from .services import ProductService
from .schemas import ProductCreateSchema, ProductUpdateSchema

@api.controller("/products", tags=["Products"])
class ProductController(APIController):
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.service = ProductService()
        super().__init__()

    @api.get("/")
    async def list_products(self, request, page: int = 1, page_size: int = 20):
        items, total = await self.service.list(page=page, page_size=page_size)
        return {"items": items, "total": total}

    @api.post("/")
    async def create_product(self, request, data: ProductCreateSchema):
        return await self.service.create(data.model_dump(), user=request.user)

    @api.get("/{id}")
    async def get_product(self, request, id: int):
        return await self.service.get(id)

    @api.patch("/{id}")
    async def update_product(self, request, id: int, data: ProductUpdateSchema):
        return await self.service.update(id, data.model_dump(), user=request.user, partial=True)

    @api.delete("/{id}")
    async def delete_product(self, request, id: int):
        await self.service.delete(id, user=request.user)
        return {"deleted": True}

    @api.post("/{id}/publish")
    async def publish_product(self, request, id: int):
        return await self.service.publish(id, user=request.user)
```

## See Also

- [Service Layer Overview](./index.md)
- [Third-Party Services](./third-party.md)
- [Service Patterns](./patterns.md)

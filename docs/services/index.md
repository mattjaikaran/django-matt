# Service Layer

The service layer sits between controllers and models. Controllers handle HTTP concerns (parsing requests, returning responses, checking permissions). Services own the business logic.

## Architecture Philosophy

django-matt enforces a **thin controller, fat service** architecture. Every layer has exactly one job:

```
Request
  │
  ▼
Controller          ← HTTP only: parse input, check permissions, format output
  │
  ▼
Service             ← Business logic: validation, DB ops, side effects, events
  │
  ▼
Model / DB          ← Data persistence, constraints, migrations
  │
  ▼
Response
```

### What belongs in the controller

- Parse path/query/body parameters (Pydantic schemas do this automatically)
- Check permissions (`permission_classes`, `@jwt_required`)
- Call one or more service methods
- Format the return value (pagination envelope, status code selection)
- Map service exceptions to HTTP errors

### What belongs in the service

- All ORM queries (reads and writes)
- Business rule validation (`raise ValidationError(...)`)
- State machine transitions (`order.cancel()`, `task.change_status()`)
- Audit field population (`created_by`, `updated_by`)
- Cross-model orchestration (checkout flow touching orders + inventory + payments)
- Side effects (emit events, send notifications, update caches)

### When you can skip the service layer

- Truly trivial CRUD with no business logic — use `CRUDController` (declarative pattern)
- One-off admin scripts or management commands that are not called from multiple places
- Read-only endpoints that return a single queryset with no transformation

### How services integrate with other django-matt modules

| Module | Integration |
|--------|-------------|
| [Events](../events/) | Service methods call `await bus.emit(event)` after mutations |
| [CQRS](../cqrs/) | Service methods become the body of `CommandHandler.execute()` |
| [Interceptors](../interceptors/) | Cross-cutting concerns (logging, timing) wrap controller dispatch, not service calls |
| [Transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/) | `create()` and `update()` already run inside `transaction.atomic()`; compose with `async with transaction.atomic()` for multi-service operations |

## Why Services?

A controller without a service quickly accumulates ORM calls, conditional logic, and audit boilerplate that has nothing to do with HTTP. The service layer prevents that:

| Without services | With services |
|-----------------|---------------|
| ORM queries in every endpoint | One service method per operation |
| Audit fields set manually each time | `create()` / `update()` handle them automatically |
| Business logic duplicated across endpoints | Tested once in the service, called anywhere |
| No reuse from management commands or tasks | Services work the same in views, Celery tasks, or the shell |

## The Four Controller Patterns

django-matt supports a progression of controller styles. Use the simplest that fits the task.

### 1. Declarative (zero-code CRUD)

```python
@api.controller("/products", tags=["Products"])
class ProductController(CRUDController):
    model = Product
    permission_classes = [IsAuthenticated]
    # GET /, POST /, GET /{id}, PATCH /{id}, DELETE /{id} — all generated
```

### 2. Basic (manual endpoints, inline ORM)

Appropriate for a handful of endpoints where the logic is trivial.

```python
@api.controller("/products", tags=["Products"])
class ProductController(APIController):
    @api.get("/")
    async def list_products(self, request):
        return [p async for p in Product.objects.all()]

    @api.post("/")
    async def create_product(self, request, data: ProductCreateSchema):
        return await Product.objects.acreate(**data.model_dump())
```

### 3. Partial service (views + custom business logic)

Use composable views for standard CRUD, add service methods for the non-trivial bits.

```python
class ProductController(APIController):
    list = ListView(model=Product)
    create = CreateView(model=Product)

    @api.post("/{id}/feature")
    async def feature_product(self, request, id: int):
        product = await product_service.get(id)
        await product_service.update_fields(id, featured=True, user=request.user)
        return product
```

### 4. Full service layer (thin controller + service class)

The recommended pattern for any controller with business logic, multiple callers, or testability requirements.

```python
# myapp/services.py
class ProductService(CRUDService["Product"]):
    model = Product

    async def get_featured(self) -> list[Product]:
        return [p async for p in self.get_queryset().filter(featured=True)]

# myapp/controllers.py
class ProductController(APIController):
    def __init__(self):
        self.service = ProductService()
        super().__init__()

    @api.get("/")
    async def list_products(self, request):
        items, total = await self.service.list()
        return {"items": items, "total": total}
```

## Quick Start: Todo Example

### 1. Define the service

```python
# todo/services.py
from django_matt.services import CRUDService
from .models import Todo

class TodoService(CRUDService["Todo"]):
    model = Todo

    def get_queryset(self):
        return super().get_queryset().select_related("created_by")

    async def for_user(self, user) -> list[Todo]:
        return [t async for t in self.get_queryset().filter(created_by=user)]

    async def mark_complete(self, pk: int, user) -> Todo:
        return await self.update_fields(pk, completed=True, user=user)
```

### 2. Inject it into the controller

```python
# todo/controllers.py
from django_matt.core import APIController
from django_matt.auth import jwt_required
from .schemas import TodoCreateSchema, TodoUpdateSchema
from .services import TodoService

@api.controller("/todos", tags=["Todos"])
class TodoController(APIController):
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.service = TodoService()
        super().__init__()

    @api.get("/")
    async def list_todos(self, request):
        items, total = await self.service.list(created_by=request.user)
        return {"items": items, "total": total}

    @api.post("/")
    async def create_todo(self, request, data: TodoCreateSchema):
        return await self.service.create(data.model_dump(), user=request.user)

    @api.get("/{id}")
    async def get_todo(self, request, id: int):
        return await self.service.get(id)

    @api.patch("/{id}")
    async def update_todo(self, request, id: int, data: TodoUpdateSchema):
        return await self.service.update(id, data.model_dump(), user=request.user, partial=True)

    @api.delete("/{id}")
    async def delete_todo(self, request, id: int):
        await self.service.delete(id, user=request.user)
        return {"deleted": True}

    @api.post("/{id}/complete")
    async def complete_todo(self, request, id: int):
        return await self.service.mark_complete(id, user=request.user)
```

## When to Use Which Class

| Situation | Use |
|-----------|-----|
| Reading from and writing to one model | `CRUDService` |
| Custom queries, read-only access to a model | `BaseService` |
| Calling an external API (Stripe, Resend, Twilio, Slack) | `BaseThirdPartyService` |

### BaseService

Read-only helpers: `get()`, `get_or_none()`, `get_by()`, `exists()`, `count()`, `get_queryset()`, `get_active_queryset()`.

Use when you need to query a model but have no write operations in this service, or to build a domain service that spans multiple models.

```python
from django_matt.services import BaseService
from .models import Report

class ReportQueryService(BaseService["Report"]):
    model = Report

    async def pending(self) -> list[Report]:
        return [r async for r in self.get_queryset().filter(status="pending")]
```

### CRUDService

Extends `BaseService` with `list()`, `create()`, `update()`, `update_fields()`, `delete()`, `bulk_create()`, `bulk_update()`, `bulk_delete()`, and `get_or_create()`.

```python
from django_matt.services import CRUDService

class InvoiceService(CRUDService["Invoice"]):
    model = Invoice

    def get_queryset(self):
        return super().get_queryset().select_related("customer", "line_items")
```

### BaseThirdPartyService

HTTP client base for external APIs. Wraps `httpx.AsyncClient` with auth headers, orjson serialization, and error mapping.

```python
from django_matt.services import BaseThirdPartyService

class ResendService(BaseThirdPartyService):
    base_url = "https://api.resend.com"

    def _auth_headers(self) -> dict:
        from django.conf import settings
        return {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}

    async def send(self, to: str, subject: str, html: str) -> dict:
        return await self._post("/emails", {"from": "no-reply@example.com",
                                             "to": to, "subject": subject, "html": html})
```

## get_queryset() Customization

`get_queryset()` is the single place to control what records every service method sees. Override it to add `select_related`, tenant filters, soft-delete exclusions, or ordering defaults.

```python
class ArticleService(CRUDService["Article"]):
    model = Article

    def get_queryset(self):
        # Eager-load author and tags; exclude soft-deleted records by default
        return (
            super()
            .get_queryset()
            .select_related("author")
            .prefetch_related("tags")
            .filter(deleted_at__isnull=True)
        )
```

All methods (`list`, `get`, `update`, `delete`, `bulk_delete`) build on `get_queryset()`, so this override applies uniformly.

## Domain Methods Beyond CRUD

Add any method that belongs to the domain. Keep them `async` and delegate ORM work through the queryset.

```python
class OrderService(CRUDService["Order"]):
    model = Order

    async def pending_for_user(self, user) -> list[Order]:
        return [o async for o in self.get_queryset().filter(user=user, status="pending")]

    async def cancel(self, pk: int, user, reason: str) -> Order:
        order = await self.get(pk)
        if order.status not in ("pending", "processing"):
            from django_matt.services import ValidationError
            raise ValidationError(f"Cannot cancel an order in status '{order.status}'")
        return await self.update(pk, {"status": "cancelled", "cancel_reason": reason}, user=user)

    async def revenue_this_month(self) -> Decimal:
        from django.utils import timezone
        from django.db.models import Sum
        start = timezone.now().replace(day=1)
        result = await self.get_queryset().filter(
            created_at__gte=start, status="completed"
        ).aaggregate(total=Sum("amount"))
        return result["total"] or Decimal("0")
```

## Error Handling

All service exceptions inherit from `ServiceError`.

```python
from django_matt.services import (
    ServiceError,
    NotFoundError,    # code="not_found"
    ValidationError,  # code="validation_error", optional .field
    ConflictError,    # code="conflict"
)
```

`CRUDService.get()` raises `NotFoundError` automatically. `create()` and `update()` wrap database exceptions in `ValidationError`. Raise `ConflictError` for business-rule violations that don't fit "not found" or "invalid field".

Map these to HTTP responses in your controller's error handler or middleware:

```python
@api.controller("/orders", tags=["Orders"])
class OrderController(APIController):
    def __init__(self):
        self.service = OrderService()
        super().__init__()

    @api.post("/{id}/cancel")
    async def cancel_order(self, request, id: int, data: CancelSchema):
        try:
            order = await self.service.cancel(id, user=request.user, reason=data.reason)
            return order
        except NotFoundError as exc:
            raise Http404(exc.message)
        except ValidationError as exc:
            raise HttpError(422, exc.message)
```

## Import Reference

```python
from django_matt.services import (
    # Base classes
    BaseService,
    CRUDService,
    BaseThirdPartyService,
    # Exceptions
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
    ThirdPartyServiceError,
)
```

## See Also

- [CRUDService API Reference](./crud-service.md) — all method signatures
- [BaseThirdPartyService Guide](./third-party.md) — external HTTP clients
- [Service Patterns](./patterns.md) — naming, structure, testing, anti-patterns
- [Migration Guide](./migration.md) — extracting logic from fat controllers into services
- [Service Layer Tutorial](../tutorials/service-layer.md) — end-to-end walkthrough
- [Controllers](../controllers.md) — controller overview
- [Dependency Injection](../di/overview.md) — alternative injection strategies

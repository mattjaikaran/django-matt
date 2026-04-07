# Migrating to Services

This guide walks through extracting business logic from fat controllers into service classes. The goal: controllers handle HTTP, services handle everything else.

## Identify Logic to Extract

Look for these signals in your controller methods:

| Signal | Example | Extract to |
|--------|---------|-----------|
| Direct ORM calls | `await Product.objects.aget(pk=id)` | `service.get(id)` |
| Conditional business rules | `if order.status != "pending": raise ...` | `service.cancel(pk, ...)` |
| Audit field assignment | `obj.updated_by = request.user` | Handled by `CRUDService.update()` |
| Multi-model orchestration | Create order + reserve inventory + charge | Orchestrator service |
| Repeated query patterns | Same `.filter().select_related()` in 3 endpoints | `service.get_queryset()` |
| Side effects | Send email, emit event, invalidate cache | Service method post-mutation |

## Step-by-Step Extraction

### 1. Create the service file

```python
# myapp/services.py
from django_matt.services import CRUDService
from .models import Product

class ProductService(CRUDService["Product"]):
    model = Product

    def get_queryset(self):
        return super().get_queryset().select_related("category")
```

### 2. Move domain methods from controller to service

Take each block of business logic and make it an async method on the service.

### 3. Wire the controller to the service

```python
class ProductController(APIController):
    def __init__(self):
        self.service = ProductService()
        super().__init__()
```

### 4. Replace inline ORM with service calls

Each controller method becomes a one-liner delegation.

## Before / After

### Before: fat controller

```python
@api.controller("/orders", tags=["Orders"])
class OrderController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list_orders(self, request, page: int = 1, status: str | None = None):
        qs = Order.objects.select_related("user").prefetch_related("items")
        if status:
            qs = qs.filter(status=status)
        qs = qs.filter(user=request.user)
        total = await qs.acount()
        offset = (page - 1) * 20
        items = [o async for o in qs[offset:offset + 20]]
        return {"items": items, "total": total, "page": page}

    @api.post("/")
    async def create_order(self, request, data: OrderCreateSchema):
        order = Order(**data.model_dump())
        order.created_by = request.user
        order.user = request.user
        await order.asave()
        return order

    @api.post("/{id}/cancel")
    async def cancel_order(self, request, id: int, data: CancelSchema):
        try:
            order = await Order.objects.select_related("user").aget(pk=id)
        except Order.DoesNotExist:
            raise HttpError(404, "Order not found")
        if order.user_id != request.user.id:
            raise HttpError(403, "Forbidden")
        if order.status not in ("pending", "processing"):
            raise HttpError(422, f"Cannot cancel order in status '{order.status}'")
        order.status = "cancelled"
        order.cancel_reason = data.reason
        order.updated_by = request.user
        await order.asave()
        # Send email
        await send_cancellation_email(order)
        return order
```

Problems:
- ORM queries duplicated across methods
- `select_related` chains repeated
- Business rules (cancel validation) mixed with HTTP error handling
- Audit fields set manually
- Side effects (email) embedded in the endpoint

### After: thin controller + service

```python
# orders/services.py
from django_matt.services import CRUDService, ValidationError
from .models import Order

class OrderService(CRUDService["Order"]):
    model = Order

    def get_queryset(self):
        return super().get_queryset().select_related("user").prefetch_related("items")

    async def cancel(self, pk: int, user, reason: str) -> Order:
        order = await self.get(pk)
        if order.status not in ("pending", "processing"):
            raise ValidationError(f"Cannot cancel order in status '{order.status}'")
        return await self.update(pk, {
            "status": "cancelled",
            "cancel_reason": reason,
        }, user=user)
```

```python
# orders/controllers.py
from django_matt.core import APIController
from django_matt.permissions import IsAuthenticated
from django_matt.services import NotFoundError, ValidationError
from .services import OrderService
from .schemas import OrderCreateSchema, CancelSchema

@api.controller("/orders", tags=["Orders"])
class OrderController(APIController):
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.service = OrderService()
        self.email = EmailService()
        super().__init__()

    @api.get("/")
    async def list_orders(self, request, page: int = 1, status: str | None = None):
        items, total = await self.service.list(
            page=page, user=request.user, status=status,
        )
        return {"items": items, "total": total, "page": page}

    @api.post("/")
    async def create_order(self, request, data: OrderCreateSchema):
        return await self.service.create(data.model_dump(), user=request.user)

    @api.post("/{id}/cancel")
    async def cancel_order(self, request, id: int, data: CancelSchema):
        order = await self.service.cancel(id, user=request.user, reason=data.reason)
        await self.email.send_cancellation(order)
        return order
```

What changed:
- `get_queryset()` defines `select_related` / `prefetch_related` once
- `list()` handles pagination, filtering, and `None`-skipping automatically
- `create()` sets `created_by` automatically when the model has the field
- `cancel()` owns the business rule; raises `ValidationError` (not `HttpError`)
- The controller catches service exceptions and maps them to HTTP status codes (or lets the framework's error handler do it)
- Side effects (email) are composed in the controller, not buried in the service

## Refactoring Checklist

Use this checklist when migrating an existing app to the service pattern.

- [ ] Create `myapp/services.py` (or `myapp/services/` package for larger apps)
- [ ] Define one `CRUDService` subclass per model that has write operations
- [ ] Move `select_related` / `prefetch_related` into `get_queryset()`
- [ ] Move business validation logic into service domain methods
- [ ] Remove manual `created_by` / `updated_by` assignments (handled by `CRUDService`)
- [ ] Replace `Model.objects.aget(pk=id)` with `service.get(id)` (auto-raises `NotFoundError`)
- [ ] Replace inline pagination math with `service.list(page=, page_size=)`
- [ ] Move multi-model transaction blocks into an orchestrator service
- [ ] Wire the service into the controller's `__init__`
- [ ] Ensure controller methods only do: parse input, call service, format output
- [ ] Write service-level tests (no HTTP, real DB)
- [ ] Verify existing controller/integration tests still pass
- [ ] Delete dead code from the controller

## Common Pitfalls During Migration

### Forgetting to call `super().__init__()`

```python
# Wrong — breaks controller setup
def __init__(self):
    self.service = ProductService()

# Correct
def __init__(self):
    self.service = ProductService()
    super().__init__()
```

### Constructing services per-request (unnecessary allocation)

```python
# Wrong — new instance on every request
@api.get("/")
async def list_products(self, request):
    service = ProductService()
    return await service.list()

# Correct — constructed once in __init__
def __init__(self):
    self.service = ProductService()
    super().__init__()
```

Exception: tenant-scoped services that need `request.auth.organization` must be constructed per-request.

### Putting HTTP concerns in the service

```python
# Wrong — service should not know about HTTP status codes
class OrderService(CRUDService["Order"]):
    async def cancel(self, pk, user):
        order = await self.get(pk)
        if order.status == "shipped":
            raise HttpError(422, "Cannot cancel shipped order")  # HTTP leak

# Correct — raise a service exception
class OrderService(CRUDService["Order"]):
    async def cancel(self, pk, user):
        order = await self.get(pk)
        if order.status == "shipped":
            raise ValidationError("Cannot cancel shipped order")
```

## See Also

- [Service Layer Overview](./index.md)
- [Service Patterns](./patterns.md)
- [CRUDService API Reference](./crud-service.md)
- [Service Layer Tutorial](../tutorials/service-layer.md)

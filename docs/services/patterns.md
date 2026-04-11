# Service Patterns and Best Practices

## Naming Conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| File | `services.py` in the app directory | `products/services.py` |
| Class | `{Domain}Service` | `ProductService`, `OrderService` |
| Third-party file | `{vendor}_service.py` or grouped in `integrations/` | `stripe_service.py` |
| Third-party class | `{Vendor}Service` | `StripeService`, `ResendService` |
| Domain methods | verb + noun, descriptive | `cancel_order()`, `for_user()`, `revenue_this_month()` |

Avoid generic names like `DataService` or `AppService`. Each service should be scoped to one model or one external system.

## File Structure

Services live beside the rest of the app code:

```
myapp/
├── models.py
├── schemas.py
├── services.py      # <- internal CRUDService / BaseService
├── controllers.py
├── admin.py
└── tests/
    ├── test_services.py
    └── test_controllers.py
```

For larger apps with several domain services, split into a `services/` package:

```
orders/
├── models.py
├── schemas.py
├── services/
│   ├── __init__.py          # re-export public API
│   ├── order_service.py     # CRUDService for Order model
│   ├── fulfillment_service.py
│   └── pricing_service.py
├── controllers.py
└── tests/
```

Third-party service clients belong in a shared location:

```
integrations/
├── stripe_service.py
├── resend_service.py
├── slack_service.py
└── twilio_service.py
```

Or co-located with the feature module that owns them:

```
billing/
├── stripe_service.py    # Stripe HTTP client
├── billing_service.py   # Internal CRUD service
└── controllers.py
```

## Service per Model vs Service per Domain

**Service per model** is the right default. One `CRUDService` per Django model keeps responsibilities clear.

```python
class ProductService(CRUDService["Product"]): ...
class CategoryService(CRUDService["Category"]): ...
class InventoryService(CRUDService["Inventory"]): ...
```

**Service per domain** is appropriate when an operation spans multiple models and does not belong to any single one of them. Keep it as a `BaseService` with a descriptive name.

```python
class CheckoutService(BaseService["Order"]):
    """Orchestrates order creation, inventory reservation, and payment."""

    def __init__(self):
        super().__init__()
        self.orders = OrderService()
        self.inventory = InventoryService()
        self.stripe = StripeService()

    async def place_order(self, user, cart: Cart, payment_method: str) -> Order:
        async with transaction.atomic():
            await self.inventory.reserve(cart.items)
            order = await self.orders.create({"user": user, "items": cart.items})
        charge = await self.stripe.charge(payment_method, order.total)
        await self.orders.update_fields(order.pk, stripe_charge_id=charge["id"])
        return order
```

## Overriding get_queryset() for Tenant Isolation

Multi-tenant applications should scope every query to the current tenant at the queryset level, not in each individual method.

```python
class TenantProductService(CRUDService["Product"]):
    model = Product

    def __init__(self, organization):
        super().__init__()
        self._org = organization

    def get_queryset(self):
        return super().get_queryset().filter(organization=self._org)
```

All inherited methods (`list`, `get`, `update`, `delete`, `bulk_*`) automatically respect the tenant filter.

```python
# In the controller
class ProductController(APIController):
    @api.get("/")
    async def list_products(self, request):
        service = TenantProductService(request.auth.organization)
        items, total = await service.list()
        return {"items": items, "total": total}
```

For convenience, create an `org_service()` helper on the controller:

```python
class TenantController(APIController):
    service_class: type[CRUDService]

    def org_service(self, request):
        return self.service_class(request.auth.organization)
```

## Combining Services in Controllers

A controller may inject multiple services. Keep one service per concern.

```python
class OrderController(APIController):
    def __init__(self):
        self.orders = OrderService()
        self.notifications = NotificationService()
        self.stripe = StripeService()
        super().__init__()

    @api.post("/{id}/cancel")
    async def cancel_order(self, request, id: int, data: CancelSchema):
        order = await self.orders.cancel(id, user=request.user, reason=data.reason)
        await self.notifications.send_cancellation(order)
        return order
```

Keep the controller method thin: it parses input, calls services, and returns output. Business logic lives in the service.

## Testing Services

Test services directly without HTTP overhead. Use `pytest-django` with the `db` or `async_db` fixture.

### Unit test with the database

```python
import pytest
from products.models import Product
from products.services import ProductService

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_create_product(user):
    service = ProductService()
    product = await service.create({"name": "Widget", "price": "9.99"}, user=user)
    assert product.pk is not None
    assert product.name == "Widget"
    assert product.created_by == user


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_list_pagination(product_factory):
    await product_factory.create_batch(25)
    service = ProductService()

    page1, total = await service.list(page=1, page_size=10)
    assert len(page1) == 10
    assert total == 25

    page3, _ = await service.list(page=3, page_size=10)
    assert len(page3) == 5


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_not_found():
    from django_matt.services import NotFoundError
    service = ProductService()
    with pytest.raises(NotFoundError):
        await service.get(999999)
```

### Mocking third-party services

Use `unittest.mock.AsyncMock` to avoid real HTTP calls in unit tests.

```python
import pytest
from unittest.mock import AsyncMock, patch
from billing.controllers import BillingController

@pytest.mark.asyncio
async def test_create_checkout_mocked(client, user):
    mock_stripe = AsyncMock()
    mock_stripe.create_checkout_session.return_value = {"url": "https://stripe.com/pay/xxx"}

    with patch("billing.controllers.StripeService", return_value=mock_stripe):
        response = await client.post("/billing/checkout", json={"price_id": "price_xxx"})

    assert response.status_code == 200
    assert "url" in response.json()
    mock_stripe.create_checkout_session.assert_called_once()
```

For integration tests that should hit a real (sandbox) API, create a fixture that reads from environment variables and skips when they are absent:

```python
@pytest.fixture
def stripe_service():
    import os
    if not os.getenv("STRIPE_TEST_KEY"):
        pytest.skip("STRIPE_TEST_KEY not set")
    from billing.stripe_service import StripeService
    return StripeService()
```

## Anti-Patterns to Avoid

### ORM calls directly in controllers

```python
# Bad: business logic and DB access in the controller
@api.post("/orders/{id}/cancel")
async def cancel(self, request, id: int):
    order = await Order.objects.aget(pk=id)
    if order.user_id != request.user.id:
        raise HttpError(403, "Forbidden")
    order.status = "cancelled"
    await order.asave()
    await Notification.objects.acreate(user=request.user, message="Order cancelled")
    return order

# Good: controller delegates, service encapsulates
@api.post("/orders/{id}/cancel")
async def cancel(self, request, id: int):
    return await self.service.cancel(id, user=request.user)
```

### Fat services with unrelated responsibilities

Keep each service focused. An `OrderService` should not send emails or call Slack. Compose those from the controller or a domain orchestrator.

```python
# Bad: order service knows about email delivery
class OrderService(CRUDService["Order"]):
    async def cancel(self, pk, user, reason):
        order = await self.update(pk, {"status": "cancelled"}, user=user)
        await send_email(user.email, "Your order was cancelled")  # wrong layer
        return order

# Good: controller composes the outcome
async def cancel_order(self, request, id: int, data: CancelSchema):
    order = await self.orders.cancel(id, user=request.user, reason=data.reason)
    await self.email.send_cancellation(order)  # separate service
    return order
```

### Creating services inside view methods

Service construction should happen once in `__init__`, not on every request.

```python
# Bad: new service instance per request
@api.get("/")
async def list_products(self, request):
    service = ProductService()  # constructed on every request
    items, total = await service.list()
    return {"items": items, "total": total}

# Good: constructed once
def __init__(self):
    self.service = ProductService()
    super().__init__()

@api.get("/")
async def list_products(self, request):
    items, total = await self.service.list()
    return {"items": items, "total": total}
```

Exception: tenant-scoped services that need a per-request value (like `organization`) are fine to construct per request.

### Catching all exceptions and swallowing errors

```python
# Bad: hides bugs
async def create_product(self, data):
    try:
        return await self.service.create(data)
    except Exception:
        return None

# Good: let service exceptions propagate, catch specifically in the controller
@api.post("/")
async def create_product(self, request, data: ProductCreateSchema):
    try:
        return await self.service.create(data.model_dump(), user=request.user)
    except ValidationError as exc:
        raise HttpError(422, exc.message)
```

### Bypassing get_queryset() with direct manager calls

Always use `self.get_queryset()` inside service methods. Calling `self.model.objects.filter(...)` directly bypasses tenant filters and soft-delete exclusions defined in `get_queryset()`.

```python
# Bad: bypasses get_queryset() overrides
async def active_products(self):
    return [p async for p in Product.objects.filter(is_active=True)]

# Good: goes through get_queryset()
async def active_products(self):
    return [p async for p in self.get_queryset().filter(is_active=True)]
```

## Advanced Patterns

### Service + Event Bus

Emit domain events after mutations so other parts of the system can react without tight coupling. The service owns *when* to emit; handlers own *what happens next*.

```python
from django_matt.events.bus import Event, get_event_bus
from django_matt.services import CRUDService

class OrderCreated(Event):
    __event_type__ = "order.created"
    order_id: int
    user_id: int
    total: str

class OrderService(CRUDService["Order"]):
    model = Order

    async def place(self, data: dict, user) -> Order:
        order = await self.create(data, user=user)
        bus = get_event_bus()
        await bus.emit(OrderCreated(
            order_id=order.pk,
            user_id=user.pk,
            total=str(order.total),
        ))
        return order
```

Register handlers at app startup (e.g. in `AppConfig.ready()`):

```python
from django_matt.events.bus import get_event_bus

def ready(self):
    bus = get_event_bus()
    bus.subscribe("order.created", send_confirmation_email)
    bus.subscribe("order.created", update_analytics)
    bus.subscribe("order.*", audit_log_handler)  # wildcard
```

### Service + CQRS

Use the CQRS `CommandBus` when you want explicit command objects with middleware (logging, validation, authorization) applied uniformly.

```python
from django_matt.cqrs.commands import Command, CommandHandler, CommandBus

class CreateProduct(Command):
    name: str
    price: str
    category_id: int

class CreateProductHandler:
    def __init__(self):
        self.service = ProductService()

    async def execute(self, command: CreateProduct) -> Product:
        return await self.service.create(command.model_dump())

# Registration
bus = CommandBus()
bus.register(CreateProduct, CreateProductHandler())

# Dispatch from controller
product = await bus.dispatch(CreateProduct(name="Widget", price="9.99", category_id=1))
```

The service stays the same regardless of whether it is called directly or through the command bus.

### Service + Interceptors

Interceptors wrap the HTTP dispatch layer (before/after the controller method). They handle cross-cutting concerns like request logging, timing, and header injection. Services are *not* wrapped by interceptors — keep service logic pure.

```python
from django_matt.interceptors.base import Interceptor

class TimingInterceptor(Interceptor):
    order = 0

    async def before_request(self, request, **kwargs):
        import time
        request._start_time = time.perf_counter()
        return None

    async def after_response(self, request, response, **kwargs):
        import time
        elapsed = time.perf_counter() - request._start_time
        response["X-Response-Time"] = f"{elapsed:.3f}s"
        return response
```

If you need to intercept service calls specifically (e.g. logging every `create()` call), override the service method or use the event bus instead.

### Service Composition

When an operation spans multiple models, create an orchestrator service that delegates to per-model services. The orchestrator owns the transaction boundary.

```python
class CheckoutService(BaseService["Order"]):
    def __init__(self):
        super().__init__()
        self.orders = OrderService()
        self.inventory = InventoryService()
        self.payments = PaymentService()

    async def checkout(self, user, cart, payment_method: str) -> Order:
        async with transaction.atomic():
            order = await self.orders.create(
                {"user": user, "items": cart.items, "total": cart.total},
                user=user,
            )
            for item in cart.items:
                await self.inventory.reserve(item.inventory_id, item.quantity)
            await self.payments.charge(order, payment_method)
        return order
```

The controller remains thin:

```python
@api.post("/checkout")
async def checkout(self, request, data: CheckoutSchema):
    cart = await self.carts.get_or_create_for_user(request.user)
    return await self.checkout_service.checkout(
        request.user, cart, data.payment_method,
    )
```

### Service + Transactions

`CRUDService.create()` and `CRUDService.update()` already run inside `transaction.atomic()`. For multi-step operations, wrap the outer call:

```python
from django.db import transaction

class TransferService(BaseService["Transaction"]):
    def __init__(self):
        super().__init__()
        self.accounts = AccountService()

    async def transfer(self, from_id: int, to_id: int, amount: Decimal) -> Transaction:
        async with transaction.atomic():
            from_acct = await self.accounts.get(from_id)
            if from_acct.balance < amount:
                raise ValidationError("Insufficient funds")
            await self.accounts.update_fields(from_id, balance=from_acct.balance - amount)
            await self.accounts.update_fields(to_id, balance=F("balance") + amount)
            return await Transaction.objects.acreate(
                from_account_id=from_id,
                to_account_id=to_id,
                amount=amount,
            )
```

If any step raises, the entire block rolls back.

### Multi-Tenant Service Pattern

Scope every query to the current tenant at the queryset level. Pass the organization at construction time so all inherited methods respect the filter automatically.

```python
class TenantCRUDService(CRUDService[ModelT]):
    """Base class for tenant-scoped services."""

    def __init__(self, organization):
        super().__init__()
        self._org = organization

    def get_queryset(self):
        return super().get_queryset().filter(organization=self._org)

class ProjectService(TenantCRUDService["Project"]):
    model = Project

    def get_queryset(self):
        return super().get_queryset().select_related("owner").prefetch_related("teams")

# In the controller — construct per-request with the tenant
@api.get("/")
async def list_projects(self, request):
    service = ProjectService(request.auth.organization)
    items, total = await service.list()
    return {"items": items, "total": total}
```

### Service Testing Patterns

**Test the service directly** — no HTTP layer, no mocking the database:

```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_order_cancel_validates_status(order_factory, user):
    service = OrderService()
    order = await order_factory.create(status="shipped")

    with pytest.raises(ValidationError, match="Cannot cancel"):
        await service.cancel(order.pk, user=user, reason="changed mind")
```

**Test service composition** with real DB and mocked externals:

```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_checkout_reserves_inventory(cart_with_items, user):
    mock_payments = AsyncMock()
    mock_payments.charge.return_value = {"id": "ch_test"}

    service = CheckoutService()
    service.payments = mock_payments

    order = await service.checkout(user, cart_with_items, "card")
    assert order.pk is not None
    mock_payments.charge.assert_called_once()
```

**Test event emission** by subscribing a collector:

```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_place_order_emits_event(user):
    from django_matt.events.bus import get_event_bus, reset_event_bus
    reset_event_bus()
    bus = get_event_bus()

    received = []
    bus.subscribe("order.created", lambda e: received.append(e))

    service = OrderService()
    await service.place({"total": "99.99"}, user=user)

    assert len(received) == 1
    assert received[0].event_type == "order.created"
```

## See Also

- [Service Layer Overview](./index.md)
- [CRUDService API Reference](./crud-service.md)
- [Third-Party Services](./third-party.md)
- [Migration Guide](./migration.md)
- [Service Layer Tutorial](../tutorials/service-layer.md)
- [Testing Guide](../testing/client.md)

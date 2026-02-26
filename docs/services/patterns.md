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

## See Also

- [Service Layer Overview](./index.md)
- [CRUDService API Reference](./crud-service.md)
- [Third-Party Services](./third-party.md)
- [Testing Guide](../testing/)

# Lifecycle Hooks

Lifecycle hooks allow you to inject custom logic before and after CRUD operations. They enable features like audit logging, notifications, cache invalidation, and validation without subclassing views.

## Overview

django-matt provides two ways to define hooks:

1. **Class-based hooks**: Methods on your ViewSet class
2. **Decorator-based hooks**: Functions registered with decorators

## Hook Types

| Hook | When Called | Receives | Returns |
|------|-------------|----------|---------|
| `before_list` | Before querying | queryset | Modified queryset |
| `after_list` | After serialization | result dict | Modified result |
| `before_create` | Before saving | data dict | Modified data |
| `after_create` | After saving | instance | Instance |
| `before_read` | Before fetching | lookup value | Modified lookup |
| `after_read` | After fetching | instance | Instance |
| `before_update` | Before saving | (instance, data) | Tuple |
| `after_update` | After saving | instance | Instance |
| `before_delete` | Before deletion | instance | Instance |
| `after_delete` | After deletion | instance | None |
| `on_error` | On exception | error | None |

## Class-Based Hooks

Define hooks as async methods on your ViewSet:

```python
from django_matt.views import APIViewSet, ListView, CreateView

class ProductViewSet(APIViewSet):
    model = Product

    list_products = ListView()
    create_product = CreateView()
    update_product = UpdateView()
    delete_product = DeleteView()

    async def before_create(self, request, data):
        """Add creator to data before saving."""
        data["created_by_id"] = request.user.id
        return data

    async def after_create(self, request, instance):
        """Send notification after creation."""
        await send_notification(f"Product created: {instance.name}")
        return instance

    async def before_update(self, request, instance, data):
        """Track changes before update."""
        data["previous_price"] = instance.price
        return instance, data

    async def after_delete(self, request, instance):
        """Clean up files after deletion."""
        await cleanup_files(instance.id)
```

## Decorator-Based Hooks

Register hooks using decorators for more flexibility:

```python
from django_matt.views import before_create, after_create, on_error
from django_matt.views.hooks import HookContext

# Hook for specific ViewSet
@before_create(ProductViewSet)
async def validate_product(context: HookContext, data: dict) -> dict:
    """Validate product data."""
    if data.get("price", 0) < 0:
        raise ValueError("Price cannot be negative")
    return data

@after_create(ProductViewSet)
async def sync_inventory(context: HookContext, instance) -> Product:
    """Sync to inventory system after creation."""
    await inventory_api.sync(instance)
    return instance

# Global hook - applies to all ViewSets
@before_create
async def log_all_creates(context: HookContext, data: dict) -> dict:
    """Log all create operations."""
    logger.info(f"Creating {context.model.__name__}: {data}")
    return data
```

## HookContext

The `HookContext` object provides information about the current operation:

```python
@dataclass
class HookContext:
    request: HttpRequest        # The HTTP request
    view_class: type            # The view class (ListView, CreateView, etc.)
    viewset: Any                # The ViewSet instance
    hook_type: HookType         # Current hook type
    instance: Model | None      # Model instance (if available)
    data: dict | None           # Request data (if available)
    queryset: QuerySet | None   # Queryset (for list operations)
    error: Exception | None     # Error (for on_error hooks)
    extra: dict                 # Additional context

    @property
    def user(self) -> User:
        """Current user from request."""
        return self.request.user

    @property
    def model(self) -> type[Model]:
        """Model class from ViewSet."""
        return self.viewset.model
```

## Hook Registration

### ViewSet-Specific Hooks

Register hooks for a specific ViewSet:

```python
from django_matt.views import before_create, after_create

@before_create(ProductViewSet)
async def product_hook(context, data):
    return data

# Or using register_hook
from django_matt.views.hooks import register_hook

@register_hook("before_create", ProductViewSet)
async def another_hook(context, data):
    return data
```

### Global Hooks

Register hooks that apply to all ViewSets:

```python
from django_matt.views.hooks import register_global_hook

@register_global_hook("after_create")
async def audit_all_creates(context, instance):
    """Log all creates to audit table."""
    await AuditLog.objects.acreate(
        action="create",
        model=context.model.__name__,
        object_id=str(instance.pk),
        user=context.user,
    )
    return instance

@register_global_hook("on_error")
async def log_all_errors(context, error):
    """Log all errors."""
    logger.error(f"Error in {context.view_class.__name__}: {error}")
```

## Hook Priority

Control hook execution order with priority:

```python
from django_matt.views import before_create
from django_matt.views.decorators import priority

# Lower priority runs first
@priority(-10)
@before_create(ProductViewSet)
async def run_first(context, data):
    """This runs before other hooks."""
    return data

@priority(10)
@before_create(ProductViewSet)
async def run_last(context, data):
    """This runs after other hooks."""
    return data
```

## Conditional Hooks

Run hooks only when conditions are met:

```python
from django_matt.views import before_delete
from django_matt.views.decorators import when, unless

# Only run for staff users
@when(lambda ctx: ctx.user.is_staff)
@before_delete(ProductViewSet)
async def staff_only_delete_check(context, instance):
    """Extra validation for staff deletions."""
    await audit_sensitive_delete(instance)
    return instance

# Run unless user is superuser
@unless(lambda ctx: ctx.user.is_superuser)
@before_delete(ProductViewSet)
async def prevent_critical_delete(context, instance):
    """Prevent deletion of critical products."""
    if instance.is_critical:
        raise ValueError("Cannot delete critical product")
    return instance
```

## Stopping the Hook Chain

Raise `StopHookChain` to prevent subsequent hooks from running:

```python
from django_matt.views.hooks import StopHookChain

@before_create(ProductViewSet)
async def check_quota(context, data):
    """Stop creation if quota exceeded."""
    if await is_quota_exceeded(context.user):
        raise StopHookChain({"error": "Quota exceeded"})
    return data
```

## Hook Composition

Compose multiple functions into a single hook:

```python
from django_matt.views.decorators import compose_hooks

async def validate_data(context, data):
    if not data.get("name"):
        raise ValueError("Name required")
    return data

async def normalize_data(context, data):
    data["name"] = data["name"].strip().title()
    return data

async def add_defaults(context, data):
    data.setdefault("status", "draft")
    return data

@compose_hooks(validate_data, normalize_data, add_defaults)
@before_create(ProductViewSet)
async def prepare_product(context, data):
    """Final processing after composition."""
    return data
```

## Error Handling Decorators

### `catch_and_continue`

Continue hook chain even if an error occurs:

```python
from django_matt.views.decorators import catch_and_continue

@catch_and_continue(ConnectionError, default=None)
@after_create(ProductViewSet)
async def sync_external_service(context, instance):
    """Try to sync, but don't fail if service is down."""
    await external_service.sync(instance)
    return instance
```

### `retry`

Retry failed hooks:

```python
from django_matt.views.decorators import retry

@retry(times=3, delay=0.5, exceptions=(ConnectionError, TimeoutError))
@after_create(ProductViewSet)
async def sync_with_retry(context, instance):
    """Retry up to 3 times with exponential backoff."""
    await external_service.sync(instance)
    return instance
```

## Debugging Hooks

### `log_hook`

Log hook execution for debugging:

```python
from django_matt.views.decorators import log_hook
import logging

logger = logging.getLogger(__name__)

@log_hook(logger.debug)
@before_create(ProductViewSet)
async def my_hook(context, data):
    return data
# Logs: "Hook 'my_hook' starting for before_create"
# Logs: "Hook 'my_hook' completed in 1.23ms"
```

### `timed_hook`

Track and warn on slow hooks:

```python
from django_matt.views.decorators import timed_hook

def warn_slow(name, ms):
    logger.warning(f"Slow hook: {name} took {ms}ms")

@timed_hook(max_ms=100, on_slow=warn_slow)
@after_create(ProductViewSet)
async def potentially_slow_hook(context, instance):
    await complex_operation(instance)
    return instance
```

## Practical Examples

### Audit Logging

```python
from django_matt.views import after_create, after_update, after_delete
from django_matt.views.hooks import register_global_hook

@register_global_hook("after_create")
async def audit_create(context, instance):
    await AuditLog.objects.acreate(
        action="create",
        model=context.model.__name__,
        object_id=str(instance.pk),
        user=context.user,
        data={"created": True},
        ip_address=context.request.META.get("REMOTE_ADDR"),
    )
    return instance

@register_global_hook("after_update")
async def audit_update(context, instance):
    await AuditLog.objects.acreate(
        action="update",
        model=context.model.__name__,
        object_id=str(instance.pk),
        user=context.user,
        data=context.extra.get("changes", {}),
    )
    return instance

@register_global_hook("after_delete")
async def audit_delete(context, instance):
    await AuditLog.objects.acreate(
        action="delete",
        model=context.model.__name__,
        object_id=str(instance.pk),
        user=context.user,
    )
```

### Notifications

```python
from django_matt.views import after_create, after_update

@after_create(OrderViewSet)
async def notify_new_order(context, order):
    """Send notifications for new orders."""
    # Email customer
    await send_email(
        to=order.customer.email,
        template="order_confirmation",
        context={"order": order},
    )

    # Notify admin
    await send_slack_message(
        channel="#orders",
        text=f"New order #{order.id} from {order.customer.name}",
    )

    # Push notification
    await push_notification(
        user_id=order.customer.id,
        title="Order Confirmed",
        body=f"Order #{order.id} has been placed",
    )

    return order

@after_update(OrderViewSet)
async def notify_order_status(context, order):
    """Notify on status changes."""
    previous_status = context.extra.get("previous_status")

    if previous_status != order.status:
        await send_email(
            to=order.customer.email,
            template="order_status_update",
            context={"order": order, "previous": previous_status},
        )

    return order
```

### Cache Invalidation

```python
from django_matt.views import after_create, after_update, after_delete

@after_create(ProductViewSet)
@after_update(ProductViewSet)
@after_delete(ProductViewSet)
async def invalidate_product_cache(context, instance):
    """Invalidate caches when products change."""
    cache_keys = [
        f"product:{instance.id}",
        f"product:slug:{instance.slug}",
        f"category:{instance.category_id}:products",
        "products:featured",
        "products:latest",
    ]

    await cache.delete_many(cache_keys)

    # Invalidate CDN
    await cdn.purge(f"/api/products/{instance.id}")

    return instance

@after_update(ProductViewSet, priority=10)
async def refresh_search_index(context, instance):
    """Update search index after product update."""
    await search_engine.index(
        index="products",
        id=str(instance.id),
        body=ProductSchema.from_orm(instance).model_dump(),
    )
    return instance
```

### Validation

```python
from django_matt.views import before_create, before_update, before_delete

@before_create(ProductViewSet)
async def validate_product_create(context, data):
    """Comprehensive validation before creation."""
    errors = []

    # Business rules
    if data.get("price", 0) < data.get("cost", 0):
        errors.append("Price cannot be less than cost")

    # Uniqueness check
    exists = await Product.objects.filter(sku=data.get("sku")).aexists()
    if exists:
        errors.append("SKU already exists")

    # Category validation
    category = await Category.objects.filter(id=data.get("category_id")).afirst()
    if not category:
        errors.append("Invalid category")
    elif not category.allows_products:
        errors.append("Category does not allow products")

    if errors:
        raise ValueError("; ".join(errors))

    return data

@before_update(ProductViewSet)
async def validate_product_update(context, instance, data):
    """Validate updates."""
    # Prevent certain changes
    if instance.is_published and data.get("sku") != instance.sku:
        raise ValueError("Cannot change SKU of published product")

    # Track changes for audit
    changes = {}
    for key, value in data.items():
        old_value = getattr(instance, key, None)
        if old_value != value:
            changes[key] = {"old": old_value, "new": value}

    context.extra["changes"] = changes
    return instance, data

@before_delete(ProductViewSet)
async def validate_product_delete(context, instance):
    """Prevent deletion of products with active orders."""
    active_orders = await Order.objects.filter(
        product=instance,
        status__in=["pending", "processing", "shipped"],
    ).aexists()

    if active_orders:
        raise ValueError("Cannot delete product with active orders")

    return instance
```

## HookManager API

For advanced use cases, access the hook manager directly:

```python
from django_matt.views.hooks import hook_manager, HookType

# Register a hook programmatically
hook = hook_manager.register(
    hook_type=HookType.BEFORE_CREATE,
    func=my_hook_function,
    viewset_class=ProductViewSet,
    priority=0,
    condition=lambda ctx: ctx.user.is_staff,
)

# Unregister a hook
hook_manager.unregister(hook)

# Get all hooks for a type
hooks = hook_manager.get_hooks(HookType.AFTER_CREATE, ProductViewSet)

# Clear all hooks (useful in tests)
hook_manager.clear()

# Clear hooks for specific ViewSet
hook_manager.clear(ProductViewSet)
```

## Testing Hooks

```python
import pytest
from django_matt.views.hooks import hook_manager

@pytest.fixture(autouse=True)
def clear_hooks():
    """Clear hooks before each test."""
    hook_manager.clear()
    yield
    hook_manager.clear()

async def test_before_create_hook():
    """Test that before_create hook is called."""
    calls = []

    @before_create(ProductViewSet)
    async def track_hook(context, data):
        calls.append(data)
        return data

    # Create product via API
    response = await client.post("/api/products/", json={"name": "Test"})

    assert len(calls) == 1
    assert calls[0]["name"] == "Test"

async def test_hook_modifies_data():
    """Test that hook modifications are applied."""
    @before_create(ProductViewSet)
    async def add_default(context, data):
        data["status"] = "draft"
        return data

    response = await client.post("/api/products/", json={"name": "Test"})

    assert response.json()["status"] == "draft"
```

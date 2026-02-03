# View Decorators

Django-matt provides a rich set of decorators for customizing hook behavior, adding conditions, handling errors, and debugging.

## Hook Decorators

### Basic Hook Decorators

Register hooks for specific ViewSets:

```python
from django_matt.views import (
    before_list,
    after_list,
    before_create,
    after_create,
    before_read,
    after_read,
    before_update,
    after_update,
    before_delete,
    after_delete,
    on_error,
)

@before_create(ProductViewSet)
async def validate_product(context, data):
    """Called before creating a product."""
    return data

@after_create(ProductViewSet)
async def notify_creation(context, instance):
    """Called after creating a product."""
    return instance
```

### Global Hooks

Apply hooks to all ViewSets:

```python
from django_matt.views.hooks import register_global_hook

@register_global_hook("after_create")
async def audit_all_creates(context, instance):
    """Applied to all ViewSets."""
    await log_creation(context.model.__name__, instance.pk)
    return instance

# Or without arguments (applies globally)
@before_create
async def global_validation(context, data):
    return data
```

---

## `@with_hooks`

Apply multiple hooks to a ViewSet using a single decorator:

```python
from django_matt.views.decorators import with_hooks

async def validate_data(context, data):
    if not data.get("name"):
        raise ValueError("Name required")
    return data

async def log_creation(context, instance):
    logger.info(f"Created: {instance}")
    return instance

async def notify_update(context, instance):
    await send_notification(instance)
    return instance

@with_hooks(
    before_create=validate_data,
    after_create=log_creation,
    after_update=notify_update,
)
class ProductViewSet(APIViewSet):
    model = Product
    list_products = ListView()
    create_product = CreateView()
    update_product = UpdateView()
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `before_list` | `Callable` | Hook before listing |
| `after_list` | `Callable` | Hook after listing |
| `before_create` | `Callable` | Hook before creation |
| `after_create` | `Callable` | Hook after creation |
| `before_read` | `Callable` | Hook before reading |
| `after_read` | `Callable` | Hook after reading |
| `before_update` | `Callable` | Hook before update |
| `after_update` | `Callable` | Hook after update |
| `before_delete` | `Callable` | Hook before deletion |
| `after_delete` | `Callable` | Hook after deletion |
| `on_error` | `Callable` | Hook on errors |

---

## Conditional Decorators

### `@when`

Run hook only when condition is true:

```python
from django_matt.views.decorators import when
from django_matt.views import before_delete, after_create

# Only run for staff users
@when(lambda ctx: ctx.user.is_staff)
@before_delete(ProductViewSet)
async def staff_delete_audit(context, instance):
    """Only called when staff member deletes."""
    await audit_staff_action("delete", instance)
    return instance

# Only run during business hours
import datetime

def is_business_hours(ctx):
    hour = datetime.datetime.now().hour
    return 9 <= hour < 17

@when(is_business_hours)
@after_create(OrderViewSet)
async def notify_sales_team(context, order):
    """Only notify during business hours."""
    await slack_notify("#sales", f"New order: {order.id}")
    return order

# Only for premium users
@when(lambda ctx: ctx.user.subscription == "premium")
@before_create(ProductViewSet)
async def premium_only_feature(context, data):
    """Enable premium features."""
    data["premium_features"] = True
    return data
```

### `@unless`

Run hook unless condition is true (inverse of `@when`):

```python
from django_matt.views.decorators import unless

# Skip for superusers (they can do anything)
@unless(lambda ctx: ctx.user.is_superuser)
@before_delete(ProductViewSet)
async def prevent_critical_delete(context, instance):
    """Non-superusers can't delete critical items."""
    if instance.is_critical:
        raise ValueError("Cannot delete critical product")
    return instance

# Skip for automated processes
@unless(lambda ctx: getattr(ctx.request, "is_automated", False))
@after_create(OrderViewSet)
async def send_confirmation_email(context, order):
    """Don't send emails for automated orders."""
    await send_order_confirmation(order)
    return order
```

---

## Priority Control

### `@priority`

Control hook execution order (lower runs first):

```python
from django_matt.views.decorators import priority
from django_matt.views import before_create

# Runs first (priority -10)
@priority(-10)
@before_create(ProductViewSet)
async def validate_first(context, data):
    """Validation should run before other hooks."""
    if not data.get("name"):
        raise ValueError("Name required")
    return data

# Default priority (0)
@before_create(ProductViewSet)
async def add_metadata(context, data):
    """Normal priority processing."""
    data["created_at"] = datetime.now()
    return data

# Runs last (priority 10)
@priority(10)
@before_create(ProductViewSet)
async def final_check(context, data):
    """Final validation after all modifications."""
    logger.info(f"Final data: {data}")
    return data
```

---

## Hook Composition

### `@compose_hooks`

Chain multiple functions into a single hook:

```python
from django_matt.views.decorators import compose_hooks
from django_matt.views import before_create

# Individual functions
async def validate_name(context, data):
    if not data.get("name"):
        raise ValueError("Name required")
    return data

async def normalize_name(context, data):
    data["name"] = data["name"].strip().title()
    return data

async def generate_slug(context, data):
    from django.utils.text import slugify
    data["slug"] = slugify(data["name"])
    return data

async def set_defaults(context, data):
    data.setdefault("status", "draft")
    data.setdefault("is_active", True)
    return data

# Compose into single hook
@compose_hooks(validate_name, normalize_name, generate_slug, set_defaults)
@before_create(ProductViewSet)
async def prepare_product(context, data):
    """Final hook after all composition steps."""
    data["prepared"] = True
    return data
```

The composed hooks execute in order, each receiving the output of the previous.

---

## Error Handling Decorators

### `@catch_and_continue`

Continue hook chain even if an error occurs:

```python
from django_matt.views.decorators import catch_and_continue
from django_matt.views import after_create

# Don't fail if external service is down
@catch_and_continue(ConnectionError, TimeoutError, default=None)
@after_create(ProductViewSet)
async def sync_to_external(context, instance):
    """Try to sync, but don't fail the request."""
    await external_service.sync(instance)
    return instance

# Catch any exception
@catch_and_continue(Exception, default=None)
@after_create(ProductViewSet)
async def optional_enrichment(context, instance):
    """Optional data enrichment."""
    instance.metadata = await fetch_metadata(instance)
    return instance
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `*exception_types` | `type[Exception]` | Exceptions to catch (default: all) |
| `default` | `Any` | Value to return on error |

### `@retry`

Retry failed hooks with exponential backoff:

```python
from django_matt.views.decorators import retry
from django_matt.views import after_create

# Retry up to 3 times
@retry(times=3, delay=0.5)
@after_create(ProductViewSet)
async def sync_with_retry(context, instance):
    """Retry on transient failures."""
    await external_api.sync(instance)
    return instance

# Retry specific exceptions
@retry(
    times=5,
    delay=1.0,
    exceptions=(ConnectionError, TimeoutError),
)
@after_create(OrderViewSet)
async def payment_processing(context, order):
    """Retry payment with backoff."""
    await payment_gateway.process(order)
    return order
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `times` | `int` | `3` | Max retry attempts |
| `delay` | `float` | `0.1` | Base delay between retries (seconds) |
| `exceptions` | `tuple` | `(Exception,)` | Exceptions to retry on |

The delay uses exponential backoff: `delay * (attempt + 1)`

---

## Debugging Decorators

### `@log_hook`

Log hook execution for debugging:

```python
from django_matt.views.decorators import log_hook
from django_matt.views import before_create
import logging

logger = logging.getLogger(__name__)

@log_hook(logger.debug)
@before_create(ProductViewSet)
async def my_hook(context, data):
    """This hook's execution will be logged."""
    return data

# Output:
# DEBUG: Hook 'my_hook' starting for before_create
# DEBUG: Hook 'my_hook' completed in 1.23ms

# On error:
# DEBUG: Hook 'my_hook' failed after 0.45ms: ValueError: Invalid data
```

### `@timed_hook`

Track execution time and warn on slow hooks:

```python
from django_matt.views.decorators import timed_hook
from django_matt.views import after_create

def warn_slow_hook(name: str, ms: float):
    logger.warning(f"Slow hook: {name} took {ms:.2f}ms")

@timed_hook(max_ms=100, on_slow=warn_slow_hook)
@after_create(ProductViewSet)
async def potentially_slow(context, instance):
    """Warns if execution exceeds 100ms."""
    await complex_operation(instance)
    return instance

# Warnings triggered if hook takes > 100ms
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_ms` | `float` | `None` | Threshold for slow warning |
| `on_slow` | `Callable` | `None` | Callback when threshold exceeded |

---

## Method Markers

### `@hook_method`

Mark ViewSet methods as specific hook types:

```python
from django_matt.views.decorators import hook_method
from django_matt.views import APIViewSet

class ProductViewSet(APIViewSet):
    model = Product

    @hook_method("before_create")
    async def validate_and_prepare(self, request, data):
        """Custom method name, but acts as before_create."""
        if not data.get("name"):
            raise ValueError("Name required")
        data["slug"] = slugify(data["name"])
        return data

    @hook_method("after_create")
    async def post_creation_tasks(self, request, instance):
        """Custom name for after_create hook."""
        await notify_admin(instance)
        return instance
```

---

## Combining Decorators

Decorators can be combined in any order:

```python
from django_matt.views.decorators import (
    when,
    priority,
    retry,
    log_hook,
    timed_hook,
)
from django_matt.views import after_create

@log_hook(logger.info)
@timed_hook(max_ms=500, on_slow=alert_slow)
@retry(times=3, delay=1.0, exceptions=(ConnectionError,))
@priority(5)
@when(lambda ctx: ctx.user.is_premium)
@after_create(ProductViewSet)
async def premium_sync(context, instance):
    """
    Complex hook with:
    - Logging
    - Timing
    - Retries
    - Priority
    - Condition
    """
    await premium_service.sync(instance)
    return instance
```

**Decorator order matters!** Apply from bottom to top:

1. `@after_create` - Register as after_create hook
2. `@when` - Add condition check
3. `@priority` - Set execution priority
4. `@retry` - Add retry logic
5. `@timed_hook` - Add timing
6. `@log_hook` - Add logging (outermost)

---

## Complete Example

```python
from django_matt.views import APIViewSet, ListView, CreateView, UpdateView, DeleteView
from django_matt.views import before_create, after_create, before_update, after_delete
from django_matt.views.decorators import (
    with_hooks,
    when,
    unless,
    priority,
    compose_hooks,
    catch_and_continue,
    retry,
    log_hook,
)


# Validation functions
async def validate_name(context, data):
    if not data.get("name"):
        raise ValueError("Name is required")
    return data

async def normalize_data(context, data):
    data["name"] = data["name"].strip().title()
    return data

async def add_metadata(context, data):
    data["created_by_id"] = context.user.id
    data["created_at"] = datetime.now()
    return data


# Composed validation
@compose_hooks(validate_name, normalize_data, add_metadata)
@priority(-10)
@before_create(ProductViewSet)
async def prepare_product(context, data):
    return data


# Notification with retry
@retry(times=3, delay=0.5, exceptions=(ConnectionError,))
@catch_and_continue(Exception, default=None)
@after_create(ProductViewSet)
async def notify_creation(context, instance):
    await notification_service.send(
        "product_created",
        {"product_id": instance.id},
    )
    return instance


# Conditional audit logging
@when(lambda ctx: ctx.user.is_staff)
@log_hook(logger.info)
@after_create(ProductViewSet)
async def audit_staff_creation(context, instance):
    await AuditLog.objects.acreate(
        action="staff_create",
        model="Product",
        object_id=instance.id,
        user=context.user,
    )
    return instance


# Prevent deletion for non-admins
@unless(lambda ctx: ctx.user.is_superuser)
@before_delete(ProductViewSet)
async def check_delete_permission(context, instance):
    if instance.is_protected:
        raise PermissionError("Cannot delete protected product")
    return instance


# ViewSet with class decorator
@with_hooks(
    before_update=lambda ctx, inst, data: (inst, {**data, "updated_at": datetime.now()}),
    after_delete=lambda ctx, inst: cleanup_files(inst.id),
)
class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"

    list_products = ListView()
    create_product = CreateView()
    update_product = UpdateView()
    delete_product = DeleteView()
```

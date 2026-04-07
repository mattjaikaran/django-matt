# Error Handling Philosophy

django-matt uses a layered error handling system. Errors are caught at the most specific scope possible, with each layer providing a fallback for the one above it.

## Layers (Most Specific to Least Specific)

```
[1] @catch decorator          — per-endpoint
[2] Exception Filters         — per-controller or per-module
[3] ErrorHandler              — global, framework-level
[4] ErrorMiddleware           — last resort, catches everything
```

Each layer converts exceptions into a consistent JSON error envelope:

```json
{
    "status": 400,
    "detail": "Human-readable error message",
    "extra": null
}
```

## APIError Hierarchy

All framework errors extend `APIError`. Raise these from your handlers for automatic status code and error envelope generation.

```python
from django_matt.core.errors import (
    APIError,                    # base — 500
    ValidationAPIError,          # 422
    NotFoundAPIError,            # 404
    PermissionAPIError,          # 403
    AuthenticationAPIError,      # 401
    RateLimitAPIError,           # 429
    ConfigurationError,          # 500
)
```

### Raising API Errors

```python
from django_matt.core.errors import NotFoundAPIError, PermissionAPIError

async def get_order(self, request, id: int):
    try:
        order = await Order.objects.aget(pk=id)
    except Order.DoesNotExist:
        raise NotFoundAPIError(
            resource_type="Order",
            resource_id=str(id),
        )

    if order.user_id != request.user.id:
        raise PermissionAPIError(
            required_permission="order.read",
            suggestion="You can only view your own orders.",
        )

    return order
```

### Validation Errors

`ValidationAPIError` renders field-level error details in the `extra` field:

```python
raise ValidationAPIError(
    message="Invalid order data",
    errors=[
        {"field": "quantity", "msg": "Must be positive"},
        {"field": "product_id", "msg": "Product not found"},
    ],
)
```

Response:

```json
{
    "status": 422,
    "detail": "Invalid order data",
    "extra": [
        {"message": "Must be positive", "key": "quantity", "source": "body"},
        {"message": "Product not found", "key": "product_id", "source": "body"}
    ]
}
```

### Custom API Errors

Create domain-specific errors:

```python
class InsufficientStockError(APIError):
    def __init__(self, product_name: str, requested: int, available: int):
        super().__init__(
            message=f"Insufficient stock for {product_name}",
            status_code=409,
            code="insufficient_stock",
            context={
                "product": product_name,
                "requested": requested,
                "available": available,
            },
            suggestion="Reduce the quantity or check back later.",
        )
```

## ErrorHandler (Global)

The `ErrorHandler` class captures exceptions, enriches them with context (traceback, code snippets, suggestions), and produces `ErrorDetail` objects.

```python
from django_matt.core.errors import ErrorHandler

handler = ErrorHandler(debug=True)

try:
    await process_order(order_id)
except Exception as exc:
    error_detail = handler.capture_exception(exc, request)
    return error_detail.to_response()
```

In debug mode, the error response includes:
- Full traceback
- Code snippet around the error location
- Auto-generated suggestions based on exception type

In production, tracebacks and snippets are stripped for security.

### Automatic Status Code Mapping

The `ErrorHandler` maps common Python exceptions to HTTP status codes:

| Exception | Status Code |
|-----------|-------------|
| `pydantic.ValidationError` | 422 |
| `PermissionError` | 403 |
| `FileNotFoundError` | 404 |
| `json.JSONDecodeError` | 400 |
| `KeyError` | 400 |
| `NotImplementedError` | 501 |
| Everything else | 500 |

Exceptions with a `status_code` attribute use that value directly.

## Exception Filters (Scoped)

Exception filters are like middleware, but scoped to specific controllers or routes. They intercept specific exception types and return custom responses.

### Defining an Exception Filter

```python
from django_matt.exceptions import ExceptionFilter

class PaymentExceptionFilter(ExceptionFilter):
    exception_types = (PaymentError, StripeError)
    order = 10  # lower runs first

    async def catch(self, exc, request):
        if isinstance(exc, PaymentError):
            return JsonResponse(
                {"detail": "Payment failed", "code": exc.code},
                status=402,
            )
        return JsonResponse(
            {"detail": "Payment service error"},
            status=503,
        )
```

### ExceptionFilterChain

Multiple filters are composed into a chain. The chain iterates filters in `order` priority; the first filter that `can_handle()` the exception processes it:

```python
from django_matt.exceptions import ExceptionFilterChain

chain = ExceptionFilterChain([
    PaymentExceptionFilter(),
    DatabaseExceptionFilter(),
])

response = await chain.handle(exc, request)
if response is None:
    # No filter handled it — fall through to global error handler
    ...
```

### Built-in Filters

django-matt provides filters for common exception types:

| Filter | Handles |
|--------|---------|
| `ValidationExceptionFilter` | Pydantic `ValidationError` |
| `NotFoundExceptionFilter` | Django `ObjectDoesNotExist`, `Http404` |
| `PermissionExceptionFilter` | `PermissionDenied` |
| `DatabaseExceptionFilter` | `IntegrityError`, `OperationalError` |
| `ThrottleExceptionFilter` | `Throttled` |

### Global Filter Registry

Register filters globally so they apply to all routes:

```python
from django_matt.exceptions import register_global_filter

register_global_filter(PaymentExceptionFilter())
```

## @catch Decorator

The `@catch` decorator attaches exception filters to individual endpoints:

```python
from django_matt.exceptions import catch

@catch(PaymentError, handler=handle_payment_error)
async def create_order(self, request, data: OrderCreateSchema):
    ...

async def handle_payment_error(exc, request):
    return JsonResponse({"detail": str(exc)}, status=402)
```

### @catch_all

Shorthand for catching all exceptions on a handler:

```python
from django_matt.exceptions import catch_all

@catch_all(handler=handle_any_error)
async def risky_operation(self, request):
    ...
```

### @exception_filter (Class Decorator)

Decorate a class to configure it as an exception filter:

```python
from django_matt.exceptions import exception_filter

@exception_filter(PaymentError, StripeError, order=10)
class PaymentFilter:
    async def catch(self, exc, request):
        return JsonResponse({"detail": "Payment failed"}, status=402)
```

## How They Compose

Consider a request that hits a controller method decorated with `@catch`, on a controller with exception filters, with global filters registered:

```
Exception raised
    |
    v
[@catch handler on the method]
    |  (if not handled)
    v
[Controller exception filters]
    |  (if not handled)
    v
[Global exception filter registry]
    |  (if not handled)
    v
[BoundView error mapping (ValidationError->422, etc.)]
    |  (if not handled)
    v
[ErrorMiddleware — returns 500 JSON envelope]
```

This layered approach means:
- **Common errors** (validation, not-found) are handled automatically by the framework
- **Domain errors** (payment failures, stock issues) are handled by scoped filters
- **Unexpected errors** are caught by the global handler and logged with full context

## ViewSet Error Hooks

ViewSets have an `on_error` hook that runs when any exception occurs during handler execution. This is for side effects (logging, cleanup), not for producing responses:

```python
class OrderViewSet(APIViewSet):
    async def on_error(self, request, error):
        logger.error(f"Order operation failed: {error}", exc_info=True)
        await notify_ops_team(error)
```

The error still propagates through the exception filter chain after hooks run.

## Best Practices

1. **Raise `APIError` subclasses** for expected errors — they produce clean, typed responses
2. **Use exception filters** for domain-specific error handling that spans multiple endpoints
3. **Use `@catch`** for one-off error handling on a single endpoint
4. **Use the `on_error` hook** for logging and alerting, not for response generation
5. **Never swallow exceptions silently** — always log or re-raise
6. **Keep error messages user-friendly** — put technical details in `context`, not `detail`

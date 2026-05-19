# Error Handling

Django Matt provides structured error handling with automatic JSON responses.

## API Errors

### Built-in Error Classes

All error classes live in `django_matt.core.errors` and are re-exported from `django_matt.core`:

```python
from django_matt.core.errors import (
    APIError,
    NotFoundAPIError,
    ValidationAPIError,
    AuthenticationAPIError,
    PermissionAPIError,      # also aliased as PermissionDeniedAPIError
    RateLimitAPIError,
    ConfigurationError,
)

# Raise errors in your handlers
async def get_user(request, user_id: int):
    try:
        user = await User.objects.aget(id=user_id)
    except User.DoesNotExist:
        raise NotFoundAPIError(
            message=f"User {user_id} not found",
            resource_type="User",
            resource_id=str(user_id),
        )
    return {"user": user.email}
```

### APIError

Base error class. `APIController.handle_exception()` catches `APIError` and returns the appropriate JSON response:

```python
from django_matt.core.errors import APIError

raise APIError(
    message="Something went wrong",
    status_code=400,
    code="custom_error",           # machine-readable, snake_case
    context={"field": "value"},    # extra debug context
    suggestion="Check the input.", # hint for developers/LLM agents
)
```

Standard error envelope (produced by `to_response()`):

```json
{
    "status": 400,
    "detail": "Something went wrong",
    "code": "custom_error",
    "hint": "Check the input.",
    "extra": null
}
```

### NotFoundAPIError (404)

```python
from django_matt.core.errors import NotFoundAPIError

raise NotFoundAPIError("Resource not found")
raise NotFoundAPIError(
    resource_type="User",
    resource_id="42",
)
# → message becomes "User with ID '42' not found"
```

### ValidationAPIError (422)

```python
from django_matt.core.errors import ValidationAPIError

raise ValidationAPIError(
    message="Invalid input",
    errors=[
        {"field": "email", "message": "Invalid email format"},
        {"field": "password", "message": "Must be at least 8 characters"},
    ],
)
```

### AuthenticationAPIError (401)

```python
from django_matt.core.errors import AuthenticationAPIError

raise AuthenticationAPIError("Invalid credentials")
raise AuthenticationAPIError("Token expired", auth_type="JWT")
```

### PermissionAPIError (403)

```python
from django_matt.core.errors import PermissionAPIError

raise PermissionAPIError("Access denied")
raise PermissionAPIError(required_permission="products.delete")
# → message becomes "Permission denied: 'products.delete' is required"
```

`PermissionDeniedAPIError` is an alias for `PermissionAPIError`.

### RateLimitAPIError (429)

```python
from django_matt.core.errors import RateLimitAPIError

raise RateLimitAPIError(
    message="Rate limit exceeded",
    retry_after=60,
    limit=100,
    remaining=0,
)
```

### ConfigurationError (500)

Raised internally when a controller or component is misconfigured (e.g., `model` not set on `CRUDController`):

```python
from django_matt.core.errors import ConfigurationError

raise ConfigurationError("Model not specified on CRUDController")
```

## Custom Error Classes

Subclass `APIError` to create domain-specific errors:

```python
from django_matt.core.errors import APIError

class PaymentRequiredError(APIError):
    def __init__(self, message: str = "Payment required", **kwargs):
        super().__init__(
            message=message,
            status_code=402,
            code="payment_required",
            **kwargs,
        )

class ConflictError(APIError):
    def __init__(self, message: str = "Resource conflict", **kwargs):
        super().__init__(
            message=message,
            status_code=409,
            code="conflict",
            **kwargs,
        )

# Usage
raise PaymentRequiredError("Subscription expired")
raise ConflictError("Email already exists", context={"email": "user@example.com"})
```

## Error Middleware

`ErrorMiddleware` catches unhandled exceptions on `/api/` paths and returns JSON. Add it to your middleware stack:

```python
# settings.py
MIDDLEWARE = [
    "django_matt.core.errors.ErrorMiddleware",
    # ... other middleware
]
```

The middleware is async-aware (supports both WSGI and ASGI stacks). Non-API paths re-raise the exception for Django's default handling.

Extend it to customize behaviour:

```python
from django_matt.core.errors import ErrorMiddleware

class CustomErrorMiddleware(ErrorMiddleware):
    async def __acall__(self, request):
        try:
            return await self.get_response(request)
        except MyCustomError as exc:
            from django.http import JsonResponse
            return JsonResponse({"detail": str(exc)}, status=exc.status_code)
        except Exception as exc:
            return await super().__acall__.__wrapped__(self, request)
```

## Validation Errors

Pydantic `ValidationError` is caught automatically in the controller wrapper and returns 422:

```json
{
    "detail": "Validation error",
    "errors": [
        {
            "loc": ["email"],
            "msg": "value is not a valid email address",
            "type": "value_error.email"
        }
    ]
}
```

## ErrorHandler

`ErrorHandler` provides utilities for capturing exceptions with rich context (traceback, code snippet, suggestions):

```python
from django_matt.core.errors import ErrorHandler

handler = ErrorHandler(debug=True)
error_detail = handler.capture_exception(exc, request)
return error_detail.to_response(include_traceback=True, include_snippet=True)

# Class-method style (utils path)
response = ErrorHandler.json_response(exc, status_code=500)
```

## Error Logging

Configure error logging:

```python
# settings.py
LOGGING = {
    "version": 1,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django_matt": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django_matt.errors": {
            "handlers": ["console"],
            "level": "WARNING",
        },
    },
}
```

## Best Practices

1. **Use specific error classes** - Use `NotFoundAPIError` instead of generic `APIError` for 404s
2. **Include helpful details** - Add context in the `details` field
3. **Use error codes** - Consistent error codes help frontend handle errors
4. **Log appropriately** - Log 5xx errors, but not 4xx client errors
5. **Don't expose internals** - Hide stack traces and internal details in production

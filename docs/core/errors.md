# Error Handling

Django Matt provides structured error handling with automatic JSON responses.

## API Errors

### Built-in Error Classes

```python
from django_matt.core import (
    APIError,
    NotFoundAPIError,
    ValidationAPIError,
    AuthenticationAPIError,
    PermissionDeniedAPIError,
    RateLimitAPIError,
)

# Raise errors in your views
@api.get("/users/{user_id}")
async def get_user(request, user_id: int):
    try:
        user = await User.objects.aget(id=user_id)
    except User.DoesNotExist:
        raise NotFoundAPIError(f"User {user_id} not found")
    return {"user": user.email}
```

### APIError

Base error class:

```python
from django_matt.core import APIError

raise APIError(
    message="Something went wrong",
    status_code=400,
    error_code="CUSTOM_ERROR",
    details={"field": "Additional context"},
)
```

Response format:

```json
{
    "error": {
        "message": "Something went wrong",
        "code": "CUSTOM_ERROR",
        "details": {"field": "Additional context"}
    }
}
```

### NotFoundAPIError

For 404 errors:

```python
from django_matt.core import NotFoundAPIError

raise NotFoundAPIError("Resource not found")
raise NotFoundAPIError("User not found", details={"user_id": 123})
```

### ValidationAPIError

For 400 validation errors:

```python
from django_matt.core import ValidationAPIError

raise ValidationAPIError(
    "Invalid input",
    details={
        "email": ["Invalid email format"],
        "password": ["Must be at least 8 characters"],
    },
)
```

### AuthenticationAPIError

For 401 authentication errors:

```python
from django_matt.core import AuthenticationAPIError

raise AuthenticationAPIError("Invalid credentials")
raise AuthenticationAPIError("Token expired")
```

### PermissionDeniedAPIError

For 403 permission errors:

```python
from django_matt.core import PermissionDeniedAPIError

raise PermissionDeniedAPIError("You don't have permission to access this resource")
```

### RateLimitAPIError

For 429 rate limit errors:

```python
from django_matt.core import RateLimitAPIError

raise RateLimitAPIError(
    "Rate limit exceeded",
    details={"retry_after": 60},
)
```

## Custom Error Classes

Create your own error classes:

```python
from django_matt.core import APIError

class PaymentRequiredError(APIError):
    def __init__(self, message: str = "Payment required", **kwargs):
        super().__init__(
            message=message,
            status_code=402,
            error_code="PAYMENT_REQUIRED",
            **kwargs,
        )

class ConflictError(APIError):
    def __init__(self, message: str = "Resource conflict", **kwargs):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            **kwargs,
        )

# Usage
raise PaymentRequiredError("Subscription expired")
raise ConflictError("Email already exists", details={"email": "user@example.com"})
```

## Error Handler

Global error handling for your API:

```python
from django_matt import MattAPI
from django_matt.core import ErrorHandler

api = MattAPI()

# Custom error handler
@api.exception_handler(ValueError)
async def handle_value_error(request, exc):
    return ErrorHandler.create_response(
        message=str(exc),
        status_code=400,
        error_code="VALUE_ERROR",
    )

# Handle all exceptions
@api.exception_handler(Exception)
async def handle_all_exceptions(request, exc):
    # Log the error
    logger.exception("Unhandled exception")

    # Return generic error in production
    if settings.DEBUG:
        return ErrorHandler.create_response(
            message=str(exc),
            status_code=500,
            error_code="INTERNAL_ERROR",
            details={"traceback": traceback.format_exc()},
        )
    return ErrorHandler.create_response(
        message="An internal error occurred",
        status_code=500,
        error_code="INTERNAL_ERROR",
    )
```

## Error Middleware

Add error middleware for global error handling:

```python
# settings.py
MIDDLEWARE = [
    "django_matt.utils.ErrorMiddleware",
    # ... other middleware
]
```

The middleware catches all unhandled exceptions and returns JSON responses:

```python
from django_matt.utils import ErrorMiddleware

# Customizing the middleware
class CustomErrorMiddleware(ErrorMiddleware):
    def process_exception(self, request, exception):
        # Custom error processing
        if isinstance(exception, MyCustomError):
            return self.create_error_response(
                message=exception.message,
                status_code=exception.status_code,
            )
        return super().process_exception(request, exception)
```

## Validation Errors

Pydantic validation errors are automatically converted:

```python
from django_matt import Schema

class UserCreate(Schema):
    email: str
    password: str

@api.post("/users")
async def create_user(request, data: UserCreate):
    # If validation fails, automatic 422 response:
    # {
    #     "error": {
    #         "message": "Validation error",
    #         "code": "VALIDATION_ERROR",
    #         "details": [
    #             {"loc": ["body", "email"], "msg": "field required", "type": "value_error.missing"}
    #         ]
    #     }
    # }
    pass
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

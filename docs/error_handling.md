# Error Handling in Django Matt

Django Matt provides a robust error handling system that makes it easy to handle exceptions in your API controllers without writing repetitive try/except blocks.

## Automatic Error Handling in Controllers

Controllers in Django Matt come with built-in error handling that automatically catches and processes exceptions, returning appropriate HTTP responses with detailed error information.

### How It Works

1. When a controller is initialized, it wraps all route methods with error handling logic
2. If an exception occurs in a controller method, it's automatically caught
3. The exception is processed by the controller's `handle_exception` method or by the default error handler
4. A properly formatted error response is returned to the client

### Example

Here's a simple controller with automatic error handling:

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get

class MyController(APIController):
    prefix = "items/"
    
    @get("")
    async def get_items(self, request):
        # No try/except needed - errors are handled automatically
        items = await get_items_from_database()
        return {"items": items}
```

If an exception occurs in the `get_items` method, it will be automatically caught and processed, returning an appropriate error response.

### Customizing Error Handling

You can customize error handling in several ways:

#### 1. Override the `handle_exception` method

```python
from django.http import JsonResponse
from django_matt.core.controller import APIController

class MyController(APIController):
    # ...
    
    def handle_exception(self, exc, request=None):
        # Custom error handling logic
        if isinstance(exc, MyCustomError):
            return JsonResponse({"error": "Custom error message"}, status=400)
        
        # Fall back to default handling for other exceptions
        return super().handle_exception(exc, request)
```

#### 2. Disable automatic error handling

If you prefer to handle errors manually in specific controllers:

```python
class MyController(APIController):
    auto_error_handling = False  # Disable automatic error handling
    
    @get("")
    async def get_items(self, request):
        try:
            items = await get_items_from_database()
            return {"items": items}
        except Exception as e:
            # Custom error handling
            return {"error": str(e)}, 500
```

## Error Response Format

By default, error responses include:

- **Message**: A human-readable error message
- **Error Type**: The type of exception that occurred
- **Status Code**: The HTTP status code
- **Code**: A machine-readable error code
- **Context**: Additional context about the error (when available)
- **Suggestion**: A helpful suggestion for fixing the error (when available)

In development mode, error responses also include:

- **Traceback**: The full exception traceback
- **Code Snippet**: The code where the error occurred
- **File Path**: The file where the error occurred
- **Line Number**: The line number where the error occurred

## Common HTTP Status Codes

Django Matt automatically maps common exceptions to appropriate HTTP status codes:

| Exception | Status Code | Description |
|-----------|-------------|-------------|
| `ValidationError` | 422 | Validation failed |
| `PermissionError` | 403 | Permission denied |
| `FileNotFoundError` | 404 | Resource not found |
| `JSONDecodeError` | 400 | Invalid JSON |
| `KeyError` | 400 | Missing key |
| `AttributeError` | 400 | Missing attribute |
| `NotImplementedError` | 501 | Not implemented |
| `DoesNotExist` | 404 | Resource not found |
| Other exceptions | 500 | Internal server error |

## Custom API Exceptions

Django Matt provides several custom exception classes that you can raise in your controllers:

### APIError

Base class for API errors:

```python
from django_matt.core.errors import APIError

def my_view(request):
    if not authorized:
        raise APIError(
            message="You are not authorized to perform this action",
            status_code=403,
            code="unauthorized",
            context={"required_role": "admin"}
        )
```

### NotFoundAPIError

For "not found" errors:

```python
from django_matt.core.errors import NotFoundAPIError

def get_item(request, id):
    item = find_item(id)
    if not item:
        raise NotFoundAPIError(
            resource_type="Item",
            resource_id=id
        )
    return item
```

### ValidationAPIError

For validation errors:

```python
from django_matt.core.errors import ValidationAPIError

def create_item(request, data):
    if not is_valid(data):
        raise ValidationAPIError(
            errors=[
                {"field": "name", "message": "Name is required"}
            ]
        )
    # Create the item
```

### PermissionAPIError

For permission errors:

```python
from django_matt.core.errors import PermissionAPIError

def update_item(request, id):
    if not has_permission(request.user, "edit_item"):
        raise PermissionAPIError(
            required_permission="edit_item"
        )
    # Update the item
```

## Error Middleware

Django Matt also provides an error middleware that catches exceptions at the middleware level:

```python
# In your settings.py
MIDDLEWARE = [
    # ...
    "django_matt.core.errors.ErrorMiddleware",
    # ...
]
```

This middleware catches any uncaught exceptions and returns properly formatted error responses.

## Best Practices

1. **Let the automatic error handling do its job**: In most cases, you don't need to write try/except blocks in your controller methods.

2. **Use custom API exceptions**: Raise appropriate custom exceptions like `NotFoundAPIError` instead of returning error responses manually.

3. **Add context to errors**: When raising exceptions, include relevant context to help debug the issue.

4. **Override `handle_exception` for custom logic**: If you need custom error handling, override the `handle_exception` method in your controller.

5. **Disable automatic error handling selectively**: If you need full control over error handling in a specific controller, set `auto_error_handling = False`.

## Conclusion

Django Matt's automatic error handling system allows you to focus on your business logic without writing repetitive try/except blocks. The system provides detailed error information in development and clean, user-friendly error messages in production. 
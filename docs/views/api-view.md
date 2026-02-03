# Base APIView

The `APIView` class is the foundation for all view operations in django-matt. It provides core functionality for request handling, serialization, and lifecycle hook integration.

## Overview

```python
from django_matt.views import APIView
from pydantic import BaseModel

class APIView(Generic[ModelT, SchemaT]):
    """Base class for composable API views."""

    path: str = ""
    methods: list[str] = ["GET"]
    response_schema: type[BaseModel] | None = None
    request_schema: type[BaseModel] | None = None
    enable_hooks: bool = True
```

## Class Attributes

### URL and HTTP Configuration

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | `""` | URL path suffix for this view |
| `methods` | `list[str]` | `["GET"]` | HTTP methods this view responds to |

### Schema Configuration

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `response_schema` | `type[BaseModel]` | `None` | Pydantic schema for response serialization |
| `request_schema` | `type[BaseModel]` | `None` | Pydantic schema for request validation |

### OpenAPI Documentation

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `summary` | `str` | Auto-generated | OpenAPI summary |
| `description` | `str` | `None` | OpenAPI description |
| `tags` | `list[str]` | From ViewSet | OpenAPI tags |
| `operation_id` | `str` | From attribute name | OpenAPI operation ID |

### Hooks

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_hooks` | `bool` | `True` | Whether to enable lifecycle hooks |

## Constructor

```python
def __init__(
    self,
    path: str | None = None,
    response_schema: type[BaseModel] | None = None,
    request_schema: type[BaseModel] | None = None,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    operation_id: str | None = None,
    enable_hooks: bool | None = None,
    **kwargs,
):
```

All parameters override the class defaults when provided.

## Key Methods

### `handle(request, **kwargs)`

The main request handler. **Must be implemented by subclasses.**

```python
async def handle(self, request: HttpRequest, **kwargs) -> Any:
    """
    Handle the request.

    Args:
        request: The HTTP request
        **kwargs: URL path parameters

    Returns:
        Response data (will be serialized to JSON)
    """
    raise NotImplementedError("Subclasses must implement handle()")
```

### `get_queryset(request)`

Get the base queryset for the view.

```python
def get_queryset(self, request: HttpRequest) -> QuerySet:
    """
    Get the base queryset for this view.

    Override in subclasses to customize filtering.
    """
    if self._viewset is None:
        raise ValueError("View not attached to a ViewSet")

    if hasattr(self._viewset, "get_queryset"):
        return self._viewset.get_queryset(request)

    return self._viewset.model.objects.all()
```

### `serialize(instance)`

Serialize a model instance using the response schema.

```python
def serialize(self, instance: Model) -> dict[str, Any]:
    """
    Serialize a model instance to a dictionary.

    Uses the response schema if available.
    """
    schema = self.get_response_schema()
    if schema is not None:
        return schema.model_validate(instance, from_attributes=True).model_dump()
    return self._model_to_dict(instance)
```

### `validate_request(request)`

Validate the request body against the request schema.

```python
def validate_request(self, request: HttpRequest) -> BaseModel | None:
    """
    Validate request body against the request schema.

    Returns:
        Validated Pydantic model instance, or None if no schema

    Raises:
        ValidationError: If validation fails
    """
```

## Descriptor Protocol

`APIView` implements Python's descriptor protocol, allowing views to be defined as class attributes on ViewSets:

```python
class ProductViewSet(APIViewSet):
    model = Product

    # View defined as class attribute
    list_products = ListView(page_size=20)

    # Accessed on instance, returns BoundView
    # viewset.list_products  -> BoundView(ListView, viewset)
```

### `__set_name__(owner, name)`

Called when the view is assigned to a ViewSet class attribute:

```python
def __set_name__(self, owner: type, name: str):
    """Called when view is assigned to a ViewSet class attribute."""
    self._viewset_attr_name = name
```

### `__get__(obj, objtype)`

Returns a bound view when accessed on an instance:

```python
def __get__(self, obj, objtype=None):
    """Return bound view when accessed on instance."""
    if obj is None:
        return self
    return BoundView(self, obj)
```

## BoundView

When a view is accessed on a ViewSet instance, a `BoundView` is returned that handles:

- Request execution
- Error handling
- Response formatting
- Hook error callbacks

```python
class BoundView:
    """A view bound to a specific ViewSet instance."""

    def __init__(self, view: APIView, viewset: ViewSet):
        self.view = view
        self.viewset = viewset
        view._viewset = viewset

    async def __call__(self, request: HttpRequest, **kwargs) -> JsonResponse:
        """Handle the request and return a JSON response."""
        try:
            result = await self.view.handle(request, **kwargs)
            return JsonResponse(result, safe=False)

        except ValidationError as e:
            await self.view._handle_error(request, e)
            return JsonResponse(
                {"detail": "Validation error", "errors": e.errors()},
                status=422,
            )
        except NotFoundAPIError as e:
            await self.view._handle_error(request, e)
            return JsonResponse(
                {"detail": str(e), "code": "not_found"},
                status=404,
            )
        # ... other error handling
```

## Hook Integration

APIView provides methods for executing lifecycle hooks:

### `_create_hook_context(...)`

Create a `HookContext` for hook execution:

```python
def _create_hook_context(
    self,
    request: HttpRequest,
    hook_type: HookType | None = None,
    instance: Model | None = None,
    data: dict | BaseModel | None = None,
    queryset: QuerySet | None = None,
    **extra,
) -> HookContext:
```

### `_run_hooks(...)`

Execute hooks of a given type:

```python
async def _run_hooks(
    self,
    hook_type: HookType | str,
    request: HttpRequest,
    value: Any = None,
    instance: Model | None = None,
    data: dict | BaseModel | None = None,
    queryset: QuerySet | None = None,
    **extra,
) -> Any:
    """
    Execute hooks for this view.

    Returns:
        The transformed value after hooks execute
    """
```

### `_handle_error(...)`

Execute error hooks when an exception occurs:

```python
async def _handle_error(
    self,
    request: HttpRequest,
    error: Exception,
    instance: Model | None = None,
) -> None:
    """Execute error hooks when an exception occurs."""
```

## Creating Custom Views

Subclass `APIView` to create custom view types:

```python
from django_matt.views import APIView
from django_matt.views.hooks import HookType


class BulkCreateView(APIView):
    """View for creating multiple resources at once."""

    path = "bulk"
    methods = ["POST"]

    async def handle(self, request: HttpRequest, **kwargs) -> dict:
        # Validate request
        data = self.validate_request(request)
        if data is None:
            raise ValueError("Request body is required")

        items = data.items  # Assuming schema has 'items' field
        created = []

        for item_data in items:
            item_dict = item_data.model_dump()

            # Run before_create hooks for each item
            item_dict = await self._run_hooks(
                HookType.BEFORE_CREATE,
                request,
                value=item_dict,
                data=item_dict,
            )

            # Create instance
            instance = self.get_model()(**item_dict)
            await instance.asave()

            # Run after_create hooks
            instance = await self._run_hooks(
                HookType.AFTER_CREATE,
                request,
                value=instance,
                instance=instance,
            )

            created.append(self.serialize(instance))

        return {"created": len(created), "items": created}


# Usage
class ProductViewSet(APIViewSet):
    model = Product

    bulk_create = BulkCreateView(request_schema=BulkProductCreate)
```

## OpenAPI Schema Generation

Views automatically generate OpenAPI documentation:

```python
def get_route_info(self) -> dict[str, Any]:
    """Get route information for OpenAPI schema generation."""
    return {
        "path": self.path,
        "methods": self.methods,
        "response_schema": self.get_response_schema(),
        "request_schema": self.get_request_schema(),
        "summary": self.summary or self._generate_summary(),
        "description": self.description,
        "tags": self.tags or (self._viewset.tags if self._viewset else None),
        "operation_id": self.operation_id or self._generate_operation_id(),
    }
```

Auto-generated summaries based on view type:

- `ListView` -> "List {Model}s"
- `CreateView` -> "Create {Model}"
- `ReadView` -> "Get {Model}"
- `UpdateView` -> "Update {Model}"
- `DeleteView` -> "Delete {Model}"

## Best Practices

### 1. Use Schemas for Validation

Always define request schemas for write operations:

```python
list_products = ListView(response_schema=ProductList)
create_product = CreateView(
    request_schema=ProductCreate,
    response_schema=ProductDetail,
)
```

### 2. Keep Handlers Focused

Each view should handle one type of operation:

```python
# Good: Separate views for different operations
list_products = ListView()
list_featured = ListView(path="featured")

# Avoid: Complex conditional logic in one view
```

### 3. Use Hooks for Cross-Cutting Concerns

Instead of overriding `handle()`, use hooks:

```python
# Good: Use hooks
async def before_create(self, request, data):
    data["created_by_id"] = request.user.id
    return data

# Avoid: Override handle() for simple modifications
```

### 4. Handle Errors Gracefully

The `BoundView` handles common errors, but you can add custom error handling:

```python
async def handle(self, request, **kwargs):
    try:
        # Your logic
        pass
    except CustomError as e:
        raise APIError(str(e), status_code=400)
```

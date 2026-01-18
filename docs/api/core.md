# Core API Reference

The core module provides the fundamental building blocks for Django Matt applications.

## Controllers

Controllers are class-based API handlers that group related endpoints together.

### APIController

::: django_matt.core.controller.APIController
    options:
      show_source: false
      members:
        - __init__
        - get_queryset
        - get_object
        - get_serializer
      heading_level: 4

### CRUDController

A controller with built-in async CRUD operations and query optimization.

::: django_matt.core.controller.CRUDController
    options:
      show_source: false
      heading_level: 4

### Controller

Base controller class (alias for APIController).

::: django_matt.core.controller.Controller
    options:
      show_source: false
      heading_level: 4

---

## Schemas

Pydantic-based schemas for request/response serialization.

### ModelSchema

::: django_matt.core.schema.ModelSchema
    options:
      show_source: false
      heading_level: 4

### Schema

::: django_matt.core.schema.Schema
    options:
      show_source: false
      heading_level: 4

### Schema Functions

#### create_schema_from_model

::: django_matt.core.schema.create_schema_from_model
    options:
      show_source: false
      heading_level: 5

#### create_model_from_schema

::: django_matt.core.schema.create_model_from_schema
    options:
      show_source: false
      heading_level: 5

#### model_validator

::: django_matt.core.schema.model_validator
    options:
      show_source: false
      heading_level: 5

---

## Errors

API error classes for structured error responses.

### APIError

Base exception for all API errors.

::: django_matt.core.errors.APIError
    options:
      show_source: false
      heading_level: 4

### NotFoundAPIError

::: django_matt.core.errors.NotFoundAPIError
    options:
      show_source: false
      heading_level: 4

### ValidationAPIError

::: django_matt.core.errors.ValidationAPIError
    options:
      show_source: false
      heading_level: 4

### AuthenticationAPIError

::: django_matt.core.errors.AuthenticationAPIError
    options:
      show_source: false
      heading_level: 4

### PermissionDeniedAPIError

::: django_matt.core.errors.PermissionDeniedAPIError
    options:
      show_source: false
      heading_level: 4

### RateLimitAPIError

::: django_matt.core.errors.RateLimitAPIError
    options:
      show_source: false
      heading_level: 4

### ErrorHandler

::: django_matt.core.errors.ErrorHandler
    options:
      show_source: false
      heading_level: 4

---

## Version Detection

Django Matt automatically detects the Django version for feature compatibility.

```python
from django_matt.core import DJANGO_VERSION, DJANGO_5_2_PLUS, DJANGO_6_0_PLUS

if DJANGO_5_2_PLUS:
    # Use Django 5.2+ features like connection pooling
    pass

if DJANGO_6_0_PLUS:
    # Use Django 6.0+ features
    pass
```

### Constants

| Constant | Type | Description |
|----------|------|-------------|
| `DJANGO_VERSION` | `tuple[int, int]` | Current Django version as tuple, e.g., `(5, 2)` |
| `DJANGO_5_2_PLUS` | `bool` | `True` if Django >= 5.2 |
| `DJANGO_6_0_PLUS` | `bool` | `True` if Django >= 6.0 |

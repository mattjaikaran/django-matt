"""
Django Matt Core Module.

Provides the core building blocks for the Django Matt framework:
- Controllers for class-based API endpoints
- Schemas for Pydantic-based model serialization
- Routing decorators for HTTP method handling
- Error handling utilities
"""

from django_matt.compat import DJANGO_5_2_PLUS, DJANGO_6_0_PLUS, DJANGO_VERSION
from django_matt.core.controller import (
    APIController,
    Controller,
    CRUDController,
)
from django_matt.core.errors import (
    APIError,
    AuthenticationAPIError,
    ErrorHandler,
    NotFoundAPIError,
    PermissionDeniedAPIError,
    RateLimitAPIError,
    ValidationAPIError,
)
from django_matt.core.schema import (
    ModelSchema,
    Schema,
    create_model_from_schema,
    create_schema_from_model,
    get_custom_openapi_schemas,
    model_validator,
    register_field_type,
    unregister_field_type,
)

__all__ = [
    # Controllers
    "Controller",
    "APIController",
    "CRUDController",
    # Schemas
    "ModelSchema",
    "Schema",
    "create_schema_from_model",
    "create_model_from_schema",
    "model_validator",
    "register_field_type",
    "unregister_field_type",
    "get_custom_openapi_schemas",
    # Errors
    "APIError",
    "NotFoundAPIError",
    "ValidationAPIError",
    "AuthenticationAPIError",
    "PermissionDeniedAPIError",
    "RateLimitAPIError",
    "ErrorHandler",
    # Version detection
    "DJANGO_VERSION",
    "DJANGO_5_2_PLUS",
    "DJANGO_6_0_PLUS",
]

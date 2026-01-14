"""
Django Matt OpenAPI module.

Provides automatic OpenAPI schema generation and interactive API documentation.
"""

from django_matt.openapi.schema import OpenAPISchema
from django_matt.openapi.docs import get_swagger_ui, get_redoc

__all__ = [
    "OpenAPISchema",
    "get_swagger_ui",
    "get_redoc",
]

"""
Django Matt OpenAPI module.

Provides automatic OpenAPI schema generation and interactive API documentation.
"""

from django_matt.openapi.docs import get_redoc, get_swagger_ui
from django_matt.openapi.schema import OpenAPISchema

__all__ = [
    "OpenAPISchema",
    "get_redoc",
    "get_swagger_ui",
]

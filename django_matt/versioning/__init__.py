"""
API versioning for django-matt.

Provides multiple versioning schemes for API endpoints:
- URLPathVersioning: Version in URL path (/api/v1/, /api/v2/)
- HeaderVersioning: Version in Accept header
- QueryParameterVersioning: Version in query string (?version=1)

Example usage:
    from django_matt.versioning import version, URLPathVersioning

    @api.get("/users")
    @version("1.0", "2.0")
    def get_users(request):
        if request.version == "2.0":
            return {"users": [...], "meta": {...}}
        return {"users": [...]}

    # Or with versioned router
    from django_matt.versioning import VersionedRouter

    v1 = VersionedRouter(version="1")
    v2 = VersionedRouter(version="2")

    @v1.get("/users")
    def get_users_v1(request):
        return {"users": [...]}

    @v2.get("/users")
    def get_users_v2(request):
        return {"users": [...], "meta": {...}}

    api.include_router(v1, prefix="/v1")
    api.include_router(v2, prefix="/v2")
"""

from django_matt.versioning.base import BaseVersioning
from django_matt.versioning.decorators import (
    deprecated,
    max_version,
    min_version,
    version,
)
from django_matt.versioning.middleware import VersioningMiddleware
from django_matt.versioning.router import VersionedRouter
from django_matt.versioning.schemes import (
    AcceptHeaderVersioning,
    HeaderVersioning,
    HostNameVersioning,
    QueryParameterVersioning,
    URLPathVersioning,
)

__all__ = [
    # Base
    "BaseVersioning",
    # Versioning schemes
    "URLPathVersioning",
    "HeaderVersioning",
    "AcceptHeaderVersioning",
    "QueryParameterVersioning",
    "HostNameVersioning",
    # Decorators
    "version",
    "deprecated",
    "min_version",
    "max_version",
    # Middleware
    "VersioningMiddleware",
    # Router
    "VersionedRouter",
]

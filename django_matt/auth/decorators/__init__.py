"""
Authentication decorators for Django Matt.

Provides decorators for protecting controller methods and views
with JWT authentication and permissions.
"""

from django_matt.auth.decorators.jwt import (
    jwt_optional,
    jwt_required,
    requires_auth,
)
from django_matt.auth.decorators.roles import (
    admin_required,
    superuser_required,
    with_permission,
    with_roles,
)

__all__ = [
    # JWT
    "jwt_required",
    "jwt_optional",
    "requires_auth",
    # Role-based
    "admin_required",
    "superuser_required",
    "with_roles",
    "with_permission",
]

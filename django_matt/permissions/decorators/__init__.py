"""
Permission decorators for Django Matt.

Provides decorators for applying permissions to controller methods and views.
"""

from django_matt.permissions.decorators.base import (
    check_permissions,
    get_request,
    create_permission_decorator,
)
from django_matt.permissions.decorators.permission import (
    requires_permission,
    requires_permissions,
    with_permissions,
)
from django_matt.permissions.decorators.role import requires_role
from django_matt.permissions.decorators.auth import authenticated, allow_any

__all__ = [
    # Base utilities
    "check_permissions",
    "get_request",
    "create_permission_decorator",
    # Permission decorators
    "requires_permission",
    "requires_permissions",
    "with_permissions",
    # Role decorators
    "requires_role",
    # Auth decorators
    "authenticated",
    "allow_any",
]

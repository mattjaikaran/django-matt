"""
Django Matt Permissions - Permission classes and decorators.

Provides a flexible permission system inspired by django-ninja-extra.
Supports class-based permissions, decorators, and integration with ViewSets.

Example:
    from django_matt.permissions import IsAuthenticated, requires_permission

    class TaskController(APIController):
        permission_classes = [IsAuthenticated]

        @get("")
        async def list_tasks(self, request):
            return await self.list(request)

        @delete("{id}")
        @requires_permission("tasks.delete")
        async def delete_task(self, request, id: str):
            return await self.delete(request, id)
"""

from django_matt.permissions.base import (
    BasePermission,
    OperationPermission,
    Permission,
    PermissionDenied,
)
from django_matt.permissions.common import (
    AllowAny,
    HasPermission,
    HasRole,
    IsAdmin,
    IsAdminOrReadOnly,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    IsOwner,
    IsStaff,
    IsSuperUser,
)
from django_matt.permissions.decorators import (
    allow_any,
    authenticated,
    check_permissions,
    requires_permission,
    requires_permissions,
    requires_role,
    with_permissions,
)

__all__ = [
    # Base classes
    "BasePermission",
    "Permission",
    "OperationPermission",
    "PermissionDenied",
    # Common permissions
    "AllowAny",
    "IsAuthenticated",
    "IsAdmin",
    "IsStaff",
    "IsSuperUser",
    "IsOwner",
    "HasRole",
    "HasPermission",
    "IsAuthenticatedOrReadOnly",
    "IsAdminOrReadOnly",
    # Decorators
    "requires_permission",
    "requires_permissions",
    "requires_role",
    "authenticated",
    "allow_any",
    "with_permissions",
    "check_permissions",
]

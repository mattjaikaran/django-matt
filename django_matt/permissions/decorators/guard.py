"""
Method-level permission override decorator for controllers.

The @guard() decorator sets permission classes on individual controller methods,
overriding the controller-level permission_classes for that endpoint only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from django_matt.permissions.base import BasePermission

F = TypeVar("F", bound=Callable[..., Any])


def guard(*permission_classes: type[BasePermission] | BasePermission) -> Callable[[F], F]:
    """
    Override controller-level permissions for a single method.

    When applied to a controller method, the method will use the given
    permission classes INSTEAD OF the controller's ``permission_classes``.

    Accepts permission classes (types) or pre-instantiated permission objects.

    Args:
        *permission_classes: One or more permission classes or instances.

    Example::

        class UserController(Controller):
            permission_classes = [IsAuthenticated]

            @guard(AllowAny)
            @route_get("/public")
            async def public_endpoint(self, request):
                ...

            @guard(IsAdmin)
            @route_post("/admin-action")
            async def admin_action(self, request):
                ...
    """

    def decorator(func: F) -> F:
        func._guard_permissions = list(permission_classes)  # type: ignore[attr-defined]
        return func

    return decorator

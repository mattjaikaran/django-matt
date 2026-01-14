"""
Permission-based decorators for Django permissions.
"""

from typing import Any, Callable, TypeVar

from django_matt.permissions.common import HasPermission
from django_matt.permissions.base import BasePermission
from django_matt.permissions.decorators.base import create_permission_decorator


F = TypeVar("F", bound=Callable[..., Any])


def requires_permission(*permissions: str) -> Callable[[F], F]:
    """
    Decorator that requires specific Django permissions.
    
    Uses Django's built-in permission system to check if the user
    has the required permissions.
    
    Example:
        class TaskController(APIController):
            @delete("{id}")
            @requires_permission("tasks.delete_task")
            async def delete_task(self, request, id: str):
                return await self.delete(request, id)
            
            @post("")
            @requires_permission("tasks.add_task", "tasks.change_task")
            async def create_task(self, request, data: TaskCreate):
                return await self.create(request, data)
    
    Args:
        *permissions: Permission strings (user must have at least one)
    """
    perm_instance = HasPermission(permissions=list(permissions))
    return create_permission_decorator([perm_instance], "permission_denied")


def requires_permissions(
    *permissions: str, require_all: bool = True
) -> Callable[[F], F]:
    """
    Decorator that requires multiple Django permissions.
    
    Similar to requires_permission but with control over whether
    all permissions are required or just one.
    
    Example:
        @requires_permissions("tasks.view", "tasks.change", require_all=True)
        async def sensitive_action(self, request):
            ...
    
    Args:
        *permissions: Permission strings
        require_all: If True, user must have all permissions.
                    If False, user needs any one.
    """
    perm_instance = HasPermission(permissions=list(permissions), require_all=require_all)
    return create_permission_decorator([perm_instance], "permission_denied")


def with_permissions(*permission_classes: type[BasePermission]) -> Callable[[F], F]:
    """
    Decorator that applies multiple permission classes.
    
    All permissions must pass for access to be granted.
    
    Example:
        @with_permissions(IsAuthenticated, IsProjectMember)
        async def project_action(self, request):
            ...
    
    Args:
        *permission_classes: Permission classes (not instances)
    """
    instances = [cls() for cls in permission_classes]
    return create_permission_decorator(instances, "permission_denied")

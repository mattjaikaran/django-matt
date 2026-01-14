"""
RBAC decorators for role hierarchy and permission checks.
"""

import inspect
from functools import wraps
from typing import Any, Callable, TypeVar

from django.http import HttpRequest, JsonResponse

from django_matt.auth.rbac.config import rbac_config
from django_matt.auth.rbac.utils import get_user_roles, user_has_permission


F = TypeVar("F", bound=Callable[..., Any])


def requires_role_hierarchy(
    min_role: str,
    message: str = "Insufficient role level.",
) -> Callable[[F], F]:
    """
    Decorator that requires a minimum role level in the hierarchy.
    
    User must have a role with priority >= the specified role's priority.
    
    Example:
        @requires_role_hierarchy("manager")
        async def approve_request(self, request):
            # Only managers, admins, and superadmins can access
            ...
    
    Args:
        min_role: Minimum role required
        message: Error message if denied
    """
    min_priority = rbac_config.get_role_priority(min_role)
    
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            request = _get_request(self_or_request, args, kwargs)
            
            user = getattr(request, "user", None)
            if user is None or not user.is_authenticated:
                return JsonResponse(
                    {"detail": "Authentication required", "code": "unauthenticated"},
                    status=401,
                )
            
            user_roles = get_user_roles(user)
            highest_priority = max(
                (rbac_config.get_role_priority(r) for r in user_roles),
                default=0,
            )
            
            if highest_priority < min_priority:
                return JsonResponse(
                    {"detail": message, "code": "insufficient_role"},
                    status=403,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            request = _get_request(self_or_request, args, kwargs)
            
            user = getattr(request, "user", None)
            if user is None or not user.is_authenticated:
                return JsonResponse(
                    {"detail": "Authentication required", "code": "unauthenticated"},
                    status=401,
                )
            
            user_roles = get_user_roles(user)
            highest_priority = max(
                (rbac_config.get_role_priority(r) for r in user_roles),
                default=0,
            )
            
            if highest_priority < min_priority:
                return JsonResponse(
                    {"detail": message, "code": "insufficient_role"},
                    status=403,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


def requires_rbac_permission(
    permission: str,
    resource: str | None = None,
    message: str = "Permission denied.",
) -> Callable[[F], F]:
    """
    Decorator that checks RBAC permission.
    
    Uses the RBAC system with role hierarchy and permission inheritance.
    
    Example:
        @requires_rbac_permission("delete", resource="tasks")
        async def delete_task(self, request, id: str):
            ...
    
    Args:
        permission: Permission to check
        resource: Optional resource scope
        message: Error message if denied
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            request = _get_request(self_or_request, args, kwargs)
            user = getattr(request, "user", None)
            
            if not user_has_permission(user, permission, resource):
                status = 401 if (user is None or not user.is_authenticated) else 403
                code = "unauthenticated" if status == 401 else "permission_denied"
                return JsonResponse(
                    {"detail": message, "code": code},
                    status=status,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            request = _get_request(self_or_request, args, kwargs)
            user = getattr(request, "user", None)
            
            if not user_has_permission(user, permission, resource):
                status = 401 if (user is None or not user.is_authenticated) else 403
                code = "unauthenticated" if status == 401 else "permission_denied"
                return JsonResponse(
                    {"detail": message, "code": code},
                    status=status,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


def _get_request(self_or_request, args, kwargs) -> HttpRequest | None:
    """Extract request from various call patterns."""
    if hasattr(self_or_request, "request"):
        return self_or_request.request
    elif isinstance(self_or_request, HttpRequest):
        return self_or_request
    elif args and isinstance(args[0], HttpRequest):
        return args[0]
    return kwargs.get("request")

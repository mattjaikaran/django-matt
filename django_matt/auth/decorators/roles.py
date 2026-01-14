"""
Role and permission-based decorators.
"""

import inspect
from functools import wraps
from typing import Any, Callable, TypeVar

from django.http import JsonResponse

from django_matt.auth.decorators.base import get_request


F = TypeVar("F", bound=Callable[..., Any])


def admin_required(func: F) -> F:
    """
    Decorator that requires admin (staff or superuser).
    
    Example:
        @delete("{id}")
        @admin_required
        async def delete_resource(self, request, id: str):
            ...
    """
    @wraps(func)
    async def async_wrapper(self_or_request, *args, **kwargs):
        request = get_request(self_or_request, args, kwargs)
        
        if request is None:
            return JsonResponse(
                {"detail": "Request not found", "code": "internal_error"},
                status=500,
            )
        
        user = getattr(request, "user", None)
        
        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required", "code": "unauthenticated"},
                status=401,
            )
        
        if not (user.is_staff or user.is_superuser):
            return JsonResponse(
                {"detail": "Admin access required", "code": "admin_required"},
                status=403,
            )
        
        if inspect.iscoroutinefunction(func):
            return await func(self_or_request, *args, **kwargs)
        return func(self_or_request, *args, **kwargs)
    
    @wraps(func)
    def sync_wrapper(self_or_request, *args, **kwargs):
        request = get_request(self_or_request, args, kwargs)
        
        if request is None:
            return JsonResponse(
                {"detail": "Request not found", "code": "internal_error"},
                status=500,
            )
        
        user = getattr(request, "user", None)
        
        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required", "code": "unauthenticated"},
                status=401,
            )
        
        if not (user.is_staff or user.is_superuser):
            return JsonResponse(
                {"detail": "Admin access required", "code": "admin_required"},
                status=403,
            )
        
        return func(self_or_request, *args, **kwargs)
    
    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore


def superuser_required(func: F) -> F:
    """
    Decorator that requires superuser status.
    
    Example:
        @post("dangerous-action")
        @superuser_required
        async def dangerous_action(self, request):
            ...
    """
    @wraps(func)
    async def async_wrapper(self_or_request, *args, **kwargs):
        request = get_request(self_or_request, args, kwargs)
        
        if request is None:
            return JsonResponse(
                {"detail": "Request not found", "code": "internal_error"},
                status=500,
            )
        
        user = getattr(request, "user", None)
        
        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required", "code": "unauthenticated"},
                status=401,
            )
        
        if not user.is_superuser:
            return JsonResponse(
                {"detail": "Superuser access required", "code": "superuser_required"},
                status=403,
            )
        
        if inspect.iscoroutinefunction(func):
            return await func(self_or_request, *args, **kwargs)
        return func(self_or_request, *args, **kwargs)
    
    @wraps(func)
    def sync_wrapper(self_or_request, *args, **kwargs):
        request = get_request(self_or_request, args, kwargs)
        
        if request is None:
            return JsonResponse(
                {"detail": "Request not found", "code": "internal_error"},
                status=500,
            )
        
        user = getattr(request, "user", None)
        
        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required", "code": "unauthenticated"},
                status=401,
            )
        
        if not user.is_superuser:
            return JsonResponse(
                {"detail": "Superuser access required", "code": "superuser_required"},
                status=403,
            )
        
        return func(self_or_request, *args, **kwargs)
    
    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore


def with_roles(*roles: str, require_all: bool = False) -> Callable[[F], F]:
    """
    Decorator that requires specific role(s) from the RBAC system.
    
    Example:
        @post("approve")
        @with_roles("manager", "admin")  # Either role works
        async def approve(self, request):
            ...
        
        @post("sensitive")
        @with_roles("manager", "compliance", require_all=True)  # Need both
        async def sensitive_action(self, request):
            ...
    
    Args:
        *roles: Required role names
        require_all: If True, user must have all roles
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            from django_matt.auth.rbac import get_user_roles
            
            request = get_request(self_or_request, args, kwargs)
            
            if request is None:
                return JsonResponse(
                    {"detail": "Request not found", "code": "internal_error"},
                    status=500,
                )
            
            user = getattr(request, "user", None)
            
            if user is None or not user.is_authenticated:
                return JsonResponse(
                    {"detail": "Authentication required", "code": "unauthenticated"},
                    status=401,
                )
            
            user_roles = set(get_user_roles(user))
            required_roles = set(roles)
            
            if require_all:
                has_roles = required_roles.issubset(user_roles)
            else:
                has_roles = bool(user_roles & required_roles)
            
            if not has_roles:
                return JsonResponse(
                    {
                        "detail": f"Required role(s): {', '.join(roles)}",
                        "code": "role_required",
                    },
                    status=403,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            from django_matt.auth.rbac import get_user_roles
            
            request = get_request(self_or_request, args, kwargs)
            
            if request is None:
                return JsonResponse(
                    {"detail": "Request not found", "code": "internal_error"},
                    status=500,
                )
            
            user = getattr(request, "user", None)
            
            if user is None or not user.is_authenticated:
                return JsonResponse(
                    {"detail": "Authentication required", "code": "unauthenticated"},
                    status=401,
                )
            
            user_roles = set(get_user_roles(user))
            required_roles = set(roles)
            
            if require_all:
                has_roles = required_roles.issubset(user_roles)
            else:
                has_roles = bool(user_roles & required_roles)
            
            if not has_roles:
                return JsonResponse(
                    {
                        "detail": f"Required role(s): {', '.join(roles)}",
                        "code": "role_required",
                    },
                    status=403,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


def with_permission(
    permission: str,
    resource: str | None = None,
) -> Callable[[F], F]:
    """
    Decorator that requires a specific RBAC permission.
    
    Example:
        @delete("{id}")
        @with_permission("delete", resource="tasks")
        async def delete_task(self, request, id: str):
            ...
    
    Args:
        permission: Permission name (e.g., "delete", "create")
        resource: Optional resource scope (e.g., "tasks", "users")
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            from django_matt.auth.rbac import user_has_permission
            
            request = get_request(self_or_request, args, kwargs)
            
            if request is None:
                return JsonResponse(
                    {"detail": "Request not found", "code": "internal_error"},
                    status=500,
                )
            
            user = getattr(request, "user", None)
            
            if not user_has_permission(user, permission, resource):
                status = 401 if (user is None or not user.is_authenticated) else 403
                code = "unauthenticated" if status == 401 else "permission_denied"
                detail = "Authentication required" if status == 401 else f"Permission '{permission}' required"
                return JsonResponse(
                    {"detail": detail, "code": code},
                    status=status,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            from django_matt.auth.rbac import user_has_permission
            
            request = get_request(self_or_request, args, kwargs)
            
            if request is None:
                return JsonResponse(
                    {"detail": "Request not found", "code": "internal_error"},
                    status=500,
                )
            
            user = getattr(request, "user", None)
            
            if not user_has_permission(user, permission, resource):
                status = 401 if (user is None or not user.is_authenticated) else 403
                code = "unauthenticated" if status == 401 else "permission_denied"
                detail = "Authentication required" if status == 401 else f"Permission '{permission}' required"
                return JsonResponse(
                    {"detail": detail, "code": code},
                    status=status,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator

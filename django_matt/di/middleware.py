"""
Dependency Injection Middleware.

Provides middleware for:
- Creating request scopes for scoped services
- Auto-injecting dependencies into views
"""

import inspect
from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, HttpResponse

from .container import Container, _scoped_instances
from .container import container as default_container
from .depends import aresolve_dependencies, resolve_dependencies


class RequestScopeMiddleware:
    """
    Middleware that creates a new DI scope for each request.

    This ensures that scoped services get a fresh instance per request
    and are properly cleaned up when the request finishes.

    Add to MIDDLEWARE:
        MIDDLEWARE = [
            ...
            'django_matt.di.RequestScopeMiddleware',
        ]
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Create a new scope for this request
        token = _scoped_instances.set({})

        try:
            response = self.get_response(request)
            return response
        finally:
            # Clean up the scope
            _scoped_instances.reset(token)


class AsyncRequestScopeMiddleware:
    """
    Async version of RequestScopeMiddleware.

    Add to MIDDLEWARE:
        MIDDLEWARE = [
            ...
            'django_matt.di.AsyncRequestScopeMiddleware',
        ]
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        if inspect.iscoroutinefunction(get_response):
            self._is_async = True
        else:
            self._is_async = False

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        # Create a new scope for this request
        token = _scoped_instances.set({})

        try:
            if self._is_async:
                response = await self.get_response(request)
            else:
                response = self.get_response(request)
            return response
        finally:
            # Clean up the scope
            _scoped_instances.reset(token)


class DependencyInjectionMiddleware:
    """
    Middleware that enables automatic dependency injection.

    This middleware:
    1. Creates a request scope for scoped services
    2. Makes the request available to dependency markers
    3. Resolves dependencies marked with Depends()

    Add to MIDDLEWARE:
        MIDDLEWARE = [
            ...
            'django_matt.di.DependencyInjectionMiddleware',
        ]
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.container = default_container

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Create a new scope for this request
        token = _scoped_instances.set({})

        # Store container on request for views to access
        request.di_container = self.container

        try:
            response = self.get_response(request)
            return response
        finally:
            # Clean up the scope
            _scoped_instances.reset(token)


class AsyncDependencyInjectionMiddleware:
    """Async version of DependencyInjectionMiddleware."""

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.container = default_container
        self._is_async = inspect.iscoroutinefunction(get_response)

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        # Create a new scope for this request
        token = _scoped_instances.set({})

        # Store container on request for views to access
        request.di_container = self.container

        try:
            if self._is_async:
                response = await self.get_response(request)
            else:
                response = self.get_response(request)
            return response
        finally:
            # Clean up the scope
            _scoped_instances.reset(token)


def inject_dependencies(
    func: Callable = None,
    *,
    container: Container = None,
) -> Callable:
    """
    Decorator that injects dependencies into a view function.

    This is useful for function-based views where you want DI
    without using controllers.

    Usage:
        from django_matt.di import inject_dependencies, Depends

        @inject_dependencies
        def my_view(request, user_service: UserService = Depends()):
            users = user_service.list_users()
            return JsonResponse({"users": users})

        # Async views work too
        @inject_dependencies
        async def my_async_view(request, user_service: UserService = Depends()):
            users = await user_service.list_users_async()
            return JsonResponse({"users": users})
    """
    container = container or default_container

    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(request, *args, **kwargs):
                # Resolve dependencies
                deps = await aresolve_dependencies(
                    fn,
                    request=request,
                    container=container,
                    **kwargs,
                )
                kwargs.update(deps)
                return await fn(request, *args, **kwargs)

            return async_wrapper

        @wraps(fn)
        def sync_wrapper(request, *args, **kwargs):
            # Resolve dependencies
            deps = resolve_dependencies(
                fn,
                request=request,
                container=container,
                **kwargs,
            )
            kwargs.update(deps)
            return fn(request, *args, **kwargs)

        return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator


def with_scope(func: Callable = None) -> Callable:
    """
    Decorator that creates a new DI scope for the function.

    Useful for background tasks or tests where you want
    a fresh set of scoped services.

    Usage:
        from django_matt.di import with_scope

        @with_scope
        def process_batch(items):
            service = container.resolve(BatchService)
            service.process(items)
    """

    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                token = _scoped_instances.set({})
                try:
                    return await fn(*args, **kwargs)
                finally:
                    _scoped_instances.reset(token)

            return async_wrapper

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            token = _scoped_instances.set({})
            try:
                return fn(*args, **kwargs)
            finally:
                _scoped_instances.reset(token)

        return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator

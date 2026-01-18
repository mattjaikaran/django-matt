"""
Page decorators for defining page views.

Provides @page, @layout, and other decorators for creating
server-driven SPA views.
"""

import asyncio
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union

from django.http import HttpRequest, HttpResponse

from django_matt.pages.response import PageResponse


def page(
    component: str,
    *,
    title: Optional[str] = None,
    meta: Optional[Dict[str, str]] = None,
    layout: Optional[Callable] = None,
    props_schema: Optional[Type] = None,
) -> Callable:
    """
    Decorator to define a page view.

    The decorated function should return a dict of props, which will
    be wrapped in a PageResponse automatically.

    Usage:
        @page("UserList")
        def user_list(request):
            users = User.objects.all()
            return {"users": users}

        @page("UserDetail", title="User Profile")
        def user_detail(request, id: int):
            user = get_object_or_404(User, id=id)
            return {"user": user}

        @page("Dashboard", layout=dashboard_layout)
        async def dashboard(request):
            stats = await get_dashboard_stats()
            return {"stats": stats}

    Args:
        component: The frontend component name to render
        title: Optional page title
        meta: Optional meta tags dict
        layout: Optional layout function for shared data
        props_schema: Optional Pydantic schema for props validation

    Returns:
        Decorated view function that returns PageResponse
    """
    def decorator(func: Callable) -> Callable:
        # Check if async
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:
            @wraps(func)
            async def async_wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
                return await _handle_page_view(
                    func, request, args, kwargs,
                    component=component,
                    title=title,
                    meta=meta,
                    layout=layout,
                    props_schema=props_schema,
                    is_async=True,
                )
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
                # Run sync version
                result = _handle_page_view_sync(
                    func, request, args, kwargs,
                    component=component,
                    title=title,
                    meta=meta,
                    layout=layout,
                    props_schema=props_schema,
                )
                return result
            return sync_wrapper

    return decorator


def _handle_page_view_sync(
    func: Callable,
    request: HttpRequest,
    args: tuple,
    kwargs: dict,
    *,
    component: str,
    title: Optional[str],
    meta: Optional[Dict[str, str]],
    layout: Optional[Callable],
    props_schema: Optional[Type],
) -> HttpResponse:
    """Handle a sync page view."""
    # Call the view function
    result = func(request, *args, **kwargs)

    # If already a response, return it
    if isinstance(result, (HttpResponse, PageResponse)):
        if isinstance(result, PageResponse):
            return result.render(request)
        return result

    # Result should be a dict of props
    if not isinstance(result, dict):
        raise TypeError(
            f"Page view {func.__name__} must return a dict or PageResponse, "
            f"got {type(result).__name__}"
        )

    props = result

    # Validate with schema if provided
    if props_schema:
        props = _validate_props(props, props_schema)

    # Get shared data from layout
    shared = {}
    if layout:
        layout_data = layout(request)
        if layout_data:
            shared.update(layout_data)

    # Create and render PageResponse
    response = PageResponse(
        component,
        props=props,
        shared=shared,
        title=title,
        meta=meta,
    )

    return response.render(request)


async def _handle_page_view(
    func: Callable,
    request: HttpRequest,
    args: tuple,
    kwargs: dict,
    *,
    component: str,
    title: Optional[str],
    meta: Optional[Dict[str, str]],
    layout: Optional[Callable],
    props_schema: Optional[Type],
    is_async: bool,
) -> HttpResponse:
    """Handle an async page view."""
    # Call the view function
    if is_async:
        result = await func(request, *args, **kwargs)
    else:
        result = func(request, *args, **kwargs)

    # If already a response, return it
    if isinstance(result, (HttpResponse, PageResponse)):
        if isinstance(result, PageResponse):
            return result.render(request)
        return result

    # Result should be a dict of props
    if not isinstance(result, dict):
        raise TypeError(
            f"Page view {func.__name__} must return a dict or PageResponse, "
            f"got {type(result).__name__}"
        )

    props = result

    # Validate with schema if provided
    if props_schema:
        props = _validate_props(props, props_schema)

    # Get shared data from layout
    shared = {}
    if layout:
        if asyncio.iscoroutinefunction(layout):
            layout_data = await layout(request)
        else:
            layout_data = layout(request)
        if layout_data:
            shared.update(layout_data)

    # Create and render PageResponse
    response = PageResponse(
        component,
        props=props,
        shared=shared,
        title=title,
        meta=meta,
    )

    return response.render(request)


def _validate_props(props: Dict[str, Any], schema: Type) -> Dict[str, Any]:
    """Validate props against a Pydantic schema."""
    try:
        from pydantic import BaseModel

        if issubclass(schema, BaseModel):
            validated = schema(**props)
            return validated.model_dump()
    except ImportError:
        pass
    except Exception as e:
        raise ValueError(f"Props validation failed: {e}")

    return props


def layout(component: str) -> Callable:
    """
    Decorator to define a layout that provides shared data.

    A layout function is called for every page that uses it,
    and its return value is merged into the page's shared data.

    Usage:
        @layout("DashboardLayout")
        def dashboard_layout(request):
            return {
                "user": request.user,
                "nav_items": get_nav_items(request.user),
                "notifications": get_notifications(request.user),
            }

        @page("Dashboard", layout=dashboard_layout)
        def dashboard(request):
            return {"stats": get_stats()}

    Args:
        component: The layout component name (for client-side)

    Returns:
        Decorated layout function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest) -> Dict[str, Any]:
            result = func(request)
            # Add layout component info
            if result is None:
                result = {}
            result["_layout"] = component
            return result
        return wrapper
    return decorator


def hybrid(
    component: str,
    *,
    title: Optional[str] = None,
    api_schema: Optional[Type] = None,
) -> Callable:
    """
    Decorator for hybrid API/Page endpoints.

    The decorated function serves as both:
    - A page view (returns PageResponse for browser)
    - An API endpoint (returns JSON for Accept: application/json)

    Usage:
        @api.get("/users")
        @hybrid("UserList")
        def user_list(request):
            users = User.objects.all()
            return {"users": users}

        # Browser visit → HTML page with UserList component
        # API request → JSON {"users": [...]}

    Args:
        component: The frontend component name
        title: Optional page title
        api_schema: Optional Pydantic schema for API response

    Returns:
        Decorated view function
    """
    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:
            @wraps(func)
            async def async_wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
                from django_matt.pages.middleware import get_request_mode, RequestMode

                mode = get_request_mode(request)

                # Call the view function
                result = await func(request, *args, **kwargs)

                # If already a response, return it
                if isinstance(result, HttpResponse):
                    return result

                # For API mode, return JSON directly
                if mode == RequestMode.API:
                    from django.http import JsonResponse
                    return JsonResponse(result)

                # For page mode, wrap in PageResponse
                response = PageResponse(component, props=result, title=title)
                return response.render(request)

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
                from django_matt.pages.middleware import get_request_mode, RequestMode

                mode = get_request_mode(request)

                # Call the view function
                result = func(request, *args, **kwargs)

                # If already a response, return it
                if isinstance(result, HttpResponse):
                    return result

                # For API mode, return JSON directly
                if mode == RequestMode.API:
                    from django.http import JsonResponse
                    return JsonResponse(result)

                # For page mode, wrap in PageResponse
                response = PageResponse(component, props=result, title=title)
                return response.render(request)

            return sync_wrapper

    return decorator


__all__ = [
    "page",
    "layout",
    "hybrid",
]

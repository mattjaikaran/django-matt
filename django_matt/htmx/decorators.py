"""
HTMX view decorators.

Provides decorators for HTMX-aware views with support for
partial template rendering and request detection.
"""

from functools import wraps
from typing import Any, Callable, Optional, Union
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.template.response import TemplateResponse

from django_matt.htmx.request import HtmxDetails, is_htmx_request


def htmx_view(
    template: Optional[str] = None,
    partial_template: Optional[str] = None,
    target: Optional[str] = None,
):
    """
    Decorator for views that handle both full page and HTMX requests.

    Automatically renders different templates based on request type:
    - Full page request: renders `template`
    - HTMX request: renders `partial_template`

    The view function should return a context dictionary.

    Args:
        template: Template for full page requests
        partial_template: Template for HTMX requests (defaults to template)
        target: Only respond to HTMX requests targeting this element ID

    Usage:
        @htmx_view(
            template="users/list.html",
            partial_template="users/partials/list.html"
        )
        def user_list(request):
            users = User.objects.all()
            return {"users": users}

        # Or with just one template:
        @htmx_view(template="users/partials/row.html")
        def user_row(request, user_id):
            user = get_object_or_404(User, id=user_id)
            return {"user": user}
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            # Get HTMX details
            htmx = HtmxDetails.from_request(request)

            # Check target filter
            if target and htmx and htmx.target != target:
                # Not our target, pass through
                pass

            # Call view function
            result = view_func(request, *args, **kwargs)

            # If view returns HttpResponse directly, use it
            if isinstance(result, HttpResponse):
                return result

            # Result should be context dict
            if not isinstance(result, dict):
                result = {"result": result}

            # Add htmx details to context
            result["htmx"] = htmx

            # Choose template
            if htmx:
                tmpl = partial_template or template
            else:
                tmpl = template

            if not tmpl:
                raise ValueError(
                    "htmx_view requires at least a template parameter"
                )

            return render(request, tmpl, result)

        # Store metadata for introspection
        wrapper.htmx_template = template
        wrapper.htmx_partial_template = partial_template
        wrapper.htmx_target = target

        return wrapper

    return decorator


def htmx_only(view_func: Optional[Callable] = None, *, allow_boosted: bool = True):
    """
    Restrict a view to HTMX requests only.

    Non-HTMX requests will receive a 405 Method Not Allowed response.

    Args:
        allow_boosted: If True, allow hx-boost requests (default: True)

    Usage:
        @htmx_only
        def partial_view(request):
            return HtmxResponse("<div>Only for HTMX</div>")

        @htmx_only(allow_boosted=False)
        def ajax_only(request):
            return HtmxResponse("<div>No boosted requests</div>")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            htmx = HtmxDetails.from_request(request)

            if not htmx:
                return HttpResponseNotAllowed(
                    ["HTMX"],
                    content="This endpoint only accepts HTMX requests.",
                )

            if htmx.boosted and not allow_boosted:
                return HttpResponseNotAllowed(
                    ["HTMX"],
                    content="This endpoint does not accept boosted requests.",
                )

            return func(request, *args, **kwargs)

        return wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator


def htmx_partial(template_name: str):
    """
    Simple decorator for rendering partials.

    The view function returns a context dict, which is rendered
    to the specified template.

    Usage:
        @htmx_partial("users/partials/card.html")
        def user_card(request, user_id):
            user = get_object_or_404(User, id=user_id)
            return {"user": user}
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            result = view_func(request, *args, **kwargs)

            if isinstance(result, HttpResponse):
                return result

            if not isinstance(result, dict):
                result = {"result": result}

            # Add htmx details
            result["htmx"] = HtmxDetails.from_request(request)

            return render(request, template_name, result)

        return wrapper

    return decorator


def htmx_trigger(
    *event_names: str,
    after: str = "receive",
    params: Optional[dict] = None,
):
    """
    Automatically add HTMX triggers to responses.

    Args:
        event_names: Event names to trigger
        after: When to trigger - "receive", "settle", or "swap"
        params: Optional parameters to include with events

    Usage:
        @htmx_trigger("itemsUpdated", "refreshSidebar")
        def update_items(request):
            # ... update logic ...
            return HtmxResponse("<div>Updated</div>")

        @htmx_trigger("notification", params={"type": "success"})
        def create_item(request):
            return HtmxResponse("<div>Created!</div>")
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            response = view_func(request, *args, **kwargs)

            # Add triggers to response
            from django_matt.htmx.response import trigger_client_event

            for event_name in event_names:
                trigger_client_event(response, event_name, params, after)

            return response

        return wrapper

    return decorator


def require_htmx_target(target_id: str):
    """
    Only process request if HTMX target matches.

    Useful for views that handle multiple HTMX targets on one page.

    Args:
        target_id: Required target element ID

    Usage:
        @require_htmx_target("user-list")
        def refresh_user_list(request):
            return render(request, "partials/user_list.html", {...})
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            htmx = HtmxDetails.from_request(request)

            if not htmx:
                return HttpResponseNotAllowed(["HTMX"])

            if htmx.target != target_id:
                return HttpResponse(
                    f"Expected target '{target_id}', got '{htmx.target}'",
                    status=400,
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def vary_on_htmx(view_func: Callable) -> Callable:
    """
    Add Vary: HX-Request header to response.

    Important for caching - ensures HTMX and non-HTMX responses
    are cached separately.

    Usage:
        @vary_on_htmx
        @htmx_view(template="page.html", partial_template="partial.html")
        def my_view(request):
            return {"data": data}
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        response = view_func(request, *args, **kwargs)

        # Add Vary header
        existing_vary = response.get("Vary", "")
        if "HX-Request" not in existing_vary:
            if existing_vary:
                response["Vary"] = f"{existing_vary}, HX-Request"
            else:
                response["Vary"] = "HX-Request"

        return response

    return wrapper


__all__ = [
    "htmx_view",
    "htmx_only",
    "htmx_partial",
    "htmx_trigger",
    "require_htmx_target",
    "vary_on_htmx",
]

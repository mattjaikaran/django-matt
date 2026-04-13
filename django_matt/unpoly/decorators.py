"""
Unpoly view decorators.

Provides decorators for Unpoly-aware views with support for
target management, layer control, and validation handling.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, HttpResponse

from django_matt.unpoly.request import UnpolyDetails


def up_target(selector: str) -> Callable:
    """
    Set a default X-Up-Target on the response.

    Args:
        selector: CSS selector for the default target fragment.

    Usage:
        @up_target(".main-content")
        def my_view(request):
            return render(request, "page.html")
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            response = view_func(request, *args, **kwargs)
            if "X-Up-Target" not in response:
                response["X-Up-Target"] = selector
            return response

        wrapper.up_target = selector
        return wrapper

    return decorator


def up_layer(mode: str) -> Callable:
    """
    Set the layer mode on the response.

    Args:
        mode: Layer mode — root, modal, drawer, popup, cover.

    Usage:
        @up_layer("modal")
        def edit_user(request, user_id):
            return render(request, "users/edit.html")
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            response = view_func(request, *args, **kwargs)
            if "X-Up-Mode" not in response:
                response["X-Up-Mode"] = mode
            return response

        wrapper.up_layer = mode
        return wrapper

    return decorator


def up_fail_target(selector: str) -> Callable:
    """
    Set a default X-Up-Fail-Target on the response.

    Args:
        selector: CSS selector for the fail target fragment.

    Usage:
        @up_fail_target(".error-container")
        def create_item(request):
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            response = view_func(request, *args, **kwargs)
            if "X-Up-Fail-Target" not in response:
                response["X-Up-Fail-Target"] = selector
            return response

        wrapper.up_fail_target = selector
        return wrapper

    return decorator


def up_only(view_func: Callable) -> Callable:
    """
    Restrict a view to Unpoly requests only.

    Non-Unpoly requests receive a 422 Unprocessable Entity response.

    Usage:
        @up_only
        def partial_view(request):
            return render(request, "partials/widget.html")
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        up = getattr(request, "up", None) or UnpolyDetails.from_request(request)
        if not up:
            return HttpResponse(
                "This endpoint only accepts Unpoly requests.",
                status=422,
                content_type="text/plain",
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def up_validate(view_func: Callable) -> Callable:
    """
    Decorator for validation endpoints.

    Checks that request.up.validate is set (meaning Unpoly is
    validating a specific form field). Returns 422 if not a
    validation request.

    Usage:
        @up_validate
        def validate_email(request):
            email = request.POST.get("email", "")
            if User.objects.filter(email=email).exists():
                return HttpResponse('<span class="error">Taken</span>')
            return HttpResponse('<span class="ok">Available</span>')
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        up = getattr(request, "up", None) or UnpolyDetails.from_request(request)
        if not up.is_validating:
            return HttpResponse(
                "This endpoint only accepts Unpoly validation requests.",
                status=422,
                content_type="text/plain",
            )
        return view_func(request, *args, **kwargs)

    wrapper.up_validate = True
    return wrapper


def vary_on_unpoly(view_func: Callable) -> Callable:
    """
    Add Vary: X-Up-Target header to response.

    Ensures Unpoly and non-Unpoly responses are cached separately.

    Usage:
        @vary_on_unpoly
        def my_view(request):
            if request.up:
                return render(request, "partial.html")
            return render(request, "full.html")
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        response = view_func(request, *args, **kwargs)
        existing = response.get("Vary", "")
        if "X-Up-Target" not in existing:
            if existing:
                response["Vary"] = f"{existing}, X-Up-Target"
            else:
                response["Vary"] = "X-Up-Target"
        return response

    return wrapper


__all__ = [
    "up_fail_target",
    "up_layer",
    "up_only",
    "up_target",
    "up_validate",
    "vary_on_unpoly",
]

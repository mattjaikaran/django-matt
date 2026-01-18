"""
Session authentication decorators.

Decorators for protecting views with session-based authentication.
"""

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def session_required(
    view_func: Callable | None = None,
    *,
    redirect_url: str | None = None,
    login_url: str | None = None,
):
    """
    Decorator to require session authentication.

    For API views, returns 401 Unauthorized.
    For web views with redirect_url, redirects to login.

    Usage:
        @api.get("/protected")
        @session_required
        async def protected_view(request):
            return {"user": request.user.email}

        # With redirect for web views
        @session_required(redirect_url="/login")
        def dashboard(request):
            return render(request, "dashboard.html")
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(request, *args, **kwargs):
            if not _is_authenticated(request):
                return _unauthorized_response(request, redirect_url or login_url)
            return func(request, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(request, *args, **kwargs):
            if not _is_authenticated(request):
                return _unauthorized_response(request, redirect_url or login_url)
            return await func(request, *args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator


def session_optional(view_func: Callable) -> Callable:
    """
    Decorator that allows both authenticated and anonymous access.

    The user will be set on request if authenticated, otherwise AnonymousUser.
    Does not return an error for unauthenticated requests.

    Usage:
        @api.get("/public")
        @session_optional
        async def public_view(request):
            if request.user.is_authenticated:
                return {"user": request.user.email}
            return {"user": "anonymous"}
    """

    @functools.wraps(view_func)
    def sync_wrapper(request, *args, **kwargs):
        # User is already set by middleware, just pass through
        return view_func(request, *args, **kwargs)

    @functools.wraps(view_func)
    async def async_wrapper(request, *args, **kwargs):
        return await view_func(request, *args, **kwargs)

    import asyncio

    if asyncio.iscoroutinefunction(view_func):
        return async_wrapper
    return sync_wrapper


def login_required(
    view_func: Callable | None = None,
    *,
    redirect_field_name: str = "next",
    login_url: str | None = None,
):
    """
    Decorator similar to Django's login_required.

    For web views, redirects to login page with next parameter.
    For API views, returns 401.

    Usage:
        @login_required
        def my_view(request):
            ...

        @login_required(login_url="/auth/login")
        def my_view(request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(request, *args, **kwargs):
            if not _is_authenticated(request):
                return _login_redirect(request, login_url, redirect_field_name)
            return func(request, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(request, *args, **kwargs):
            if not _is_authenticated(request):
                return _login_redirect(request, login_url, redirect_field_name)
            return await func(request, *args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator


def fresh_session_required(
    view_func: Callable | None = None,
    *,
    max_age: int = 300,  # 5 minutes
    redirect_url: str | None = None,
):
    """
    Decorator to require a fresh session for sensitive operations.

    A session is "fresh" if the user authenticated recently.
    Useful for password changes, payment actions, etc.

    Usage:
        @api.post("/change-password")
        @fresh_session_required(max_age=300)
        async def change_password(request, data: PasswordChangeSchema):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(request, *args, **kwargs):
            if not _is_authenticated(request):
                return _unauthorized_response(request, redirect_url)

            if not _is_session_fresh(request, max_age):
                return _reauthentication_required(request, redirect_url)

            return func(request, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(request, *args, **kwargs):
            if not _is_authenticated(request):
                return _unauthorized_response(request, redirect_url)

            if not _is_session_fresh(request, max_age):
                return _reauthentication_required(request, redirect_url)

            return await func(request, *args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator


def _is_authenticated(request: "HttpRequest") -> bool:
    """Check if request has an authenticated user."""
    user = getattr(request, "user", None)
    return user is not None and user.is_authenticated


def _is_session_fresh(request: "HttpRequest", max_age: int) -> bool:
    """Check if the session is fresh (recently authenticated)."""
    session = getattr(request, "session", None)
    if not session:
        return False

    # Check using our enhanced session store method
    if hasattr(session, "is_fresh"):
        return session.is_fresh(max_age)

    # Fallback: check _session_created timestamp
    from datetime import datetime

    from django.utils import timezone

    created = session.get("_session_created")
    if not created:
        return False

    try:
        created_time = datetime.fromisoformat(created)
        age = (timezone.now() - created_time).total_seconds()
        return age < max_age
    except (ValueError, TypeError):
        return False


def _unauthorized_response(
    request: "HttpRequest",
    redirect_url: str | None = None,
) -> "HttpResponse":
    """Return appropriate unauthorized response."""
    # Check if this is an API request
    if _is_api_request(request):
        from django.http import JsonResponse

        return JsonResponse(
            {"detail": "Authentication required"},
            status=401,
        )

    # Web request - redirect if URL provided
    if redirect_url:
        from django.shortcuts import redirect

        return redirect(redirect_url)

    # Default: return 401
    from django.http import HttpResponse

    return HttpResponse("Authentication required", status=401)


def _login_redirect(
    request: "HttpRequest",
    login_url: str | None = None,
    redirect_field_name: str = "next",
) -> "HttpResponse":
    """Redirect to login page with next parameter."""
    from urllib.parse import urlencode

    from django.conf import settings
    from django.shortcuts import redirect

    # Get login URL
    url = login_url or getattr(settings, "LOGIN_URL", "/login")

    # For API requests, just return 401
    if _is_api_request(request):
        from django.http import JsonResponse

        return JsonResponse(
            {"detail": "Authentication required", "login_url": url},
            status=401,
        )

    # Add next parameter
    if redirect_field_name:
        params = {redirect_field_name: request.get_full_path()}
        url = f"{url}?{urlencode(params)}"

    return redirect(url)


def _reauthentication_required(
    request: "HttpRequest",
    redirect_url: str | None = None,
) -> "HttpResponse":
    """Return response requiring re-authentication."""
    if _is_api_request(request):
        from django.http import JsonResponse

        return JsonResponse(
            {
                "detail": "Re-authentication required for this action",
                "code": "fresh_session_required",
            },
            status=403,
        )

    if redirect_url:
        from django.shortcuts import redirect

        return redirect(redirect_url)

    from django.http import HttpResponse

    return HttpResponse("Re-authentication required", status=403)


def _is_api_request(request: "HttpRequest") -> bool:
    """Check if this is an API request (wants JSON response)."""
    accept = request.META.get("HTTP_ACCEPT", "")
    content_type = request.content_type or ""

    return (
        "application/json" in accept
        or "application/json" in content_type
        or request.path.startswith("/api/")
    )

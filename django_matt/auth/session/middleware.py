"""
Session authentication middleware.

Provides session-based authentication and CSRF protection.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin

from .config import get_session_config

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


class SessionAuthMiddleware(MiddlewareMixin):
    """
    Middleware that authenticates users via session cookies.

    This works alongside Django's built-in SessionMiddleware.
    Add after SessionMiddleware in MIDDLEWARE list.

    Usage:
        MIDDLEWARE = [
            ...
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django_matt.auth.session.SessionAuthMiddleware',
            ...
        ]
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.config = get_session_config()

    def __call__(self, request: "HttpRequest") -> "HttpResponse":
        # Ensure session exists
        if not hasattr(request, "session"):
            request.user = AnonymousUser()
            return self.get_response(request)

        # Try to get user from session
        user = self._get_user_from_session(request)
        request.user = user

        # Track activity if configured
        if (
            self.config.track_session_activity
            and user.is_authenticated
            and hasattr(request.session, "mark_activity")
        ):
            request.session.mark_activity()
            request.session.modified = True

        response = self.get_response(request)

        return response

    def _get_user_from_session(self, request: "HttpRequest"):
        """Get user from session data."""
        User = get_user_model()

        user_id = request.session.get("_auth_user_id")
        if not user_id:
            return AnonymousUser()

        try:
            user = User.objects.get(pk=user_id)
            # Check if user is still active
            if not user.is_active:
                return AnonymousUser()
            return user
        except User.DoesNotExist:
            return AnonymousUser()


class CSRFMiddleware(MiddlewareMixin):
    """
    CSRF protection middleware for session-based authentication.

    Validates CSRF tokens on state-changing requests (POST, PUT, PATCH, DELETE).
    Skips validation for safe methods (GET, HEAD, OPTIONS) and exempted views.

    Usage:
        MIDDLEWARE = [
            ...
            'django_matt.auth.session.CSRFMiddleware',
            ...
        ]
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.config = get_session_config()

    def __call__(self, request: "HttpRequest") -> "HttpResponse":
        if not self.config.csrf_enabled:
            return self.get_response(request)

        # Set CSRF token cookie on all requests
        self._ensure_csrf_cookie(request)

        # Skip validation for safe methods
        if request.method in self.SAFE_METHODS:
            return self.get_response(request)

        # Skip if view is CSRF exempt
        if getattr(request, "_csrf_exempt", False):
            return self.get_response(request)

        # Skip if view is marked with our csrf_exempt decorator
        view = getattr(request, "resolver_match", None)
        if view and getattr(view.func, "_csrf_exempt", False):
            return self.get_response(request)

        # Skip for trusted origins
        if self._is_trusted_origin(request):
            return self.get_response(request)

        # Validate CSRF token
        if not self._validate_csrf(request):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("CSRF token validation failed")

        return self.get_response(request)

    def _ensure_csrf_cookie(self, request: "HttpRequest") -> None:
        """Ensure CSRF token exists in session."""
        from .csrf import get_csrf_token

        # Generate token if not exists
        get_csrf_token(request)

    def _validate_csrf(self, request: "HttpRequest") -> bool:
        """Validate CSRF token from request."""
        from .csrf import verify_csrf_token

        # Get token from header or POST data
        token = self._get_csrf_token_from_request(request)

        if not token:
            return False

        return verify_csrf_token(request, token)

    def _get_csrf_token_from_request(self, request: "HttpRequest") -> str | None:
        """Extract CSRF token from request."""
        # Try header first (for AJAX requests)
        header_name = f"HTTP_{self.config.csrf_header_name.upper().replace('-', '_')}"
        token = request.META.get(header_name)

        if token:
            return token

        # Try POST data
        if hasattr(request, "POST"):
            token = request.POST.get("csrfmiddlewaretoken")
            if token:
                return token

        # Try cookie (double-submit pattern)
        token = request.COOKIES.get(self.config.csrf_cookie_name)

        return token

    def _is_trusted_origin(self, request: "HttpRequest") -> bool:
        """Check if request is from a trusted origin."""
        if not self.config.csrf_trusted_origins:
            return False

        origin = request.META.get("HTTP_ORIGIN")
        referer = request.META.get("HTTP_REFERER")

        check_origin = origin or referer
        if not check_origin:
            return False

        for trusted in self.config.csrf_trusted_origins:
            if check_origin.startswith(trusted):
                return True

        return False

    def process_response(self, request: "HttpRequest", response: "HttpResponse") -> "HttpResponse":
        """Set CSRF cookie on response."""
        from .csrf import get_csrf_token

        if not self.config.csrf_enabled:
            return response

        # Set CSRF cookie
        token = get_csrf_token(request)

        if token and not request.COOKIES.get(self.config.csrf_cookie_name):
            response.set_cookie(
                self.config.csrf_cookie_name,
                token,
                max_age=self.config.csrf_cookie_age,
                path="/",
                secure=self.config.csrf_cookie_secure,
                httponly=self.config.csrf_cookie_httponly,
                samesite=self.config.csrf_cookie_samesite,
            )

        return response


class AsyncSessionAuthMiddleware:
    """Async version of SessionAuthMiddleware."""

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.config = get_session_config()

    async def __call__(self, request: "HttpRequest") -> "HttpResponse":
        if not hasattr(request, "session"):
            request.user = AnonymousUser()
            return await self.get_response(request)

        user = await self._aget_user_from_session(request)
        request.user = user

        if (
            self.config.track_session_activity
            and user.is_authenticated
            and hasattr(request.session, "mark_activity")
        ):
            request.session.mark_activity()
            request.session.modified = True

        response = await self.get_response(request)
        return response

    async def _aget_user_from_session(self, request: "HttpRequest"):
        """Get user from session (async)."""
        from asgiref.sync import sync_to_async

        User = get_user_model()

        user_id = request.session.get("_auth_user_id")
        if not user_id:
            return AnonymousUser()

        try:
            user = await sync_to_async(User.objects.get)(pk=user_id)
            if not user.is_active:
                return AnonymousUser()
            return user
        except User.DoesNotExist:
            return AnonymousUser()


class AsyncCSRFMiddleware:
    """Async version of CSRFMiddleware."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.config = get_session_config()

    async def __call__(self, request: "HttpRequest") -> "HttpResponse":
        if not self.config.csrf_enabled:
            return await self.get_response(request)

        from .csrf import get_csrf_token

        get_csrf_token(request)

        if request.method in self.SAFE_METHODS:
            return await self.get_response(request)

        if getattr(request, "_csrf_exempt", False):
            return await self.get_response(request)

        view = getattr(request, "resolver_match", None)
        if view and getattr(view.func, "_csrf_exempt", False):
            return await self.get_response(request)

        if not self._validate_csrf(request):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("CSRF token validation failed")

        response = await self.get_response(request)

        token = get_csrf_token(request)
        if token and not request.COOKIES.get(self.config.csrf_cookie_name):
            response.set_cookie(
                self.config.csrf_cookie_name,
                token,
                max_age=self.config.csrf_cookie_age,
                path="/",
                secure=self.config.csrf_cookie_secure,
                httponly=self.config.csrf_cookie_httponly,
                samesite=self.config.csrf_cookie_samesite,
            )

        return response

    def _validate_csrf(self, request: "HttpRequest") -> bool:
        """Validate CSRF token."""
        from .csrf import verify_csrf_token

        header_name = f"HTTP_{self.config.csrf_header_name.upper().replace('-', '_')}"
        token = request.META.get(header_name)

        if not token and hasattr(request, "POST"):
            token = request.POST.get("csrfmiddlewaretoken")

        if not token:
            token = request.COOKIES.get(self.config.csrf_cookie_name)

        if not token:
            return False

        return verify_csrf_token(request, token)

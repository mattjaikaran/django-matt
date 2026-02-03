"""
Feature flag middleware.

Provides middleware for setting up flag context on each request.

Usage:
    # In settings.py
    MIDDLEWARE = [
        ...
        'django_matt.flags.FlagMiddleware',
        ...
    ]

    # Then in views:
    from django_matt.flags import feature_enabled
    if feature_enabled("my_flag"):
        ...
"""

import logging
from typing import Callable

from django.http import HttpRequest, HttpResponse

from django_matt.flags.context import FlagContext, set_current_context

logger = logging.getLogger("django_matt.flags")


class FlagMiddleware:
    """
    Middleware that sets up feature flag context for each request.

    Creates a FlagContext from the request and sets it as the current
    context for the duration of the request.

    This middleware should be placed after authentication middleware
    so that request.user is available.

    Configuration (in settings.py):
        FEATURE_FLAG_MIDDLEWARE = {
            "header_overrides": True,  # Allow flag overrides via headers
            "cookie_overrides": True,  # Allow flag overrides via cookies
            "query_overrides": True,   # Allow flag overrides via query params
            "override_prefix": "ff_",  # Prefix for override params
            "expose_flags_header": True,  # Add X-Feature-Flags header to response
        }
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

        # Load configuration
        from django.conf import settings

        config = getattr(settings, "FEATURE_FLAG_MIDDLEWARE", {})
        self.header_overrides = config.get("header_overrides", False)
        self.cookie_overrides = config.get("cookie_overrides", False)
        self.query_overrides = config.get("query_overrides", False)
        self.override_prefix = config.get("override_prefix", "ff_")
        self.expose_flags_header = config.get("expose_flags_header", False)
        self.debug_mode = config.get("debug_mode", settings.DEBUG)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Create flag context from request
        ctx = FlagContext.from_request(request)

        # Apply overrides if enabled
        if self.debug_mode:
            self._apply_overrides(request, ctx)

        # Set as current context
        set_current_context(ctx)

        # Store on request for easy access
        request.flag_context = ctx  # type: ignore

        try:
            response = self.get_response(request)

            # Add flags header if enabled
            if self.expose_flags_header:
                self._add_flags_header(response, ctx)

            return response
        finally:
            # Clear context
            set_current_context(None)

    def _apply_overrides(self, request: HttpRequest, ctx: FlagContext):
        """Apply flag overrides from headers, cookies, or query params."""
        overrides = {}

        # Header overrides (X-Feature-Flag-{flag_name}: true/false)
        if self.header_overrides:
            for key, value in request.META.items():
                if key.startswith("HTTP_X_FEATURE_FLAG_"):
                    flag_key = key[20:].lower().replace("_", "-")
                    overrides[flag_key] = value.lower() in ("true", "1", "yes", "on")

        # Cookie overrides
        if self.cookie_overrides:
            for key, value in request.COOKIES.items():
                if key.startswith(self.override_prefix):
                    flag_key = key[len(self.override_prefix) :]
                    overrides[flag_key] = value.lower() in ("true", "1", "yes", "on")

        # Query param overrides
        if self.query_overrides:
            for key, value in request.GET.items():
                if key.startswith(self.override_prefix):
                    flag_key = key[len(self.override_prefix) :]
                    overrides[flag_key] = value.lower() in ("true", "1", "yes", "on")

        # Apply overrides to context attributes
        if overrides:
            ctx.attributes["_overrides"] = overrides
            logger.debug(f"Applied flag overrides: {overrides}")

    def _add_flags_header(self, response: HttpResponse, ctx: FlagContext):
        """Add X-Feature-Flags header to response."""
        try:
            flags = ctx.get_all_flags()
            if flags:
                # Format: flag1=true,flag2=false,...
                header_value = ",".join(f"{k}={'true' if v else 'false'}" for k, v in flags.items())
                response["X-Feature-Flags"] = header_value
        except Exception as e:
            logger.warning(f"Failed to add feature flags header: {e}")


class AsyncFlagMiddleware:
    """
    Async version of FlagMiddleware.

    Use this with ASGI applications.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

        from django.conf import settings

        config = getattr(settings, "FEATURE_FLAG_MIDDLEWARE", {})
        self.header_overrides = config.get("header_overrides", False)
        self.cookie_overrides = config.get("cookie_overrides", False)
        self.query_overrides = config.get("query_overrides", False)
        self.override_prefix = config.get("override_prefix", "ff_")
        self.expose_flags_header = config.get("expose_flags_header", False)
        self.debug_mode = config.get("debug_mode", settings.DEBUG)

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        # Create flag context from request
        ctx = FlagContext.from_request(request)

        # Apply overrides if enabled
        if self.debug_mode:
            self._apply_overrides(request, ctx)

        # Set as current context
        set_current_context(ctx)

        # Store on request for easy access
        request.flag_context = ctx  # type: ignore

        try:
            response = await self.get_response(request)

            # Add flags header if enabled
            if self.expose_flags_header:
                self._add_flags_header(response, ctx)

            return response
        finally:
            # Clear context
            set_current_context(None)

    def _apply_overrides(self, request: HttpRequest, ctx: FlagContext):
        """Apply flag overrides from headers, cookies, or query params."""
        overrides = {}

        if self.header_overrides:
            for key, value in request.META.items():
                if key.startswith("HTTP_X_FEATURE_FLAG_"):
                    flag_key = key[20:].lower().replace("_", "-")
                    overrides[flag_key] = value.lower() in ("true", "1", "yes", "on")

        if self.cookie_overrides:
            for key, value in request.COOKIES.items():
                if key.startswith(self.override_prefix):
                    flag_key = key[len(self.override_prefix) :]
                    overrides[flag_key] = value.lower() in ("true", "1", "yes", "on")

        if self.query_overrides:
            for key, value in request.GET.items():
                if key.startswith(self.override_prefix):
                    flag_key = key[len(self.override_prefix) :]
                    overrides[flag_key] = value.lower() in ("true", "1", "yes", "on")

        if overrides:
            ctx.attributes["_overrides"] = overrides

    def _add_flags_header(self, response: HttpResponse, ctx: FlagContext):
        """Add X-Feature-Flags header to response."""
        try:
            flags = ctx.get_all_flags()
            if flags:
                header_value = ",".join(f"{k}={'true' if v else 'false'}" for k, v in flags.items())
                response["X-Feature-Flags"] = header_value
        except Exception as e:
            logger.warning(f"Failed to add feature flags header: {e}")


__all__ = [
    "FlagMiddleware",
    "AsyncFlagMiddleware",
]

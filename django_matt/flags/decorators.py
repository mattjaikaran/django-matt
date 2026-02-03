"""
Feature flag decorators.

Provides decorators for controlling access based on feature flags.

Usage:
    from django_matt.flags import feature_flag, requires_flag

    # Enable/disable endpoint based on flag
    @feature_flag("new_api", default=False)
    async def new_endpoint(request):
        ...

    # Require flag to be enabled (404 if not)
    @requires_flag("beta_feature")
    async def beta_endpoint(request):
        ...

    # With custom fallback
    @feature_flag("experimental", fallback=old_endpoint)
    async def experimental_endpoint(request):
        ...
"""

import functools
import inspect
from typing import TYPE_CHECKING, Any, Callable

from django.http import HttpResponse, JsonResponse

if TYPE_CHECKING:
    from django.http import HttpRequest


def feature_flag(
    flag_key: str,
    default: bool = False,
    fallback: Callable | None = None,
    fallback_response: HttpResponse | dict | None = None,
):
    """
    Decorator that gates a view based on a feature flag.

    If the flag is disabled:
    - Calls fallback function if provided
    - Returns fallback_response if provided
    - Returns 404 if neither is provided and default is False

    Args:
        flag_key: The feature flag key to check
        default: Default value if flag doesn't exist
        fallback: Alternative function to call if flag is disabled
        fallback_response: Response to return if flag is disabled

    Returns:
        Decorated function

    Example:
        @feature_flag("new_checkout")
        async def checkout_v2(request):
            ...

        @feature_flag("beta", fallback=stable_endpoint)
        async def beta_endpoint(request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.flags.context import FlagContext

            # Get or create context
            ctx = FlagContext.from_request(request)

            if ctx.is_enabled(flag_key, default=default):
                return await func(request, *args, **kwargs)

            # Flag is disabled
            if fallback is not None:
                if inspect.iscoroutinefunction(fallback):
                    return await fallback(request, *args, **kwargs)
                return fallback(request, *args, **kwargs)

            if fallback_response is not None:
                if isinstance(fallback_response, dict):
                    return JsonResponse(fallback_response, status=404)
                return fallback_response

            return JsonResponse(
                {"detail": "Feature not available", "code": "feature_disabled"},
                status=404,
            )

        @functools.wraps(func)
        def sync_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.flags.context import FlagContext

            # Get or create context
            ctx = FlagContext.from_request(request)

            if ctx.is_enabled(flag_key, default=default):
                return func(request, *args, **kwargs)

            # Flag is disabled
            if fallback is not None:
                return fallback(request, *args, **kwargs)

            if fallback_response is not None:
                if isinstance(fallback_response, dict):
                    return JsonResponse(fallback_response, status=404)
                return fallback_response

            return JsonResponse(
                {"detail": "Feature not available", "code": "feature_disabled"},
                status=404,
            )

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def requires_flag(
    flag_key: str,
    status_code: int = 404,
    error_message: str = "Feature not available",
    error_code: str = "feature_disabled",
):
    """
    Decorator that requires a feature flag to be enabled.

    Returns an error response if the flag is disabled.

    Args:
        flag_key: The feature flag key to require
        status_code: HTTP status code for error response
        error_message: Error message to return
        error_code: Error code for the response

    Returns:
        Decorated function

    Example:
        @requires_flag("beta_feature")
        async def beta_only_endpoint(request):
            ...

        @requires_flag("admin_tools", status_code=403, error_message="Access denied")
        async def admin_tools(request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.flags.context import FlagContext

            ctx = FlagContext.from_request(request)

            if not ctx.is_enabled(flag_key):
                return JsonResponse(
                    {"detail": error_message, "code": error_code},
                    status=status_code,
                )

            return await func(request, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.flags.context import FlagContext

            ctx = FlagContext.from_request(request)

            if not ctx.is_enabled(flag_key):
                return JsonResponse(
                    {"detail": error_message, "code": error_code},
                    status=status_code,
                )

            return func(request, *args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def variant_flag(
    flag_key: str,
    variant_handlers: dict[str, Callable] | None = None,
    default_variant: str | None = None,
):
    """
    Decorator for A/B testing with variant-based routing.

    Routes to different handlers based on variant assignment.

    Args:
        flag_key: The feature flag key
        variant_handlers: Dict mapping variant keys to handler functions
        default_variant: Default variant if none assigned

    Returns:
        Decorated function

    Example:
        @variant_flag(
            "checkout_experiment",
            variant_handlers={
                "control": checkout_v1,
                "treatment_a": checkout_v2,
                "treatment_b": checkout_v3,
            },
            default_variant="control",
        )
        async def checkout(request):
            # This is called if no variant matches
            ...
    """

    def decorator(func: Callable) -> Callable:
        handlers = variant_handlers or {}

        @functools.wraps(func)
        async def async_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.flags.context import FlagContext

            ctx = FlagContext.from_request(request)
            variant = ctx.get_variant(flag_key, default=default_variant)

            if variant and variant in handlers:
                handler = handlers[variant]
                if inspect.iscoroutinefunction(handler):
                    return await handler(request, *args, **kwargs)
                return handler(request, *args, **kwargs)

            return await func(request, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.flags.context import FlagContext

            ctx = FlagContext.from_request(request)
            variant = ctx.get_variant(flag_key, default=default_variant)

            if variant and variant in handlers:
                handler = handlers[variant]
                return handler(request, *args, **kwargs)

            return func(request, *args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def with_flag_context(func: Callable) -> Callable:
    """
    Decorator that ensures FlagContext is available.

    Creates a FlagContext from the request and sets it as current.
    Useful for functions that need flag context but don't check specific flags.

    Example:
        @with_flag_context
        async def my_view(request):
            from django_matt.flags import feature_enabled
            if feature_enabled("my_flag"):
                ...
    """

    @functools.wraps(func)
    async def async_wrapper(request: "HttpRequest", *args, **kwargs):
        from django_matt.flags.context import FlagContext

        ctx = FlagContext.from_request(request)
        with ctx:
            return await func(request, *args, **kwargs)

    @functools.wraps(func)
    def sync_wrapper(request: "HttpRequest", *args, **kwargs):
        from django_matt.flags.context import FlagContext

        ctx = FlagContext.from_request(request)
        with ctx:
            return func(request, *args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class FlagEnabledMixin:
    """
    Mixin for class-based views that adds feature flag checking.

    Usage:
        class MyView(FlagEnabledMixin, APIController):
            required_flags = ["beta_feature"]
            optional_flags = {"new_ui": False}

            async def get(self, request):
                if self.flag_context.is_enabled("new_ui"):
                    ...
    """

    # Flags that must be enabled for this view
    required_flags: list[str] = []

    # Optional flags with defaults
    optional_flags: dict[str, bool] = {}

    # Error response for disabled required flags
    flag_error_status: int = 404
    flag_error_message: str = "Feature not available"

    @property
    def flag_context(self):
        """Get the flag context for this request."""
        if not hasattr(self, "_flag_context"):
            from django_matt.flags.context import FlagContext

            self._flag_context = FlagContext.from_request(self.request)
        return self._flag_context

    def check_flags(self) -> HttpResponse | None:
        """
        Check required flags.

        Returns error response if any required flag is disabled,
        None if all flags are enabled.
        """
        for flag_key in self.required_flags:
            if not self.flag_context.is_enabled(flag_key):
                return JsonResponse(
                    {"detail": self.flag_error_message, "code": "feature_disabled"},
                    status=self.flag_error_status,
                )
        return None

    def is_flag_enabled(self, flag_key: str) -> bool:
        """Check if a specific flag is enabled."""
        default = self.optional_flags.get(flag_key, False)
        return self.flag_context.is_enabled(flag_key, default=default)

    def get_variant(self, flag_key: str, default: str | None = None) -> str | None:
        """Get variant for a flag."""
        return self.flag_context.get_variant(flag_key, default=default)


__all__ = [
    "feature_flag",
    "requires_flag",
    "variant_flag",
    "with_flag_context",
    "FlagEnabledMixin",
]

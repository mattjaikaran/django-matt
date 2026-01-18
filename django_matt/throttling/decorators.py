"""
Throttle decorators for django-matt.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from django_matt.throttling.backends import get_default_backend
from django_matt.throttling.base import BaseThrottle
from django_matt.throttling.throttles import AnonRateThrottle, UserRateThrottle

if TYPE_CHECKING:
    from django.http import HttpRequest

F = TypeVar("F", bound=Callable[..., Any])


class ThrottleError(Exception):
    """Raised when a request is throttled."""

    def __init__(
        self,
        message: str = "Request was throttled",
        wait: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.wait = wait
        self.headers = headers or {}


def throttle(
    throttle_class: type[BaseThrottle] | None = None,
    *,
    rate: str | None = None,
    scope: str | None = None,
    methods: list[str] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to apply rate limiting to a view function.

    Can be used with or without arguments:
        @throttle(rate="100/hour")
        def my_view(request): ...

        @throttle(UserRateThrottle, rate="1000/day")
        def my_view(request): ...

        @throttle(ScopedRateThrottle, scope="uploads")
        def upload_view(request): ...

    Args:
        throttle_class: Throttle class to use (default: UserRateThrottle for authenticated,
                       AnonRateThrottle for anonymous)
        rate: Rate limit string like "100/hour"
        scope: Scope name for ScopedRateThrottle
        methods: HTTP methods to throttle (default: all methods)

    Returns:
        Decorated function with rate limiting
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            # Check if method should be throttled
            if methods and request.method.upper() not in [m.upper() for m in methods]:
                return func(request, *args, **kwargs)

            # Determine throttle class
            cls = throttle_class
            if cls is None:
                # Auto-select based on authentication
                if hasattr(request, "user") and request.user.is_authenticated:
                    cls = UserRateThrottle
                else:
                    cls = AnonRateThrottle

            # Create throttle instance
            throttle_kwargs: dict[str, Any] = {}
            if rate is not None:
                throttle_kwargs["rate"] = rate
            if scope is not None and hasattr(cls, "scope"):
                throttle_kwargs["scope"] = scope

            throttle_instance = cls(**throttle_kwargs)

            # Set backend
            throttle_instance.backend = get_default_backend()

            # Check if request is allowed
            if not throttle_instance.allow_request(request):
                wait = throttle_instance.wait()
                headers = throttle_instance.get_throttle_headers()
                raise ThrottleError(
                    message=f"Request was throttled. Expected available in {int(wait or 0)} seconds.",
                    wait=wait,
                    headers=headers,
                )

            # Request allowed - execute view
            response = func(request, *args, **kwargs)

            # Add rate limit headers to response if it's an HttpResponse
            if hasattr(response, "__setitem__"):
                for key, value in throttle_instance.get_throttle_headers().items():
                    response[key] = value

            return response

        # Store throttle info for introspection
        wrapper._throttle_class = throttle_class  # type: ignore
        wrapper._throttle_rate = rate  # type: ignore
        wrapper._throttle_scope = scope  # type: ignore

        return wrapper  # type: ignore

    return decorator


def throttle_anon(rate: str = "100/hour") -> Callable[[F], F]:
    """
    Shortcut decorator to throttle anonymous users.

    Example:
        @throttle_anon("50/hour")
        def public_endpoint(request):
            return {"message": "Hello"}

    Args:
        rate: Rate limit string

    Returns:
        Decorated function with anonymous rate limiting
    """
    return throttle(AnonRateThrottle, rate=rate)


def throttle_user(rate: str = "1000/day") -> Callable[[F], F]:
    """
    Shortcut decorator to throttle authenticated users.

    Example:
        @throttle_user("500/hour")
        def user_endpoint(request):
            return {"message": "Hello"}

    Args:
        rate: Rate limit string

    Returns:
        Decorated function with user rate limiting
    """
    return throttle(UserRateThrottle, rate=rate)


class ThrottlesMixin:
    """
    Mixin for class-based views to apply throttling.

    Example:
        class MyController(Controller, ThrottlesMixin):
            throttle_classes = [UserRateThrottle]
            throttle_rates = {"default": "100/hour"}

            @route.get("/items")
            def list_items(self):
                return []
    """

    throttle_classes: list[type[BaseThrottle]] = []
    throttle_rates: dict[str, str] = {}

    def get_throttles(self) -> list[BaseThrottle]:
        """
        Get throttle instances for this view.

        Returns:
            List of throttle instances
        """
        backend = get_default_backend()
        throttles = []

        for cls in self.throttle_classes:
            rate = self.throttle_rates.get(cls.__name__, None)
            instance = cls(rate=rate) if rate else cls()
            instance.backend = backend
            throttles.append(instance)

        return throttles

    def check_throttles(self, request: HttpRequest) -> None:
        """
        Check if the request should be throttled.

        Args:
            request: The Django HTTP request

        Raises:
            ThrottleError: If any throttle denies the request
        """
        for throttle_instance in self.get_throttles():
            if not throttle_instance.allow_request(request):
                wait = throttle_instance.wait()
                headers = throttle_instance.get_throttle_headers()
                raise ThrottleError(
                    message=f"Request was throttled. Expected available in {int(wait or 0)} seconds.",
                    wait=wait,
                    headers=headers,
                )

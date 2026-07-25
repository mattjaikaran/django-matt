# file-length-max: 550
"""
Analytics decorators.

Provides decorators for tracking events and timing on views and functions.

Usage:
    from django_matt.analytics import track_event, track_timing

    @track_event("api_called", properties={"endpoint": "users"})
    async def get_users(request):
        ...

    @track_timing("db_query")
    async def expensive_query():
        ...

    @track_event("button_click", include_args=True)
    def handle_click(request, button_id):
        ...
"""

import functools
import inspect
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("django_matt.analytics")


def track_event(
    event_name: str,
    properties: dict | None = None,
    category: str = "custom",
    include_args: bool = False,
    include_result: bool = False,
    condition: Callable[..., bool] | None = None,
):
    """
    Decorator to track an event when a function is called.

    Args:
        event_name: Name of the event to track
        properties: Static properties to include
        category: Event category
        include_args: Include function arguments in properties
        include_result: Include function result in properties
        condition: Function to determine if event should be tracked

    Example:
        @track_event("user_signup", category="conversion")
        async def signup(request, data):
            ...

        @track_event("api_call", include_args=True)
        def api_endpoint(request, resource_id):
            ...

        @track_event(
            "expensive_operation",
            condition=lambda result: result.success,
            include_result=True,
        )
        def operation():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            from .tracker import get_tracker

            result = await func(*args, **kwargs)

            # Check condition
            if condition and not condition(result):
                return result

            # Build properties
            event_props = dict(properties or {})

            if include_args:
                # Get argument names
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())

                for i, arg in enumerate(args):
                    if i < len(params):
                        param_name = params[i]
                        # Skip request objects
                        if param_name != "request" and param_name != "self":
                            event_props[param_name] = _serialize_arg(arg)

                for key, value in kwargs.items():
                    if key != "request":
                        event_props[key] = _serialize_arg(value)

            if include_result:
                event_props["result"] = _serialize_arg(result)

            # Get user and session from request if available
            request = _get_request(args, kwargs)
            user = None
            session = None

            if request:
                if hasattr(request, "user") and request.user.is_authenticated:
                    user = request.user
                session = getattr(request, "analytics_session", None)

            # Track event
            tracker = get_tracker()
            tracker.track_event(
                name=event_name,
                properties=event_props,
                user=user,
                session=session,
                category=category,
                request=request,
            )

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            from .tracker import get_tracker

            result = func(*args, **kwargs)

            # Check condition
            if condition and not condition(result):
                return result

            # Build properties
            event_props = dict(properties or {})

            if include_args:
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())

                for i, arg in enumerate(args):
                    if i < len(params):
                        param_name = params[i]
                        if param_name != "request" and param_name != "self":
                            event_props[param_name] = _serialize_arg(arg)

                for key, value in kwargs.items():
                    if key != "request":
                        event_props[key] = _serialize_arg(value)

            if include_result:
                event_props["result"] = _serialize_arg(result)

            request = _get_request(args, kwargs)
            user = None
            session = None

            if request:
                if hasattr(request, "user") and request.user.is_authenticated:
                    user = request.user
                session = getattr(request, "analytics_session", None)

            tracker = get_tracker()
            tracker.track_event(
                name=event_name,
                properties=event_props,
                user=user,
                session=session,
                category=category,
                request=request,
            )

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_timing(
    metric_name: str,
    properties: dict | None = None,
    category: str = "system",
    threshold_ms: float | None = None,
    include_args: bool = False,
):
    """
    Decorator to track execution time of a function.

    Args:
        metric_name: Name for the timing metric
        properties: Static properties to include
        category: Event category
        threshold_ms: Only track if execution exceeds this threshold
        include_args: Include function arguments in properties

    Example:
        @track_timing("db_query")
        def query_database():
            ...

        @track_timing("api_latency", threshold_ms=100)
        async def slow_endpoint(request):
            ...

        @track_timing("process_time", include_args=True)
        def process_data(data_size):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            from .tracker import get_tracker

            start_time = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Check threshold
            if threshold_ms and elapsed_ms < threshold_ms:
                return result

            # Build properties
            event_props = dict(properties or {})
            event_props["duration_ms"] = elapsed_ms
            event_props["function"] = func.__name__
            event_props["module"] = func.__module__

            if include_args:
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())

                for i, arg in enumerate(args):
                    if i < len(params):
                        param_name = params[i]
                        if param_name != "request" and param_name != "self":
                            event_props[param_name] = _serialize_arg(arg)

                for key, value in kwargs.items():
                    if key != "request":
                        event_props[key] = _serialize_arg(value)

            request = _get_request(args, kwargs)
            user = None
            session = None

            if request:
                if hasattr(request, "user") and request.user.is_authenticated:
                    user = request.user
                session = getattr(request, "analytics_session", None)

            tracker = get_tracker()
            tracker.track_event(
                name=f"timing_{metric_name}",
                properties=event_props,
                user=user,
                session=session,
                category=category,
                request=request,
            )

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            from .tracker import get_tracker

            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if threshold_ms and elapsed_ms < threshold_ms:
                return result

            event_props = dict(properties or {})
            event_props["duration_ms"] = elapsed_ms
            event_props["function"] = func.__name__
            event_props["module"] = func.__module__

            if include_args:
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())

                for i, arg in enumerate(args):
                    if i < len(params):
                        param_name = params[i]
                        if param_name != "request" and param_name != "self":
                            event_props[param_name] = _serialize_arg(arg)

                for key, value in kwargs.items():
                    if key != "request":
                        event_props[key] = _serialize_arg(value)

            request = _get_request(args, kwargs)
            user = None
            session = None

            if request:
                if hasattr(request, "user") and request.user.is_authenticated:
                    user = request.user
                session = getattr(request, "analytics_session", None)

            tracker = get_tracker()
            tracker.track_event(
                name=f"timing_{metric_name}",
                properties=event_props,
                user=user,
                session=session,
                category=category,
                request=request,
            )

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_page_view(
    path: str | None = None,
    title: str = "",
):
    """
    Decorator to track a page view when a view is called.

    Args:
        path: Override path (defaults to request.path)
        title: Page title

    Example:
        @track_page_view(title="Dashboard")
        def dashboard_view(request):
            ...

        @track_page_view()  # Uses request.path automatically
        async def dynamic_view(request, slug):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            from .tracker import get_tracker

            request = _get_request(args, kwargs)
            if not request:
                return await func(*args, **kwargs)

            result = await func(*args, **kwargs)

            # Track page view
            tracker = get_tracker()
            user = None
            session = None

            if hasattr(request, "user") and request.user.is_authenticated:
                user = request.user
            session = getattr(request, "analytics_session", None)

            tracker.track_page_view(
                path=path or request.path,
                url=request.build_absolute_uri(),
                title=title,
                user=user,
                session=session,
                referrer=request.META.get("HTTP_REFERER"),
                request=request,
            )

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            from .tracker import get_tracker

            request = _get_request(args, kwargs)
            if not request:
                return func(*args, **kwargs)

            result = func(*args, **kwargs)

            tracker = get_tracker()
            user = None
            session = None

            if hasattr(request, "user") and request.user.is_authenticated:
                user = request.user
            session = getattr(request, "analytics_session", None)

            tracker.track_page_view(
                path=path or request.path,
                url=request.build_absolute_uri(),
                title=title,
                user=user,
                session=session,
                referrer=request.META.get("HTTP_REFERER"),
                request=request,
            )

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class TrackedMixin:
    """
    Mixin for class-based views to add analytics tracking.

    Usage:
        class MyView(TrackedMixin, APIController):
            tracked_events = ["view_accessed"]
            track_page_views = True

            async def get(self, request):
                # Automatically tracks "view_accessed" event
                # and page view
                ...
    """

    # Events to track when view is accessed
    tracked_events: list[str] = []

    # Whether to track page views
    track_page_views: bool = False

    # Additional properties for tracked events
    track_properties: dict = {}

    def _track_analytics(self, request):
        """Track analytics for this view."""
        from .tracker import get_tracker

        tracker = get_tracker()
        user = None
        session = None

        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
        session = getattr(request, "analytics_session", None)

        # Track events
        for event_name in self.tracked_events:
            tracker.track_event(
                name=event_name,
                properties={
                    "view": self.__class__.__name__,
                    **self.track_properties,
                },
                user=user,
                session=session,
                request=request,
            )

        # Track page view
        if self.track_page_views:
            tracker.track_page_view(
                path=request.path,
                url=request.build_absolute_uri(),
                user=user,
                session=session,
                request=request,
            )


def _get_request(args: tuple, kwargs: dict):
    """Extract request object from arguments."""
    # Check kwargs
    if "request" in kwargs:
        return kwargs["request"]

    # Check positional args
    for arg in args:
        if hasattr(arg, "META") and hasattr(arg, "path"):
            return arg

    return None


def _serialize_arg(value: Any) -> Any:
    """Serialize an argument value for tracking."""
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (list, tuple)):
        return [_serialize_arg(v) for v in value[:10]]  # Limit list size

    if isinstance(value, dict):
        return {k: _serialize_arg(v) for k, v in list(value.items())[:10]}

    # For other objects, use string representation
    try:
        return str(value)[:200]  # Limit string length
    except Exception:
        return "<unserializable>"


__all__ = [
    "track_event",
    "track_timing",
    "track_page_view",
    "TrackedMixin",
]

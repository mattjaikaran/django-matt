"""
Experiment decorators.

Provides decorators for controlling behavior based on experiment assignments.

Usage:
    from django_matt.experiments import experiment, requires_experiment

    # Route to different handlers based on experiment variant
    @experiment("checkout_test", variant_handlers={
        "control": checkout_v1,
        "treatment": checkout_v2,
    })
    async def checkout(request):
        ...

    # Require user to be in an experiment
    @requires_experiment("beta_feature")
    async def beta_endpoint(request):
        ...
"""

import functools
import inspect
from typing import TYPE_CHECKING, Any, Callable

from django.http import HttpResponse, JsonResponse

if TYPE_CHECKING:
    from django.http import HttpRequest


def experiment(
    experiment_key: str,
    variant_handlers: dict[str, Callable] | None = None,
    default_variant: str | None = None,
    track_exposure: bool = True,
):
    """
    Decorator for A/B testing with variant-based routing.

    Routes to different handlers based on experiment variant assignment.

    Args:
        experiment_key: The experiment key
        variant_handlers: Dict mapping variant keys to handler functions
        default_variant: Default variant if not assigned
        track_exposure: Whether to track exposure events

    Returns:
        Decorated function

    Example:
        @experiment(
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
            from django_matt.experiments.context import ExperimentContext

            # Get or create context
            ctx = ExperimentContext.from_request(request)

            # Get variant assignment
            variant = ctx.get_variant(experiment_key, default=default_variant)

            # Track exposure if enabled
            if track_exposure and variant:
                ctx.track_exposure(experiment_key)

            # Route to variant handler
            if variant and variant in handlers:
                handler = handlers[variant]
                if inspect.iscoroutinefunction(handler):
                    return await handler(request, *args, **kwargs)
                return handler(request, *args, **kwargs)

            # Fall through to default handler
            return await func(request, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.experiments.context import ExperimentContext

            ctx = ExperimentContext.from_request(request)
            variant = ctx.get_variant(experiment_key, default=default_variant)

            if track_exposure and variant:
                ctx.track_exposure(experiment_key)

            if variant and variant in handlers:
                handler = handlers[variant]
                return handler(request, *args, **kwargs)

            return func(request, *args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def requires_experiment(
    experiment_key: str,
    allowed_variants: list[str] | None = None,
    status_code: int = 404,
    error_message: str = "Not available",
    error_code: str = "experiment_not_available",
):
    """
    Decorator that requires user to be assigned to an experiment.

    Returns an error response if the user is not in the experiment
    or not in an allowed variant.

    Args:
        experiment_key: The experiment key to require
        allowed_variants: List of variant keys to allow (None = any)
        status_code: HTTP status code for error response
        error_message: Error message to return
        error_code: Error code for the response

    Returns:
        Decorated function

    Example:
        @requires_experiment("beta_feature")
        async def beta_only_endpoint(request):
            ...

        @requires_experiment("checkout_test", allowed_variants=["treatment_a", "treatment_b"])
        async def new_checkout(request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.experiments.context import ExperimentContext

            ctx = ExperimentContext.from_request(request)
            assignment = ctx.get_assignment(experiment_key)

            if not assignment:
                return JsonResponse(
                    {"detail": error_message, "code": error_code},
                    status=status_code,
                )

            if allowed_variants and assignment.variant:
                if assignment.variant.key not in allowed_variants:
                    return JsonResponse(
                        {"detail": error_message, "code": error_code},
                        status=status_code,
                    )

            return await func(request, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(request: "HttpRequest", *args, **kwargs):
            from django_matt.experiments.context import ExperimentContext

            ctx = ExperimentContext.from_request(request)
            assignment = ctx.get_assignment(experiment_key)

            if not assignment:
                return JsonResponse(
                    {"detail": error_message, "code": error_code},
                    status=status_code,
                )

            if allowed_variants and assignment.variant:
                if assignment.variant.key not in allowed_variants:
                    return JsonResponse(
                        {"detail": error_message, "code": error_code},
                        status=status_code,
                    )

            return func(request, *args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def with_experiment_context(func: Callable) -> Callable:
    """
    Decorator that ensures ExperimentContext is available.

    Creates an ExperimentContext from the request and sets it as current.

    Example:
        @with_experiment_context
        async def my_view(request):
            from django_matt.experiments import get_variant
            variant = get_variant("my_experiment")
            ...
    """

    @functools.wraps(func)
    async def async_wrapper(request: "HttpRequest", *args, **kwargs):
        from django_matt.experiments.context import ExperimentContext

        ctx = ExperimentContext.from_request(request)
        with ctx:
            return await func(request, *args, **kwargs)

    @functools.wraps(func)
    def sync_wrapper(request: "HttpRequest", *args, **kwargs):
        from django_matt.experiments.context import ExperimentContext

        ctx = ExperimentContext.from_request(request)
        with ctx:
            return func(request, *args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def track_conversion(
    experiment_key: str,
    metric_name: str = "conversion",
    value: float = 1.0,
):
    """
    Decorator that tracks a conversion after the view executes.

    Tracks the conversion only if the response is successful (2xx status).

    Args:
        experiment_key: The experiment key
        metric_name: Name of the metric
        value: Metric value

    Example:
        @track_conversion("checkout_test", metric_name="purchase")
        async def complete_checkout(request):
            # Process checkout...
            return JsonResponse({"success": True})
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(request: "HttpRequest", *args, **kwargs):
            response = await func(request, *args, **kwargs)

            # Track conversion if response is successful
            if hasattr(response, "status_code") and 200 <= response.status_code < 300:
                from django_matt.experiments.context import ExperimentContext

                ctx = ExperimentContext.from_request(request)
                ctx.track_conversion(experiment_key, metric_name=metric_name, value=value)

            return response

        @functools.wraps(func)
        def sync_wrapper(request: "HttpRequest", *args, **kwargs):
            response = func(request, *args, **kwargs)

            if hasattr(response, "status_code") and 200 <= response.status_code < 300:
                from django_matt.experiments.context import ExperimentContext

                ctx = ExperimentContext.from_request(request)
                ctx.track_conversion(experiment_key, metric_name=metric_name, value=value)

            return response

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class ExperimentMixin:
    """
    Mixin for class-based views that adds experiment functionality.

    Usage:
        class MyView(ExperimentMixin, APIController):
            experiment_key = "my_experiment"

            async def get(self, request):
                variant = self.get_variant()
                if variant == "treatment":
                    ...
    """

    # Experiment key for this view
    experiment_key: str | None = None

    # Whether to auto-track exposure
    track_exposure: bool = True

    # Variant-specific handlers
    variant_handlers: dict[str, Callable] = {}

    @property
    def experiment_context(self):
        """Get the experiment context for this request."""
        if not hasattr(self, "_experiment_context"):
            from django_matt.experiments.context import ExperimentContext

            self._experiment_context = ExperimentContext.from_request(self.request)
        return self._experiment_context

    def get_assignment(self, experiment_key: str | None = None):
        """Get experiment assignment."""
        key = experiment_key or self.experiment_key
        if not key:
            return None
        return self.experiment_context.get_assignment(key)

    def get_variant(self, experiment_key: str | None = None, default: str | None = None) -> str | None:
        """Get variant key for the experiment."""
        key = experiment_key or self.experiment_key
        if not key:
            return default

        variant = self.experiment_context.get_variant(key, default=default)

        if self.track_exposure and variant:
            self.experiment_context.track_exposure(key)

        return variant

    def get_variant_payload(self, experiment_key: str | None = None) -> dict[str, Any]:
        """Get variant payload (configuration)."""
        key = experiment_key or self.experiment_key
        if not key:
            return {}
        return self.experiment_context.get_variant_payload(key)

    def track_conversion(
        self,
        experiment_key: str | None = None,
        metric_name: str = "conversion",
        value: float = 1.0,
    ):
        """Track a conversion event."""
        key = experiment_key or self.experiment_key
        if key:
            self.experiment_context.track_conversion(key, metric_name=metric_name, value=value)

    def is_in_variant(self, variant_key: str, experiment_key: str | None = None) -> bool:
        """Check if user is in a specific variant."""
        current_variant = self.get_variant(experiment_key)
        return current_variant == variant_key


__all__ = [
    "experiment",
    "requires_experiment",
    "with_experiment_context",
    "track_conversion",
    "ExperimentMixin",
]

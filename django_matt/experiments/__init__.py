"""
A/B Testing and Experiments for Django Matt.

A complete experimentation system with support for:
- Multi-armed bandit algorithms (epsilon-greedy, UCB, Thompson sampling)
- Statistical analysis (chi-square, t-tests, confidence intervals)
- Automatic winner detection with significance testing
- Experiment lifecycle management (draft, running, paused, completed)
- Mutual exclusion groups (user can only be in one experiment per group)
- Holdout groups for long-term analysis
- Integration with feature flags module
- REST API for experiment management
- Event tracking for conversions and revenue

Usage:
    # Get variant assignment
    from django_matt.experiments import get_variant

    variant = get_variant("checkout_experiment", user=request.user)
    if variant == "control":
        return checkout_v1()
    elif variant == "treatment":
        return checkout_v2()

    # Track conversion
    from django_matt.experiments import track_conversion

    track_conversion("checkout_experiment", user=request.user)

    # Using decorator
    from django_matt.experiments import experiment

    @experiment(
        "checkout_test",
        variant_handlers={
            "control": checkout_v1,
            "treatment": checkout_v2,
        },
    )
    async def checkout(request):
        # Default handler if no variant matches
        ...

    # Using context
    from django_matt.experiments import ExperimentContext

    ctx = ExperimentContext.from_request(request)
    variant = ctx.get_variant("my_experiment")
    ctx.track_conversion("my_experiment")

    # Register controllers
    from django_matt.experiments import ExperimentController
    api.register_controller(ExperimentController)

    # Statistical analysis
    from django_matt.experiments import analyze_experiment

    analysis = analyze_experiment(experiment)
    if analysis.has_winner:
        print(f"Winner: {analysis.winner_variant_key}")
        print(f"Confidence: {analysis.winner_confidence}")

Configuration (settings.py):
    # Backend selection
    EXPERIMENT_BACKEND = "database"  # or "redis"

    # Backend-specific settings
    EXPERIMENT_BACKEND_SETTINGS = {
        "database": {
            "cache_timeout": 60,
            "use_cache": True,
        },
        "redis": {
            "redis_url": "redis://localhost:6379/0",
            "cache_timeout": 300,
        },
    }

    # Middleware configuration
    EXPERIMENT_MIDDLEWARE = {
        "anonymous_id_cookie": "experiment_id",
        "cookie_max_age": 365 * 24 * 60 * 60,
        "expose_header": True,
        "auto_assign": False,
    }

    # Add middleware (after auth middleware)
    MIDDLEWARE = [
        ...
        'django_matt.experiments.ExperimentMiddleware',
        ...
    ]
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


# Lazy imports to avoid circular dependencies
def __getattr__(name: str):
    """Lazy import handler."""
    # Models
    if name == "Experiment":
        from django_matt.experiments.models import Experiment

        return Experiment
    if name == "Variant":
        from django_matt.experiments.models import Variant

        return Variant
    if name == "ExperimentAssignment":
        from django_matt.experiments.models import ExperimentAssignment

        return ExperimentAssignment
    if name == "ExperimentResult":
        from django_matt.experiments.models import ExperimentResult

        return ExperimentResult
    if name == "ExperimentAuditLog":
        from django_matt.experiments.models import ExperimentAuditLog

        return ExperimentAuditLog
    if name == "ExperimentStatus":
        from django_matt.experiments.models import ExperimentStatus

        return ExperimentStatus
    if name == "AssignmentStrategy":
        from django_matt.experiments.models import AssignmentStrategy

        return AssignmentStrategy
    if name == "MetricType":
        from django_matt.experiments.models import MetricType

        return MetricType

    # Context
    if name == "ExperimentContext":
        from django_matt.experiments.context import ExperimentContext

        return ExperimentContext
    if name == "get_current_context":
        from django_matt.experiments.context import get_current_context

        return get_current_context

    # Manager
    if name == "ExperimentManager":
        from django_matt.experiments.manager import ExperimentManager

        return ExperimentManager
    if name == "get_manager":
        from django_matt.experiments.manager import get_manager

        return get_manager

    # Decorators
    if name == "experiment":
        from django_matt.experiments.decorators import experiment

        return experiment
    if name == "requires_experiment":
        from django_matt.experiments.decorators import requires_experiment

        return requires_experiment
    if name == "with_experiment_context":
        from django_matt.experiments.decorators import with_experiment_context

        return with_experiment_context
    if name == "track_conversion_decorator":
        from django_matt.experiments.decorators import track_conversion

        return track_conversion
    if name == "ExperimentMixin":
        from django_matt.experiments.decorators import ExperimentMixin

        return ExperimentMixin

    # Middleware
    if name == "ExperimentMiddleware":
        from django_matt.experiments.middleware import ExperimentMiddleware

        return ExperimentMiddleware
    if name == "AsyncExperimentMiddleware":
        from django_matt.experiments.middleware import AsyncExperimentMiddleware

        return AsyncExperimentMiddleware

    # Backends
    if name == "ExperimentBackend":
        from django_matt.experiments.backends import ExperimentBackend

        return ExperimentBackend
    if name == "DatabaseBackend":
        from django_matt.experiments.backends import DatabaseBackend

        return DatabaseBackend
    if name == "RedisBackend":
        from django_matt.experiments.backends import RedisBackend

        return RedisBackend
    if name == "MemoryBackend":
        from django_matt.experiments.backends import MemoryBackend

        return MemoryBackend
    if name == "get_backend":
        from django_matt.experiments.backends import get_backend

        return get_backend

    # Analysis
    if name == "StatisticalAnalyzer":
        from django_matt.experiments.analysis import StatisticalAnalyzer

        return StatisticalAnalyzer
    if name == "ExperimentAnalysis":
        from django_matt.experiments.analysis import ExperimentAnalysis

        return ExperimentAnalysis
    if name == "VariantStats":
        from django_matt.experiments.analysis import VariantStats

        return VariantStats
    if name == "ComparisonResult":
        from django_matt.experiments.analysis import ComparisonResult

        return ComparisonResult
    if name == "analyze_experiment":
        from django_matt.experiments.analysis import analyze_experiment

        return analyze_experiment

    # Controllers
    if name == "ExperimentController":
        from django_matt.experiments.controllers import ExperimentController

        return ExperimentController
    if name == "ExperimentAssignmentController":
        from django_matt.experiments.controllers import ExperimentAssignmentController

        return ExperimentAssignmentController

    # Aliases for main module exports
    if name == "get_experiment_variant":
        from django_matt.experiments.manager import get_variant_key

        return get_variant_key
    if name == "track_experiment_conversion":
        from django_matt.experiments.manager import track_conversion

        return track_conversion

    raise AttributeError(f"module 'django_matt.experiments' has no attribute {name!r}")


# Convenience functions that use the default manager


def get_assignment(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    create: bool = True,
    context: dict[str, Any] | None = None,
):
    """
    Get or create an experiment assignment.

    Args:
        experiment_key: Experiment key
        user: Authenticated user (optional)
        anonymous_id: Anonymous identifier (optional)
        create: Whether to create assignment if not exists
        context: Additional context for targeting

    Returns:
        ExperimentAssignment or None

    Example:
        assignment = get_assignment("checkout_test", user=request.user)
        if assignment:
            print(f"Assigned to: {assignment.variant.key}")
    """
    from django_matt.experiments.manager import get_assignment as _get_assignment

    return _get_assignment(
        experiment_key=experiment_key,
        user=user,
        anonymous_id=anonymous_id,
        create=create,
        context=context,
    )


def get_variant(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    create: bool = True,
    context: dict[str, Any] | None = None,
    default: str | None = None,
) -> str | None:
    """
    Get variant key for an experiment.

    Args:
        experiment_key: Experiment key
        user: Authenticated user (optional)
        anonymous_id: Anonymous identifier (optional)
        create: Whether to create assignment if not exists
        context: Additional context for targeting
        default: Default value if not assigned

    Returns:
        Variant key or default

    Example:
        variant = get_variant("checkout_test", user=request.user)
        if variant == "control":
            return checkout_v1()
        elif variant == "treatment":
            return checkout_v2()
    """
    from django_matt.experiments.manager import get_variant_key

    return get_variant_key(
        experiment_key=experiment_key,
        user=user,
        anonymous_id=anonymous_id,
        create=create,
        context=context,
        default=default,
    )


def track_conversion(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    metric_name: str = "conversion",
    value: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Track a conversion event for an experiment.

    Args:
        experiment_key: Experiment key
        user: Authenticated user (optional)
        anonymous_id: Anonymous identifier (optional)
        metric_name: Name of the metric (default: "conversion")
        value: Metric value (default: 1.0 for binary conversion)
        metadata: Additional event data

    Returns:
        True if event was tracked

    Example:
        # After successful checkout
        track_conversion("checkout_test", user=request.user)

        # With custom metric
        track_conversion(
            "checkout_test",
            user=request.user,
            metric_name="add_to_cart",
        )
    """
    from django_matt.experiments.manager import track_conversion as _track_conversion

    return _track_conversion(
        experiment_key=experiment_key,
        user=user,
        anonymous_id=anonymous_id,
        metric_name=metric_name,
        value=value,
        metadata=metadata,
    )


def track_revenue(
    experiment_key: str,
    amount: float,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    metric_name: str = "revenue",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Track a revenue event for an experiment.

    Args:
        experiment_key: Experiment key
        amount: Revenue amount
        user: Authenticated user (optional)
        anonymous_id: Anonymous identifier (optional)
        metric_name: Name of the metric (default: "revenue")
        metadata: Additional event data

    Returns:
        True if event was tracked

    Example:
        track_revenue(
            "checkout_test",
            amount=99.99,
            user=request.user,
        )
    """
    from django_matt.experiments.manager import track_revenue as _track_revenue

    return _track_revenue(
        experiment_key=experiment_key,
        amount=amount,
        user=user,
        anonymous_id=anonymous_id,
        metric_name=metric_name,
        metadata=metadata,
    )


__all__ = [
    # Convenience functions
    "get_assignment",
    "get_variant",
    "track_conversion",
    "track_revenue",
    # Aliases for main module
    "get_experiment_variant",
    "track_experiment_conversion",
    # Models
    "Experiment",
    "Variant",
    "ExperimentAssignment",
    "ExperimentResult",
    "ExperimentAuditLog",
    "ExperimentStatus",
    "AssignmentStrategy",
    "MetricType",
    # Context
    "ExperimentContext",
    "get_current_context",
    # Manager
    "ExperimentManager",
    "get_manager",
    # Decorators
    "experiment",
    "requires_experiment",
    "with_experiment_context",
    "track_conversion_decorator",
    "ExperimentMixin",
    # Middleware
    "ExperimentMiddleware",
    "AsyncExperimentMiddleware",
    # Backends
    "ExperimentBackend",
    "DatabaseBackend",
    "RedisBackend",
    "MemoryBackend",
    "get_backend",
    # Analysis
    "StatisticalAnalyzer",
    "ExperimentAnalysis",
    "VariantStats",
    "ComparisonResult",
    "analyze_experiment",
    # Controllers
    "ExperimentController",
    "ExperimentAssignmentController",
]

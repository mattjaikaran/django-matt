# file-length-max: 450
"""
Experiment context management.

Provides ExperimentContext for managing experiment assignments and tracking.

Usage:
    from django_matt.experiments.context import ExperimentContext

    # Create context from request
    ctx = ExperimentContext.from_request(request)

    # Get variant assignment
    variant = ctx.get_variant("checkout_experiment")

    # Track conversion
    ctx.track_conversion("checkout_experiment")
"""

import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.http import HttpRequest

    from django_matt.experiments.models import (
        ExperimentAssignment,
    )

# Context variable for current experiment context
_current_context: contextvars.ContextVar["ExperimentContext | None"] = contextvars.ContextVar(
    "experiment_context", default=None
)


@dataclass
class ExperimentContext:
    """
    Context for experiment assignments and tracking.

    Holds user, organization, and custom attributes for experiment evaluation.
    Can be created from a request or manually for testing.
    """

    user: "AbstractUser | None" = None
    anonymous_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    _manager: Any = None  # Lazy manager reference
    _assignment_cache: dict[str, "ExperimentAssignment | None"] = field(default_factory=dict)

    @classmethod
    def from_request(cls, request: "HttpRequest") -> "ExperimentContext":
        """
        Create an ExperimentContext from an HTTP request.

        Extracts user and anonymous ID from the request.
        """
        import secrets

        user = None
        anonymous_id = None
        attributes = {}

        # Get user if authenticated
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user

            # Add user attributes
            if hasattr(user, "email"):
                attributes["email"] = user.email
            if hasattr(user, "is_staff"):
                attributes["is_staff"] = user.is_staff
            if hasattr(user, "date_joined"):
                from django.utils import timezone

                attributes["days_since_signup"] = (timezone.now() - user.date_joined).days
        else:
            # Try to get anonymous ID from cookie or create new one
            anonymous_id = request.COOKIES.get("experiment_id")
            if not anonymous_id:
                # Check for session-based ID
                if hasattr(request, "session"):
                    anonymous_id = request.session.get("experiment_id")
                    if not anonymous_id:
                        anonymous_id = secrets.token_hex(16)
                        request.session["experiment_id"] = anonymous_id
                else:
                    anonymous_id = secrets.token_hex(16)

        # Add request attributes
        attributes["path"] = request.path
        attributes["method"] = request.method

        # Add header-based attributes
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        attributes["user_agent"] = user_agent
        attributes["is_mobile"] = any(
            x in user_agent.lower() for x in ["mobile", "android", "iphone", "ipad"]
        )

        return cls(user=user, anonymous_id=anonymous_id, attributes=attributes)

    @classmethod
    def current(cls) -> "ExperimentContext | None":
        """Get the current experiment context from context var."""
        return _current_context.get()

    @classmethod
    def set_current(cls, context: "ExperimentContext | None"):
        """Set the current experiment context."""
        _current_context.set(context)

    @property
    def manager(self):
        """Get the experiment manager."""
        if self._manager is None:
            from django_matt.experiments.manager import get_manager

            self._manager = get_manager()
        return self._manager

    def get_assignment(
        self,
        experiment_key: str,
        create: bool = True,
    ) -> "ExperimentAssignment | None":
        """
        Get experiment assignment for this context.

        Args:
            experiment_key: Experiment key
            create: Whether to create assignment if not exists

        Returns:
            ExperimentAssignment or None
        """
        # Check cache
        cache_key = f"{experiment_key}:{create}"
        if cache_key in self._assignment_cache:
            return self._assignment_cache[cache_key]

        assignment = self.manager.get_assignment(
            experiment_key=experiment_key,
            user=self.user,
            anonymous_id=self.anonymous_id,
            create=create,
            context=self.attributes,
        )

        self._assignment_cache[cache_key] = assignment
        return assignment

    def get_variant(
        self,
        experiment_key: str,
        default: str | None = None,
        create: bool = True,
    ) -> str | None:
        """
        Get variant key for an experiment.

        Args:
            experiment_key: Experiment key
            default: Default value if not assigned
            create: Whether to create assignment if not exists

        Returns:
            Variant key or default
        """
        return self.manager.get_variant_key(
            experiment_key=experiment_key,
            user=self.user,
            anonymous_id=self.anonymous_id,
            create=create,
            context=self.attributes,
            default=default,
        )

    def get_variant_payload(
        self,
        experiment_key: str,
        create: bool = True,
    ) -> dict[str, Any]:
        """
        Get variant payload (configuration) for an experiment.

        Args:
            experiment_key: Experiment key
            create: Whether to create assignment if not exists

        Returns:
            Variant payload dict or empty dict
        """
        assignment = self.get_assignment(experiment_key, create=create)

        if assignment and assignment.variant:
            return assignment.variant.payload or {}

        return {}

    def is_in_experiment(
        self,
        experiment_key: str,
        create: bool = False,
    ) -> bool:
        """
        Check if context is assigned to an experiment.

        Args:
            experiment_key: Experiment key
            create: Whether to create assignment if not exists

        Returns:
            True if assigned to experiment
        """
        assignment = self.get_assignment(experiment_key, create=create)
        return assignment is not None

    def is_in_variant(
        self,
        experiment_key: str,
        variant_key: str,
        create: bool = True,
    ) -> bool:
        """
        Check if context is assigned to a specific variant.

        Args:
            experiment_key: Experiment key
            variant_key: Variant key to check
            create: Whether to create assignment if not exists

        Returns:
            True if assigned to the specified variant
        """
        current_variant = self.get_variant(experiment_key, create=create)
        return current_variant == variant_key

    def track_exposure(
        self,
        experiment_key: str,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Track exposure to an experiment.

        Call this when the user actually sees the variant.

        Args:
            experiment_key: Experiment key
            metadata: Additional metadata
        """
        self.manager.track_conversion(
            experiment_key=experiment_key,
            user=self.user,
            anonymous_id=self.anonymous_id,
            metric_name="exposure",
            value=1.0,
            metadata=metadata,
        )

    def track_conversion(
        self,
        experiment_key: str,
        metric_name: str = "conversion",
        value: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Track a conversion event.

        Args:
            experiment_key: Experiment key
            metric_name: Name of the metric
            value: Metric value (1.0 for binary conversion)
            metadata: Additional metadata
        """
        self.manager.track_conversion(
            experiment_key=experiment_key,
            user=self.user,
            anonymous_id=self.anonymous_id,
            metric_name=metric_name,
            value=value,
            metadata=metadata,
        )

    def track_revenue(
        self,
        experiment_key: str,
        amount: float,
        metric_name: str = "revenue",
        metadata: dict[str, Any] | None = None,
    ):
        """
        Track a revenue event.

        Args:
            experiment_key: Experiment key
            amount: Revenue amount
            metric_name: Name of the metric
            metadata: Additional metadata
        """
        self.manager.track_revenue(
            experiment_key=experiment_key,
            amount=amount,
            user=self.user,
            anonymous_id=self.anonymous_id,
            metric_name=metric_name,
            metadata=metadata,
        )

    def get_all_experiments(self) -> dict[str, str | None]:
        """
        Get all running experiments and their variant assignments.

        Returns:
            Dict of experiment_key -> variant_key (or None for holdout)
        """
        from django_matt.experiments.models import Experiment, ExperimentStatus

        experiments = Experiment.objects.filter(status=ExperimentStatus.RUNNING.value)

        result = {}
        for exp in experiments:
            variant = self.get_variant(exp.key, create=True)
            result[exp.key] = variant

        return result

    def with_attributes(self, **attributes) -> "ExperimentContext":
        """
        Create a new context with additional attributes.

        Args:
            **attributes: Additional attributes to add

        Returns:
            New ExperimentContext with merged attributes
        """
        merged = {**self.attributes, **attributes}
        return ExperimentContext(
            user=self.user,
            anonymous_id=self.anonymous_id,
            attributes=merged,
            _manager=self._manager,
        )

    def with_user(self, user: "AbstractUser") -> "ExperimentContext":
        """
        Create a new context with a different user.

        Args:
            user: User to use

        Returns:
            New ExperimentContext with the user
        """
        return ExperimentContext(
            user=user,
            anonymous_id=None,
            attributes=self.attributes,
            _manager=self._manager,
        )

    def with_anonymous_id(self, anonymous_id: str) -> "ExperimentContext":
        """
        Create a new context with a different anonymous ID.

        Args:
            anonymous_id: Anonymous ID to use

        Returns:
            New ExperimentContext with the anonymous ID
        """
        return ExperimentContext(
            user=None,
            anonymous_id=anonymous_id,
            attributes=self.attributes,
            _manager=self._manager,
        )

    def __enter__(self):
        """Enter context manager - set as current context."""
        self._token = _current_context.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - restore previous context."""
        _current_context.reset(self._token)
        return False


def get_current_context() -> ExperimentContext | None:
    """Get the current experiment context."""
    return _current_context.get()


def set_current_context(context: ExperimentContext | None):
    """Set the current experiment context."""
    _current_context.set(context)


__all__ = [
    "ExperimentContext",
    "get_current_context",
    "set_current_context",
]

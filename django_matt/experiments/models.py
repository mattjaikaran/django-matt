"""
Experiment models for A/B testing.

Provides Experiment, Variant, ExperimentAssignment, and ExperimentResult models
for comprehensive A/B testing and experimentation.
"""

import hashlib
import secrets
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class ExperimentStatus(str, Enum):
    """Status of an experiment."""

    DRAFT = "draft"  # Not yet running
    RUNNING = "running"  # Actively collecting data
    PAUSED = "paused"  # Temporarily stopped
    COMPLETED = "completed"  # Finished with results
    ARCHIVED = "archived"  # No longer active

    @classmethod
    def choices(cls):
        return [(s.value, s.name.title()) for s in cls]


class AssignmentStrategy(str, Enum):
    """Strategy for assigning users to variants."""

    RANDOM = "random"  # Random assignment based on weights
    EPSILON_GREEDY = "epsilon_greedy"  # Explore with epsilon, exploit best
    UCB = "ucb"  # Upper Confidence Bound
    THOMPSON = "thompson"  # Thompson Sampling

    @classmethod
    def choices(cls):
        return [(s.value, s.name.replace("_", " ").title()) for s in cls]


class MetricType(str, Enum):
    """Type of metric being tracked."""

    CONVERSION = "conversion"  # Binary (did/didn't convert)
    REVENUE = "revenue"  # Continuous (revenue amount)
    COUNT = "count"  # Count of events
    DURATION = "duration"  # Time-based metric

    @classmethod
    def choices(cls):
        return [(t.value, t.name.title()) for t in cls]


class ExperimentManager(models.Manager):
    """Custom manager for Experiment with common queries."""

    def active(self) -> models.QuerySet:
        """Get running experiments."""
        return self.filter(status=ExperimentStatus.RUNNING.value)

    def by_key(self, key: str) -> "Experiment | None":
        """Get experiment by key."""
        try:
            return self.get(key=key)
        except self.model.DoesNotExist:
            return None

    def for_user(self, user: "AbstractUser") -> models.QuerySet:
        """Get experiments a user is eligible for."""
        return self.filter(
            status=ExperimentStatus.RUNNING.value,
        )


class Experiment(models.Model):
    """
    A/B test experiment.

    Manages the lifecycle of an experiment from draft to completion,
    including variant configuration and statistical settings.

    Attributes:
        key: Unique identifier for the experiment
        name: Human-readable name
        description: Description of hypothesis and goals
        status: Current experiment status
        strategy: Assignment strategy (random, epsilon-greedy, UCB, Thompson)
        start_date: When the experiment started
        end_date: When the experiment ended or is scheduled to end
        min_sample_size: Minimum sample size per variant
        target_confidence: Required confidence level (e.g., 0.95)
        primary_metric: Name of the primary success metric
        secondary_metrics: Additional metrics to track
        exclusion_group: Mutual exclusion group name
        holdout_percentage: Percentage of users in holdout group
        targeting_rules: Rules for experiment eligibility
        metadata: Additional configuration data
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique identifier for the experiment",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Description of hypothesis and goals",
    )
    status = models.CharField(
        max_length=20,
        choices=ExperimentStatus.choices(),
        default=ExperimentStatus.DRAFT.value,
        db_index=True,
    )
    strategy = models.CharField(
        max_length=20,
        choices=AssignmentStrategy.choices(),
        default=AssignmentStrategy.RANDOM.value,
        help_text="Strategy for assigning users to variants",
    )

    # Timing
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the experiment started",
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the experiment ended or is scheduled to end",
    )

    # Statistical settings
    min_sample_size = models.IntegerField(
        default=100,
        help_text="Minimum sample size per variant before analysis",
    )
    target_confidence = models.FloatField(
        default=0.95,
        help_text="Required confidence level (0.0-1.0)",
    )

    # Metrics
    primary_metric = models.CharField(
        max_length=255,
        default="conversion",
        help_text="Name of the primary success metric",
    )
    secondary_metrics = models.JSONField(
        default=list,
        blank=True,
        help_text="List of secondary metric names",
    )

    # Exclusion and targeting
    exclusion_group = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Mutual exclusion group - user can only be in one experiment per group",
    )
    holdout_percentage = models.FloatField(
        default=0.0,
        help_text="Percentage of users in holdout group (0.0-1.0)",
    )
    targeting_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="Rules for experiment eligibility",
    )

    # Multi-armed bandit settings
    epsilon = models.FloatField(
        default=0.1,
        help_text="Exploration rate for epsilon-greedy (0.0-1.0)",
    )
    exploration_weight = models.FloatField(
        default=2.0,
        help_text="Exploration weight for UCB algorithm",
    )

    # Winner detection
    winner_variant_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of winning variant if determined",
    )
    winner_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence level when winner was determined",
    )
    winner_detected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Feature flag integration
    feature_flag_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Associated feature flag key",
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_experiments",
    )

    objects = ExperimentManager()

    class Meta:
        app_label = "django_matt"
        ordering = ["-created_at"]
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["status"]),
            models.Index(fields=["exclusion_group"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.key} ({self.status})"

    @property
    def is_running(self) -> bool:
        """Check if experiment is currently running."""
        if self.status != ExperimentStatus.RUNNING.value:
            return False
        now = timezone.now()
        if self.end_date and now >= self.end_date:
            return False
        return True

    @property
    def status_enum(self) -> ExperimentStatus:
        return ExperimentStatus(self.status)

    @property
    def strategy_enum(self) -> AssignmentStrategy:
        return AssignmentStrategy(self.strategy)

    @property
    def has_winner(self) -> bool:
        """Check if a winner has been determined."""
        return self.winner_variant_id is not None

    @property
    def total_participants(self) -> int:
        """Get total number of participants."""
        return self.assignments.count()

    def get_variant_weights(self) -> dict[str, float]:
        """Get current variant weights based on strategy."""
        variants = list(self.variants.all())
        if not variants:
            return {}

        if self.strategy == AssignmentStrategy.RANDOM.value:
            return {str(v.id): v.weight for v in variants}

        # For bandit algorithms, calculate dynamic weights
        from django_matt.experiments.manager import ExperimentManager as EM

        manager = EM()
        return manager.get_bandit_weights(self)

    def start(self):
        """Start the experiment."""
        if self.status != ExperimentStatus.DRAFT.value:
            raise ValueError(f"Cannot start experiment in {self.status} status")

        if not self.variants.exists():
            raise ValueError("Experiment must have at least one variant")

        self.status = ExperimentStatus.RUNNING.value
        self.start_date = timezone.now()
        self.save(update_fields=["status", "start_date", "updated_at"])

    def pause(self):
        """Pause the experiment."""
        if self.status != ExperimentStatus.RUNNING.value:
            raise ValueError(f"Cannot pause experiment in {self.status} status")

        self.status = ExperimentStatus.PAUSED.value
        self.save(update_fields=["status", "updated_at"])

    def resume(self):
        """Resume a paused experiment."""
        if self.status != ExperimentStatus.PAUSED.value:
            raise ValueError(f"Cannot resume experiment in {self.status} status")

        self.status = ExperimentStatus.RUNNING.value
        self.save(update_fields=["status", "updated_at"])

    def complete(self, winner_variant: "Variant | None" = None, confidence: float | None = None):
        """Complete the experiment with optional winner."""
        self.status = ExperimentStatus.COMPLETED.value
        self.end_date = timezone.now()

        if winner_variant:
            self.winner_variant_id = winner_variant.id
            self.winner_confidence = confidence
            self.winner_detected_at = timezone.now()

        self.save(update_fields=[
            "status", "end_date", "winner_variant_id",
            "winner_confidence", "winner_detected_at", "updated_at"
        ])


class Variant(models.Model):
    """
    A variant (treatment) in an experiment.

    Each experiment has multiple variants including a control.

    Attributes:
        experiment: The parent experiment
        key: Unique key within the experiment
        name: Human-readable name
        description: Description of the variant
        is_control: Whether this is the control variant
        weight: Weight for random assignment
        payload: Variant-specific configuration
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    key = models.CharField(
        max_length=100,
        help_text="Unique key within the experiment",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name",
    )
    description = models.TextField(
        blank=True,
        default="",
    )
    is_control = models.BooleanField(
        default=False,
        help_text="Whether this is the control variant",
    )
    weight = models.IntegerField(
        default=1,
        help_text="Weight for random assignment",
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Variant-specific configuration",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["-is_control", "key"]
        verbose_name = "Variant"
        verbose_name_plural = "Variants"
        unique_together = [["experiment", "key"]]
        indexes = [
            models.Index(fields=["experiment", "key"]),
        ]

    def __str__(self):
        control_str = " (control)" if self.is_control else ""
        return f"{self.experiment.key}/{self.key}{control_str}"

    @property
    def assignment_count(self) -> int:
        """Number of users assigned to this variant."""
        return self.assignments.count()

    @property
    def conversion_count(self) -> int:
        """Number of conversions for this variant."""
        return self.results.filter(
            metric_type=MetricType.CONVERSION.value,
            value__gt=0,
        ).count()

    @property
    def conversion_rate(self) -> float:
        """Conversion rate for this variant."""
        total = self.assignment_count
        if total == 0:
            return 0.0
        conversions = self.conversion_count
        return conversions / total


class ExperimentAssignment(models.Model):
    """
    Assignment of a user to an experiment variant.

    Tracks which variant a user was assigned to for an experiment.

    Attributes:
        experiment: The experiment
        variant: The assigned variant
        user: The assigned user (optional)
        anonymous_id: Anonymous identifier for non-logged-in users
        assigned_at: When the assignment was made
        is_holdout: Whether this user is in the holdout group
        context: Additional context at time of assignment
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    variant = models.ForeignKey(
        Variant,
        on_delete=models.CASCADE,
        related_name="assignments",
        null=True,  # Null for holdout group
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="experiment_assignments",
    )
    anonymous_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Anonymous identifier for non-logged-in users",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_holdout = models.BooleanField(
        default=False,
        help_text="Whether this user is in the holdout group",
    )
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context at time of assignment",
    )

    class Meta:
        app_label = "django_matt"
        ordering = ["-assigned_at"]
        verbose_name = "Experiment Assignment"
        verbose_name_plural = "Experiment Assignments"
        indexes = [
            models.Index(fields=["experiment", "user"]),
            models.Index(fields=["experiment", "anonymous_id"]),
            models.Index(fields=["variant"]),
            models.Index(fields=["assigned_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["experiment", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_experiment_user",
            ),
            models.UniqueConstraint(
                fields=["experiment", "anonymous_id"],
                condition=models.Q(anonymous_id__gt=""),
                name="unique_experiment_anonymous",
            ),
        ]

    def __str__(self):
        user_str = str(self.user_id) if self.user_id else self.anonymous_id[:8]
        variant_str = self.variant.key if self.variant else "holdout"
        return f"{self.experiment.key}: {user_str} -> {variant_str}"

    @property
    def identifier(self) -> str:
        """Get the user identifier (user ID or anonymous ID)."""
        if self.user_id:
            return str(self.user_id)
        return self.anonymous_id


class ExperimentResult(models.Model):
    """
    Result/event tracked for an experiment.

    Tracks conversions, revenue, and other metrics for experiment analysis.

    Attributes:
        assignment: The experiment assignment
        variant: The variant (denormalized for query performance)
        metric_name: Name of the metric
        metric_type: Type of metric (conversion, revenue, count, duration)
        value: The metric value
        timestamp: When the event occurred
        metadata: Additional event data
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    assignment = models.ForeignKey(
        ExperimentAssignment,
        on_delete=models.CASCADE,
        related_name="results",
    )
    variant = models.ForeignKey(
        Variant,
        on_delete=models.CASCADE,
        related_name="results",
        null=True,
        blank=True,
    )
    metric_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Name of the metric",
    )
    metric_type = models.CharField(
        max_length=20,
        choices=MetricType.choices(),
        default=MetricType.CONVERSION.value,
    )
    value = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=Decimal("1.0"),
        help_text="Metric value (1.0 for conversion events)",
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        app_label = "django_matt"
        ordering = ["-timestamp"]
        verbose_name = "Experiment Result"
        verbose_name_plural = "Experiment Results"
        indexes = [
            models.Index(fields=["assignment", "metric_name"]),
            models.Index(fields=["variant", "metric_name"]),
            models.Index(fields=["metric_name", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.assignment.experiment.key}: {self.metric_name}={self.value}"


class ExperimentAuditLog(models.Model):
    """
    Audit log for experiment changes.

    Records all changes to experiments for compliance and debugging.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
    )
    experiment_key = models.CharField(
        max_length=255,
        help_text="Experiment key (preserved if deleted)",
    )
    action = models.CharField(
        max_length=50,
        db_index=True,
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
    )
    old_values = models.JSONField(
        default=dict,
        blank=True,
    )
    new_values = models.JSONField(
        default=dict,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="experiment_audit_logs",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["-created_at"]
        verbose_name = "Experiment Audit Log"
        verbose_name_plural = "Experiment Audit Logs"

    def __str__(self):
        return f"{self.experiment_key} - {self.action}"

    @classmethod
    def log(
        cls,
        experiment: Experiment,
        action: str,
        changes: dict | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        user: "AbstractUser | None" = None,
        ip_address: str | None = None,
    ) -> "ExperimentAuditLog":
        """Create an audit log entry."""
        return cls.objects.create(
            experiment=experiment,
            experiment_key=experiment.key,
            action=action,
            changes=changes or {},
            old_values=old_values or {},
            new_values=new_values or {},
            user=user,
            ip_address=ip_address,
        )


__all__ = [
    "ExperimentStatus",
    "AssignmentStrategy",
    "MetricType",
    "Experiment",
    "Variant",
    "ExperimentAssignment",
    "ExperimentResult",
    "ExperimentAuditLog",
]

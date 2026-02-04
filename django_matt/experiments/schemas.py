"""
Pydantic schemas for experiments API.

Provides request/response schemas for the experiments REST API.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class ExperimentStatusEnum(str, Enum):
    """Status of an experiment."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class AssignmentStrategyEnum(str, Enum):
    """Strategy for assigning users to variants."""

    RANDOM = "random"
    EPSILON_GREEDY = "epsilon_greedy"
    UCB = "ucb"
    THOMPSON = "thompson"


class MetricTypeEnum(str, Enum):
    """Type of metric."""

    CONVERSION = "conversion"
    REVENUE = "revenue"
    COUNT = "count"
    DURATION = "duration"


# -----------------------------------------------------------------------------
# Variant Schemas
# -----------------------------------------------------------------------------


class VariantBase(BaseModel):
    """Base schema for variants."""

    key: str = Field(..., min_length=1, max_length=100, description="Unique key")
    name: str = Field(..., min_length=1, max_length=255, description="Display name")
    description: str = Field(default="", description="Description")
    is_control: bool = Field(default=False, description="Whether this is control")
    weight: int = Field(default=1, ge=0, description="Assignment weight")
    payload: dict[str, Any] = Field(default_factory=dict, description="Configuration")


class VariantCreate(VariantBase):
    """Schema for creating a variant."""


class VariantUpdate(BaseModel):
    """Schema for updating a variant."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    weight: int | None = Field(default=None, ge=0)
    payload: dict[str, Any] | None = None


class VariantResponse(VariantBase):
    """Schema for variant response."""

    id: str
    assignment_count: int = Field(default=0, description="Number of assignments")
    conversion_count: int = Field(default=0, description="Number of conversions")
    conversion_rate: float = Field(default=0.0, description="Conversion rate")

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Experiment Schemas
# -----------------------------------------------------------------------------


class TargetingRule(BaseModel):
    """Schema for a targeting rule."""

    attribute: str = Field(..., description="Attribute to check")
    operator: str = Field(default="eq", description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")


class ExperimentBase(BaseModel):
    """Base schema for experiments."""

    key: str = Field(..., min_length=1, max_length=255, description="Unique identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Display name")
    description: str = Field(default="", description="Hypothesis and goals")
    strategy: AssignmentStrategyEnum = Field(
        default=AssignmentStrategyEnum.RANDOM,
        description="Assignment strategy",
    )
    min_sample_size: int = Field(default=100, ge=1, description="Min samples per variant")
    target_confidence: float = Field(
        default=0.95, ge=0.5, le=0.99, description="Target confidence level"
    )
    primary_metric: str = Field(default="conversion", description="Primary metric")
    secondary_metrics: list[str] = Field(default_factory=list, description="Secondary metrics")
    exclusion_group: str = Field(default="", description="Mutual exclusion group")
    holdout_percentage: float = Field(default=0.0, ge=0.0, le=1.0, description="Holdout percentage")
    targeting_rules: list[TargetingRule] = Field(
        default_factory=list, description="Targeting rules"
    )
    epsilon: float = Field(default=0.1, ge=0.0, le=1.0, description="Epsilon for epsilon-greedy")
    exploration_weight: float = Field(default=2.0, ge=0.0, description="UCB exploration weight")
    feature_flag_key: str = Field(default="", description="Associated feature flag")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ExperimentCreate(ExperimentBase):
    """Schema for creating an experiment."""

    variants: list[VariantCreate] = Field(default_factory=list, description="Initial variants")
    scheduled_start: datetime | None = Field(default=None, description="Scheduled start")
    scheduled_end: datetime | None = Field(default=None, description="Scheduled end")


class ExperimentUpdate(BaseModel):
    """Schema for updating an experiment."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    strategy: AssignmentStrategyEnum | None = None
    min_sample_size: int | None = Field(default=None, ge=1)
    target_confidence: float | None = Field(default=None, ge=0.5, le=0.99)
    primary_metric: str | None = None
    secondary_metrics: list[str] | None = None
    exclusion_group: str | None = None
    holdout_percentage: float | None = Field(default=None, ge=0.0, le=1.0)
    targeting_rules: list[TargetingRule] | None = None
    epsilon: float | None = Field(default=None, ge=0.0, le=1.0)
    exploration_weight: float | None = Field(default=None, ge=0.0)
    scheduled_end: datetime | None = None
    feature_flag_key: str | None = None
    metadata: dict[str, Any] | None = None


class ExperimentResponse(ExperimentBase):
    """Schema for experiment response."""

    id: str
    status: ExperimentStatusEnum
    start_date: datetime | None = None
    end_date: datetime | None = None
    winner_variant_id: str | None = None
    winner_confidence: float | None = None
    winner_detected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by_id: str | None = None
    variants: list[VariantResponse] = Field(default_factory=list)
    total_participants: int = 0
    is_running: bool = False
    has_winner: bool = False

    class Config:
        from_attributes = True


class ExperimentListResponse(BaseModel):
    """List of experiments response."""

    items: list[ExperimentResponse]
    total: int
    page: int = 1
    page_size: int = 20


# -----------------------------------------------------------------------------
# Assignment Schemas
# -----------------------------------------------------------------------------


class AssignmentContext(BaseModel):
    """Context for experiment assignment."""

    user_id: str | None = Field(default=None, description="User ID")
    anonymous_id: str | None = Field(default=None, description="Anonymous identifier")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Custom attributes")


class AssignmentRequest(BaseModel):
    """Request for getting/creating an assignment."""

    experiment_key: str = Field(..., description="Experiment key")
    context: AssignmentContext = Field(default_factory=AssignmentContext)
    create: bool = Field(default=True, description="Create if not exists")


class AssignmentResponse(BaseModel):
    """Response for experiment assignment."""

    experiment_key: str
    variant_key: str | None = None
    variant_id: str | None = None
    is_holdout: bool = False
    assigned_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict, description="Variant payload")


class BulkAssignmentRequest(BaseModel):
    """Request for multiple experiment assignments."""

    experiment_keys: list[str] = Field(default_factory=list)
    context: AssignmentContext = Field(default_factory=AssignmentContext)
    include_all_running: bool = Field(default=False, description="Include all running experiments")


class BulkAssignmentResponse(BaseModel):
    """Response for multiple experiment assignments."""

    assignments: dict[str, AssignmentResponse]


# -----------------------------------------------------------------------------
# Event Tracking Schemas
# -----------------------------------------------------------------------------


class ConversionEvent(BaseModel):
    """Schema for tracking a conversion event."""

    experiment_key: str = Field(..., description="Experiment key")
    metric_name: str = Field(default="conversion", description="Metric name")
    value: float = Field(default=1.0, description="Metric value")
    user_id: str | None = Field(default=None, description="User ID")
    anonymous_id: str | None = Field(default=None, description="Anonymous identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Event metadata")


class RevenueEvent(BaseModel):
    """Schema for tracking a revenue event."""

    experiment_key: str = Field(..., description="Experiment key")
    amount: float = Field(..., ge=0, description="Revenue amount")
    metric_name: str = Field(default="revenue", description="Metric name")
    user_id: str | None = Field(default=None, description="User ID")
    anonymous_id: str | None = Field(default=None, description="Anonymous identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Event metadata")


class EventResponse(BaseModel):
    """Response for event tracking."""

    success: bool
    message: str = ""


# -----------------------------------------------------------------------------
# Analysis Schemas
# -----------------------------------------------------------------------------


class VariantStatsResponse(BaseModel):
    """Statistics for a variant."""

    variant_id: str
    variant_key: str
    is_control: bool
    sample_size: int
    conversions: int = 0
    conversion_rate: float = 0.0
    total_value: float = 0.0
    mean_value: float = 0.0
    confidence_interval_lower: float = 0.0
    confidence_interval_upper: float = 0.0


class ComparisonResponse(BaseModel):
    """Result of comparing variants."""

    variant_id: str
    variant_key: str
    control_id: str
    control_key: str
    absolute_lift: float = 0.0
    relative_lift: float = 0.0
    lift_confidence_interval: tuple[float, float] = (0.0, 0.0)
    p_value: float = 1.0
    z_score: float = 0.0
    is_significant: bool = False
    confidence_level: float = 0.95
    statistical_power: float = 0.0
    required_sample_size: int = 0


class ExperimentAnalysisResponse(BaseModel):
    """Complete analysis of an experiment."""

    experiment_id: str
    experiment_key: str
    status: str
    total_participants: int
    total_conversions: int
    overall_conversion_rate: float
    variant_stats: list[VariantStatsResponse] = Field(default_factory=list)
    comparisons: list[ComparisonResponse] = Field(default_factory=list)
    has_winner: bool = False
    winner_variant_id: str | None = None
    winner_variant_key: str | None = None
    winner_confidence: float = 0.0
    winner_reason: str = ""
    should_continue: bool = True
    recommendation: str = ""
    analysis_timestamp: str = ""
    confidence_level: float = 0.95


# -----------------------------------------------------------------------------
# Utility Schemas
# -----------------------------------------------------------------------------


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    code: str = "error"
    errors: list[dict[str, Any]] = Field(default_factory=list)


class ExperimentStatsResponse(BaseModel):
    """Statistics for all experiments."""

    total_experiments: int
    draft_experiments: int
    running_experiments: int
    paused_experiments: int
    completed_experiments: int
    total_assignments: int
    total_conversions: int
    experiments_by_strategy: dict[str, int] = Field(default_factory=dict)


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""

    id: str
    experiment_key: str
    action: str
    changes: dict[str, Any]
    old_values: dict[str, Any]
    new_values: dict[str, Any]
    user_id: str | None = None
    ip_address: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """List of audit logs response."""

    items: list[AuditLogResponse]
    total: int
    page: int = 1
    page_size: int = 20


__all__ = [
    # Enums
    "ExperimentStatusEnum",
    "AssignmentStrategyEnum",
    "MetricTypeEnum",
    # Variant schemas
    "VariantBase",
    "VariantCreate",
    "VariantUpdate",
    "VariantResponse",
    # Experiment schemas
    "TargetingRule",
    "ExperimentBase",
    "ExperimentCreate",
    "ExperimentUpdate",
    "ExperimentResponse",
    "ExperimentListResponse",
    # Assignment schemas
    "AssignmentContext",
    "AssignmentRequest",
    "AssignmentResponse",
    "BulkAssignmentRequest",
    "BulkAssignmentResponse",
    # Event tracking schemas
    "ConversionEvent",
    "RevenueEvent",
    "EventResponse",
    # Analysis schemas
    "VariantStatsResponse",
    "ComparisonResponse",
    "ExperimentAnalysisResponse",
    # Utility schemas
    "MessageResponse",
    "ErrorResponse",
    "ExperimentStatsResponse",
    "AuditLogResponse",
    "AuditLogListResponse",
]

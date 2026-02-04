"""
Pydantic schemas for feature flags API.

Provides request/response schemas for the feature flags REST API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class FlagTypeEnum(str, Enum):
    """Type of feature flag."""

    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    VARIANT = "variant"


class FlagStatusEnum(str, Enum):
    """Status of a feature flag."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class OverrideTypeEnum(str, Enum):
    """Type of flag override."""

    USER = "user"
    ORGANIZATION = "organization"
    EMAIL = "email"
    ATTRIBUTE = "attribute"


# -----------------------------------------------------------------------------
# Variant Schemas
# -----------------------------------------------------------------------------


class VariantSchema(BaseModel):
    """Schema for a variant in A/B testing."""

    key: str = Field(..., description="Unique key for the variant")
    name: str = Field(default="", description="Human-readable name")
    weight: int = Field(default=1, ge=0, description="Weight for random assignment")
    payload: dict[str, Any] = Field(default_factory=dict, description="Variant-specific data")


class VariantsConfigSchema(BaseModel):
    """Configuration for variants."""

    variants: list[VariantSchema] = Field(default_factory=list)
    default_variant: str | None = Field(default=None, description="Default variant key")


# -----------------------------------------------------------------------------
# Targeting Rule Schemas
# -----------------------------------------------------------------------------


class TargetingRuleSchema(BaseModel):
    """Schema for a targeting rule."""

    attribute: str = Field(..., description="Attribute to check")
    operator: Literal[
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not_in",
        "contains",
        "starts_with",
        "ends_with",
        "regex",
    ] = Field(default="eq", description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")


# -----------------------------------------------------------------------------
# Feature Flag Schemas
# -----------------------------------------------------------------------------


class FeatureFlagBase(BaseModel):
    """Base schema for feature flags."""

    key: str = Field(..., min_length=1, max_length=255, description="Unique flag identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable name")
    description: str = Field(default="", description="Description of the flag")
    flag_type: FlagTypeEnum = Field(default=FlagTypeEnum.BOOLEAN, description="Type of flag")
    enabled_by_default: bool = Field(default=False, description="Default enabled state")
    rollout_percentage: int = Field(default=0, ge=0, le=100, description="Rollout percentage")
    variants: VariantsConfigSchema = Field(
        default_factory=VariantsConfigSchema, description="Variant configuration"
    )
    targeting_rules: list[TargetingRuleSchema] = Field(
        default_factory=list, description="Targeting rules"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class FeatureFlagCreate(FeatureFlagBase):
    """Schema for creating a feature flag."""

    status: FlagStatusEnum = Field(default=FlagStatusEnum.INACTIVE, description="Initial status")
    scheduled_enable_at: datetime | None = Field(default=None, description="Scheduled enable time")
    scheduled_disable_at: datetime | None = Field(
        default=None, description="Scheduled disable time"
    )


class FeatureFlagUpdate(BaseModel):
    """Schema for updating a feature flag."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    flag_type: FlagTypeEnum | None = None
    status: FlagStatusEnum | None = None
    enabled_by_default: bool | None = None
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)
    variants: VariantsConfigSchema | None = None
    targeting_rules: list[TargetingRuleSchema] | None = None
    scheduled_enable_at: datetime | None = None
    scheduled_disable_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class FeatureFlagResponse(FeatureFlagBase):
    """Schema for feature flag response."""

    id: str
    status: FlagStatusEnum
    scheduled_enable_at: datetime | None = None
    scheduled_disable_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by_id: str | None = None
    is_active: bool = Field(description="Whether the flag is currently active")
    override_count: int = Field(default=0, description="Number of overrides")

    class Config:
        from_attributes = True


class FeatureFlagListResponse(BaseModel):
    """List of feature flags response."""

    items: list[FeatureFlagResponse]
    total: int
    page: int = 1
    page_size: int = 20


# -----------------------------------------------------------------------------
# Override Schemas
# -----------------------------------------------------------------------------


class FlagOverrideBase(BaseModel):
    """Base schema for flag overrides."""

    override_type: OverrideTypeEnum
    target_id: str = Field(default="", description="Target ID (user ID, org ID)")
    target_value: str = Field(default="", description="Target value (email, attribute value)")
    enabled: bool = Field(default=True, description="Override enabled state")
    variant: str | None = Field(default=None, description="Override variant")
    expires_at: datetime | None = Field(default=None, description="Override expiry")


class FlagOverrideCreate(FlagOverrideBase):
    """Schema for creating a flag override."""


class FlagOverrideUpdate(BaseModel):
    """Schema for updating a flag override."""

    enabled: bool | None = None
    variant: str | None = None
    expires_at: datetime | None = None


class FlagOverrideResponse(FlagOverrideBase):
    """Schema for flag override response."""

    id: str
    flag_id: str
    flag_key: str
    created_at: datetime
    created_by_id: str | None = None
    is_active: bool = Field(description="Whether the override is active (not expired)")

    class Config:
        from_attributes = True


class FlagOverrideListResponse(BaseModel):
    """List of flag overrides response."""

    items: list[FlagOverrideResponse]
    total: int


# -----------------------------------------------------------------------------
# Evaluation Schemas
# -----------------------------------------------------------------------------


class FlagEvaluationContext(BaseModel):
    """Context for flag evaluation."""

    user_id: str | None = Field(default=None, description="User ID")
    organization_id: str | None = Field(default=None, description="Organization ID")
    email: str | None = Field(default=None, description="User email")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Additional attributes")


class FlagEvaluationRequest(BaseModel):
    """Request for evaluating a flag."""

    flag_key: str
    context: FlagEvaluationContext = Field(default_factory=FlagEvaluationContext)
    default: bool = False


class FlagEvaluationResponse(BaseModel):
    """Response for flag evaluation."""

    flag_key: str
    enabled: bool
    variant: str | None = None
    reason: str = Field(default="", description="Reason for the evaluation result")


class BulkEvaluationRequest(BaseModel):
    """Request for evaluating multiple flags."""

    flag_keys: list[str] = Field(default_factory=list, description="Specific flags to evaluate")
    context: FlagEvaluationContext = Field(default_factory=FlagEvaluationContext)
    include_all: bool = Field(default=False, description="Include all active flags")


class BulkEvaluationResponse(BaseModel):
    """Response for bulk flag evaluation."""

    flags: dict[str, bool]
    variants: dict[str, str | None] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Audit Log Schemas
# -----------------------------------------------------------------------------


class FlagAuditLogResponse(BaseModel):
    """Schema for flag audit log response."""

    id: str
    flag_key: str
    action: str
    changes: dict[str, Any]
    old_values: dict[str, Any]
    new_values: dict[str, Any]
    user_id: str | None = None
    ip_address: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class FlagAuditLogListResponse(BaseModel):
    """List of audit logs response."""

    items: list[FlagAuditLogResponse]
    total: int
    page: int = 1
    page_size: int = 20


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


class FlagStatsResponse(BaseModel):
    """Statistics for feature flags."""

    total_flags: int
    active_flags: int
    inactive_flags: int
    archived_flags: int
    total_overrides: int
    flags_by_type: dict[str, int]
    recent_changes: int = Field(description="Changes in last 24 hours")


__all__ = [
    "FlagTypeEnum",
    "FlagStatusEnum",
    "OverrideTypeEnum",
    "VariantSchema",
    "VariantsConfigSchema",
    "TargetingRuleSchema",
    "FeatureFlagBase",
    "FeatureFlagCreate",
    "FeatureFlagUpdate",
    "FeatureFlagResponse",
    "FeatureFlagListResponse",
    "FlagOverrideBase",
    "FlagOverrideCreate",
    "FlagOverrideUpdate",
    "FlagOverrideResponse",
    "FlagOverrideListResponse",
    "FlagEvaluationContext",
    "FlagEvaluationRequest",
    "FlagEvaluationResponse",
    "BulkEvaluationRequest",
    "BulkEvaluationResponse",
    "FlagAuditLogResponse",
    "FlagAuditLogListResponse",
    "MessageResponse",
    "ErrorResponse",
    "FlagStatsResponse",
]

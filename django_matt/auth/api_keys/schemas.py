"""
Pydantic schemas for API Key endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# Request schemas


class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the key")
    is_test: bool = Field(default=False, description="Create a test key")
    scopes: list[str] = Field(default_factory=list, description="Permission scopes")
    expires_at: datetime | None = Field(default=None, description="Expiration date")
    allowed_ips: list[str] = Field(default_factory=list, description="Allowed IP addresses")

    model_config = {"from_attributes": True}


class APIKeyUpdateRequest(BaseModel):
    """Request to update an API key."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    scopes: list[str] | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)
    allowed_ips: list[str] | None = Field(default=None)
    is_active: bool | None = Field(default=None)

    model_config = {"from_attributes": True}


# Response schemas


class APIKeyResponse(BaseModel):
    """API key response (without the full key)."""

    id: int
    name: str
    prefix: str = Field(description="Key prefix for identification")
    is_test: bool
    is_active: bool
    plan: str
    scopes: list[str]
    rate_limit: int
    rate_limit_period: int
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None
    total_requests: int
    allowed_ips: list[str]

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(APIKeyResponse):
    """Response when creating a new API key (includes full key)."""

    key: str = Field(description="Full API key - save this, it won't be shown again!")


class APIKeyListResponse(BaseModel):
    """List of API keys."""

    items: list[APIKeyResponse]
    total: int


# Usage schemas


class UsageRecord(BaseModel):
    """Single usage record."""

    hour: datetime
    request_count: int
    error_count: int
    avg_response_time_ms: float
    max_response_time_ms: float
    bytes_sent: int
    bytes_received: int
    endpoint_counts: dict[str, int]

    model_config = {"from_attributes": True}


class UsageSummary(BaseModel):
    """Usage summary for a time period."""

    period_start: datetime
    period_end: datetime
    total_requests: int
    total_errors: int
    error_rate: float
    avg_response_time_ms: float
    total_bytes_sent: int
    total_bytes_received: int
    top_endpoints: list[dict[str, Any]]
    requests_by_hour: list[dict[str, Any]]


class UsageResponse(BaseModel):
    """Usage analytics response."""

    api_key_id: int
    api_key_name: str
    summary: UsageSummary
    records: list[UsageRecord]


# Export schemas


class ExportRequest(BaseModel):
    """Request to export data."""

    format: str = Field(default="json", description="Export format: json, csv")
    start_date: datetime | None = Field(default=None)
    end_date: datetime | None = Field(default=None)
    include_usage: bool = Field(default=True)


class ExportResponse(BaseModel):
    """Export response."""

    download_url: str | None = Field(default=None, description="URL to download export")
    data: Any | None = Field(default=None, description="Inline data for small exports")
    format: str
    record_count: int

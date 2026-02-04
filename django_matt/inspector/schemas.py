"""
Pydantic schemas for the Request Inspector API.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CapturedRequestSchema(BaseModel):
    """Schema for a captured request."""

    id: str
    timestamp: float
    timestamp_formatted: Optional[str] = None
    method: str
    path: str
    full_url: str
    query_string: str = ""
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: Optional[str] = None
    request_content_type: Optional[str] = None
    response_status: int = 0
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: Optional[str] = None
    response_content_type: Optional[str] = None
    duration_ms: float = 0.0
    client_ip: str = ""
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    exception: Optional[str] = None
    traceback: Optional[str] = None
    status_category: str = "unknown"
    is_success: bool = False
    is_error: bool = False

    class Config:
        from_attributes = True


class CapturedRequestListSchema(BaseModel):
    """Schema for a list of captured requests."""

    items: list[CapturedRequestSchema]
    total: int
    page: int = 1
    page_size: int = 50
    has_next: bool = False
    has_prev: bool = False


class InspectorStatsSchema(BaseModel):
    """Schema for inspector statistics."""

    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    methods: dict[str, int] = Field(default_factory=dict)
    status_codes: dict[str, int] = Field(default_factory=dict)
    is_capturing: bool = True


class ExportRequestSchema(BaseModel):
    """Schema for export request."""

    format: str = Field(default="curl", description="Export format: curl, httpie, python, fetch")
    include_response: bool = Field(
        default=False, description="Include expected response as comment"
    )


class ExportResponseSchema(BaseModel):
    """Schema for export response."""

    format: str
    content: str
    content_type: str = "text/plain"


class MessageResponseSchema(BaseModel):
    """Schema for simple message responses."""

    message: str
    success: bool = True


class ErrorResponseSchema(BaseModel):
    """Schema for error responses."""

    detail: str
    code: str = "error"


class CaptureStatusSchema(BaseModel):
    """Schema for capture status."""

    is_capturing: bool
    storage_type: str
    request_count: int
    max_requests: int


__all__ = [
    "CapturedRequestSchema",
    "CapturedRequestListSchema",
    "InspectorStatsSchema",
    "ExportRequestSchema",
    "ExportResponseSchema",
    "MessageResponseSchema",
    "ErrorResponseSchema",
    "CaptureStatusSchema",
]

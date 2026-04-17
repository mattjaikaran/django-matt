"""Batch request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class BatchRequest(BaseModel):
    """A single sub-request within a batch."""

    method: str = Field(description="HTTP method (GET, POST, PUT, PATCH, DELETE)")
    path: str = Field(description="Relative URL path for this sub-request")
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    name: str | None = Field(
        default=None,
        description="Optional name for referencing this request's result in dependencies",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Names of requests that must complete before this one",
    )

    @field_validator("method")
    @classmethod
    def normalize_method(cls, v: str) -> str:
        return v.upper()


class BatchResponse(BaseModel):
    """Response for a single sub-request."""

    status: int
    body: Any = None
    headers: dict[str, str] = Field(default_factory=dict)
    name: str | None = None
    error: str | None = None


class BatchPayload(BaseModel):
    """Top-level batch request payload."""

    requests: list[BatchRequest] = Field(min_length=1)
    atomic: bool = Field(
        default=False,
        description="Wrap all sub-requests in a single DB transaction",
    )

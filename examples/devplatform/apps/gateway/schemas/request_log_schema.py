from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RequestLogSchema(BaseModel):
    id: UUID
    project_id: UUID
    api_key_id: UUID | None = None
    method: str
    path: str
    status_code: int
    response_time_ms: int
    ip_address: str | None = None
    user_agent: str
    request_body_size: int
    response_body_size: int
    error_message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestLogListSchema(BaseModel):
    items: list[RequestLogSchema]
    total: int
    limit: int
    offset: int


class RequestLogFilterSchema(BaseModel):
    """Query parameter documentation for request log filtering."""

    method: str | None = None
    status_code: int | None = None
    path_contains: str | None = None
    min_response_time: int | None = None
    max_response_time: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class WebhookSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    url: str
    events: list[str]
    is_active: bool
    description: str
    created_at: datetime
    updated_at: datetime


class WebhookCreateSchema(BaseModel):
    url: HttpUrl
    events: list[str]
    description: str = ""


class WebhookUpdateSchema(BaseModel):
    url: HttpUrl | None = None
    events: list[str] | None = None
    is_active: bool | None = None
    description: str | None = None


class WebhookDeliverySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    webhook_id: str
    event_type: str
    payload: dict
    status_code: int | None
    response_body: str
    success: bool
    attempted_at: datetime
    duration_ms: int | None

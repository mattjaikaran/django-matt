from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StripeWebhookEvent(BaseModel):
    id: str
    object: str = "event"
    type: str
    api_version: str | None = None
    created: int = 0
    livemode: bool = False
    data: dict[str, Any] = Field(default_factory=dict)
    pending_webhooks: int = 0
    request: dict[str, Any] | None = None


class WebhookResponse(BaseModel):
    status: str = "ok"
    event_id: str = ""
    event_type: str = ""


class WebhookErrorResponse(BaseModel):
    status: str = "error"
    detail: str = ""

"""Pydantic schemas for {{ project_name }}."""

from datetime import datetime

from pydantic import BaseModel


class AuditEntrySchema(BaseModel):
    id: int
    user_id: int | None
    action: str
    resource_type: str
    resource_id: str
    details: dict
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeatureFlagCreate(BaseModel):
    name: str
    description: str = ""
    enabled: bool = False
    rollout_percent: int = 0


class FeatureFlagUpdate(BaseModel):
    enabled: bool | None = None
    rollout_percent: int | None = None
    description: str | None = None


class FeatureFlagSchema(BaseModel):
    id: int
    name: str
    description: str
    enabled: bool
    rollout_percent: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

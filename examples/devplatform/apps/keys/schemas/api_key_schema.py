from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class APIKeySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    created_by_id: int
    created_at: datetime


class APIKeyCreateSchema(BaseModel):
    name: str = Field(min_length=1)
    scopes: list[str] = ["read"]
    expires_at: datetime | None = None


class APIKeyCreatedSchema(APIKeySchema):
    """Returned only on creation -- includes the full key (shown once)."""

    full_key: str


class APIKeyUpdateSchema(BaseModel):
    name: str | None = None
    scopes: list[str] | None = None
    is_active: bool | None = None

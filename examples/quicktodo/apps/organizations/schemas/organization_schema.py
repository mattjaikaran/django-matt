from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str = ""
    created_at: datetime
    updated_at: datetime


class OrganizationCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str = ""


class OrganizationUpdateSchema(BaseModel):
    name: str | None = None
    description: str | None = None


class OrganizationWithRoleSchema(OrganizationSchema):
    role: str

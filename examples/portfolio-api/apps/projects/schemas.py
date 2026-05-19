from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    slug: str
    description: str
    long_description: str
    tech_stack: list[str]
    image_url: str | None = None
    live_url: str | None = None
    github_url: str | None = None
    featured: bool
    order: int
    is_published: bool
    created_at: datetime
    updated_at: datetime


class ProjectCreateSchema(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str
    long_description: str = ""
    tech_stack: list[str] = []
    image_url: str | None = None
    live_url: str | None = None
    github_url: str | None = None
    featured: bool = False
    order: int = 0
    is_published: bool = True


class ProjectUpdateSchema(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    long_description: str | None = None
    tech_stack: list[str] | None = None
    image_url: str | None = None
    live_url: str | None = None
    github_url: str | None = None
    featured: bool | None = None
    order: int | None = None
    is_published: bool | None = None

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ExperienceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company: str
    role: str
    company_url: str | None = None
    location: str
    start_date: date
    end_date: date | None = None
    is_current: bool
    description: str
    tech_used: list[str]
    order: int
    created_at: datetime
    updated_at: datetime


class ExperienceCreateSchema(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=255)
    company_url: str | None = None
    location: str = ""
    start_date: date
    end_date: date | None = None
    is_current: bool = False
    description: str
    tech_used: list[str] = []
    order: int = 0


class ExperienceUpdateSchema(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    company_url: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    description: str | None = None
    tech_used: list[str] | None = None
    order: int | None = None

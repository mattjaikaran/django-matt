from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkillCategoryLiteral = Literal["frontend", "backend", "devops", "database", "mobile", "other"]


class SkillSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    level: int
    icon: str
    order: int
    created_at: datetime
    updated_at: datetime


class SkillCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: SkillCategoryLiteral
    level: int = Field(default=3, ge=1, le=5)
    icon: str = Field(default="", max_length=50)
    order: int = 0


class SkillUpdateSchema(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: SkillCategoryLiteral | None = None
    level: int | None = Field(default=None, ge=1, le=5)
    icon: str | None = None
    order: int | None = None

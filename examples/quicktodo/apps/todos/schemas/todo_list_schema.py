from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TodoListSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str = ""
    created_by_id: int | None = None
    organization_id: str
    created_at: datetime
    updated_at: datetime
    todo_count: int = 0
    completed_count: int = 0


class TodoListCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class TodoListUpdateSchema(BaseModel):
    name: str | None = None
    description: str | None = None

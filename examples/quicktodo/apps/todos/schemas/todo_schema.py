from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TodoSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str = ""
    status: str = "pending"
    priority: str = "medium"
    assignee_id: int | None = None
    todo_list_id: str
    due_date: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TodoCreateSchema(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    status: str = "pending"
    priority: str = "medium"
    assignee_id: int | None = None
    todo_list_id: str | None = None
    due_date: datetime | None = None


class TodoUpdateSchema(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee_id: int | None = None
    due_date: datetime | None = None

import datetime
import uuid
from typing import Optional, List

from pydantic import Field

from django_matt.core.schema import Schema


class TaskBase(Schema):
    """Base schema for Task items."""

    title: str = Field(..., description="The title of the task")
    description: Optional[str] = Field(
        None, description="A detailed description of the task"
    )
    completed: bool = Field(False, description="Whether the task is completed")


class TaskCreate(TaskBase):
    """Schema for creating a new Task."""
    
    class Config:
        from_attributes = True


class TaskUpdate(Schema):
    """Schema for updating an existing Task."""

    title: Optional[str] = Field(None, description="The title of the task")
    description: Optional[str] = Field(
        None, description="A detailed description of the task"
    )
    completed: Optional[bool] = Field(
        None, description="Whether the task is completed"
    )
    
    class Config:
        from_attributes = True


class Task(TaskBase):
    """Schema for a Task with all fields."""

    id: uuid.UUID = Field(..., description="The unique identifier for the task")
    created_at: datetime.datetime = Field(
        ..., description="When the task was created"
    )
    updated_at: Optional[datetime.datetime] = Field(
        None, description="When the task was last updated"
    )

    class Config:
        from_attributes = True


class TaskList(Schema):
    """Schema for a list of Tasks."""

    items: List[Task] = Field(..., description="List of tasks")
    count: int = Field(..., description="Total number of tasks")
    
    class Config:
        from_attributes = True

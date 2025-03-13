import datetime
import uuid

from pydantic import Field

from django_matt.core.schema import Schema


class TodoBase(Schema):
    """Base schema for Todo items."""

    title: str = Field(..., description="The title of the todo item")
    description: str | None = Field(
        None, description="A detailed description of the todo item"
    )
    completed: bool = Field(False, description="Whether the todo item is completed")


class TodoCreate(TodoBase):
    """Schema for creating a new Todo item."""

    pass


class TodoUpdate(Schema):
    """Schema for updating an existing Todo item."""

    title: str | None = Field(None, description="The title of the todo item")
    description: str | None = Field(
        None, description="A detailed description of the todo item"
    )
    completed: bool | None = Field(
        None, description="Whether the todo item is completed"
    )


class Todo(TodoBase):
    """Schema for a Todo item with all fields."""

    id: uuid.UUID = Field(..., description="The unique identifier for the todo item")
    created_at: datetime.datetime = Field(
        ..., description="When the todo item was created"
    )
    updated_at: datetime.datetime | None = Field(
        None, description="When the todo item was last updated"
    )

    class Config:
        orm_mode = True


class TodoList(Schema):
    """Schema for a list of Todo items."""

    items: list[Todo] = Field(..., description="List of todo items")
    count: int = Field(..., description="Total number of todo items")

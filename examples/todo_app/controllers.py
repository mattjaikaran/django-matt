import uuid
from typing import Any

from django.http import HttpRequest

from django_matt.core.controller import CRUDController
from django_matt.core.router import delete, get, post, put

from .models import Todo
from .schemas import Todo as TodoSchema
from .schemas import TodoCreate, TodoList, TodoUpdate
from .services import TodoService


class TodoController(CRUDController):
    """Controller for Todo items. HTTP concerns only — logic lives in TodoService."""

    prefix = "todos/"
    model = Todo
    schema = TodoSchema
    create_schema = TodoCreate
    update_schema = TodoUpdate

    def __init__(self):
        self.service = TodoService()
        super().__init__()

    @get("", response_model=TodoList)
    async def get_todos(self, request: HttpRequest) -> dict[str, Any]:
        """Get all todo items."""
        items, total = await self.service.list()
        return {"items": items, "total": total}

    @get("{id}", response_model=TodoSchema)
    async def get_todo(self, request: HttpRequest, id: str) -> Todo:
        """Get a specific todo item by ID."""
        return await self.service.get(uuid.UUID(id))

    @post("", response_model=TodoSchema, status_code=201)
    async def create_todo(self, request: HttpRequest, data: TodoCreate) -> Todo:
        """Create a new todo item."""
        return await self.service.create(data.model_dump())

    @put("{id}", response_model=TodoSchema)
    async def update_todo(self, request: HttpRequest, id: str, data: TodoUpdate) -> Todo:
        """Update an existing todo item."""
        return await self.service.update(uuid.UUID(id), data.model_dump(), partial=True)

    @delete("{id}", status_code=204)
    async def delete_todo(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """Delete a todo item."""
        await self.service.delete(uuid.UUID(id))
        return {}

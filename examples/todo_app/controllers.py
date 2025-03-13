import uuid
from typing import Any

from django.http import HttpRequest

from django_matt.core.controller import CRUDController
from django_matt.core.router import delete, get, post, put

from .models import Todo
from .schemas import Todo as TodoSchema
from .schemas import TodoCreate, TodoList, TodoUpdate


class TodoController(CRUDController):
    """Controller for Todo items."""

    prefix = "todos/"
    model = Todo
    schema = TodoSchema
    create_schema = TodoCreate
    update_schema = TodoUpdate

    @get("", response_model=TodoList)
    async def get_todos(self, request: HttpRequest) -> dict[str, Any]:
        """Get all todo items."""
        result = await self.list(request)
        return result

    @get("{id}", response_model=TodoSchema)
    async def get_todo(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """Get a specific todo item by ID."""
        todo_id = uuid.UUID(id)
        result = await self.retrieve(request, todo_id)
        return result

    @post("", response_model=TodoSchema, status_code=201)
    async def create_todo(
        self, request: HttpRequest, data: TodoCreate
    ) -> dict[str, Any]:
        """Create a new todo item."""
        result = await self.create(request, data)
        return result

    @put("{id}", response_model=TodoSchema)
    async def update_todo(
        self, request: HttpRequest, id: str, data: TodoUpdate
    ) -> dict[str, Any]:
        """Update an existing todo item."""
        todo_id = uuid.UUID(id)
        result = await self.update(request, todo_id, data)
        return result

    @delete("{id}", status_code=204)
    async def delete_todo(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """Delete a todo item."""
        todo_id = uuid.UUID(id)
        await self.delete(request, todo_id)
        return {}

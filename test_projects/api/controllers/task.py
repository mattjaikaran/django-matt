import uuid
from typing import Any, Dict, Tuple, Optional

from django.http import HttpRequest
from ninja_extra import status

from django_matt.core.controller import CRUDController
from django_matt.core.router import delete, get, post, put

from ..models import Task
from ..schemas import Task as TaskSchema
from ..schemas import TaskCreate, TaskList, TaskUpdate


class TaskController(CRUDController):
    """Controller for Task items."""

    prefix = "tasks/"
    model = Task
    schema = TaskSchema
    create_schema = TaskCreate
    update_schema = TaskUpdate

    @get("", response_model=TaskList)
    async def get_tasks(self, request: HttpRequest) -> Dict[str, Any]:
        """Get all tasks."""
        try:
            result = await self.list(request)
            return result
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @get("{id}", response_model=TaskSchema)
    async def get_task(self, request: HttpRequest, id: str) -> Dict[str, Any]:
        """Get a specific task by ID."""
        try:
            task_id = uuid.UUID(id)
            result = await self.retrieve(request, task_id)
            return result
        except Task.DoesNotExist:
            return {"error": "Task not found"}, status.HTTP_404_NOT_FOUND
        except ValueError:
            return {"error": "Invalid UUID format"}, status.HTTP_400_BAD_REQUEST
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @post("", response_model=TaskSchema, status_code=status.HTTP_201_CREATED)
    async def create_task(
        self, request: HttpRequest, data: TaskCreate
    ) -> Dict[str, Any]:
        """Create a new task."""
        try:
            result = await self.create(request, data)
            return result
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @put("{id}", response_model=TaskSchema)
    async def update_task(
        self, request: HttpRequest, id: str, data: TaskUpdate
    ) -> Dict[str, Any]:
        """Update an existing task."""
        try:
            task_id = uuid.UUID(id)
            result = await self.update(request, task_id, data)
            return result
        except Task.DoesNotExist:
            return {"error": "Task not found"}, status.HTTP_404_NOT_FOUND
        except ValueError:
            return {"error": "Invalid UUID format"}, status.HTTP_400_BAD_REQUEST
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @delete("{id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_task(self, request: HttpRequest, id: str) -> Dict[str, Any]:
        """Delete a task."""
        try:
            task_id = uuid.UUID(id)
            await self.delete(request, task_id)
            return {}
        except Task.DoesNotExist:
            return {"error": "Task not found"}, status.HTTP_404_NOT_FOUND
        except ValueError:
            return {"error": "Invalid UUID format"}, status.HTTP_400_BAD_REQUEST
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

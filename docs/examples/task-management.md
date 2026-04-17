# Complete Example: Task Management API

A full example combining CRUD operations, organization-scoped access, real-time WebSocket notifications, and background tasks.

## Models

```python
# models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    organization = models.ForeignKey("Organization", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## Schemas

```python
# schemas.py
from django_matt.core import ModelSchema, Schema
from pydantic import Field
from typing import Optional
from datetime import date
from .models import Task, Project

class TaskSchema(ModelSchema):
    class Meta:
        model = Task
        fields = ["id", "title", "description", "status", "project_id",
                  "assignee_id", "due_date", "created_at", "updated_at"]

class TaskCreate(Schema):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    project_id: int
    assignee_id: Optional[int] = None
    due_date: Optional[date] = None

class TaskUpdate(Schema):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    assignee_id: Optional[int] = None
    due_date: Optional[date] = None

class ProjectSchema(ModelSchema):
    task_count: int = 0

    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_at"]
```

## Controller

```python
# api.py
from django_matt import MattAPI
from django_matt.core import APIController
from django_matt.auth import jwt_required
from django_matt.permissions import IsAuthenticated
from django_matt.core.errors import NotFoundAPIError, PermissionDeniedAPIError
from django_matt.websockets.groups import broadcast

from .models import Task, Project
from .schemas import TaskSchema, TaskCreate, TaskUpdate, ProjectSchema

api = MattAPI(title="Task Management API", version="1.0.0")

@api.controller("/projects/{project_id}/tasks", tags=["Tasks"])
class TaskController(APIController):
    permission_classes = [IsAuthenticated]

    async def get_project(self, project_id: int, request):
        project = await Project.objects.filter(
            id=project_id,
            organization__members__user=request.user
        ).afirst()
        if not project:
            raise NotFoundAPIError("Project not found")
        return project

    @api.get("/")
    async def list(self, request, project_id: int, status: str = None):
        """List tasks in a project."""
        await self.get_project(project_id, request)

        qs = Task.objects.filter(project_id=project_id)
        if status:
            qs = qs.filter(status=status)

        tasks = await qs.select_related("assignee").all()
        return {"tasks": [TaskSchema.from_orm(t) for t in tasks]}

    @api.post("/")
    async def create(self, request, project_id: int, data: TaskCreate):
        """Create a new task."""
        project = await self.get_project(project_id, request)

        task = await Task.objects.acreate(
            project=project,
            **data.dict()
        )

        # Notify via WebSocket
        await broadcast(f"project_{project_id}", {
            "type": "task_created",
            "task": TaskSchema.from_orm(task).dict(),
        })

        return TaskSchema.from_orm(task)

    @api.get("/{task_id}")
    async def detail(self, request, project_id: int, task_id: int):
        """Get task details."""
        await self.get_project(project_id, request)

        task = await Task.objects.filter(
            id=task_id,
            project_id=project_id
        ).select_related("assignee").afirst()

        if not task:
            raise NotFoundAPIError("Task not found")

        return TaskSchema.from_orm(task)

    @api.patch("/{task_id}")
    async def update(self, request, project_id: int, task_id: int, data: TaskUpdate):
        """Update a task."""
        await self.get_project(project_id, request)

        task = await Task.objects.filter(
            id=task_id,
            project_id=project_id
        ).afirst()

        if not task:
            raise NotFoundAPIError("Task not found")

        for key, value in data.dict(exclude_unset=True).items():
            setattr(task, key, value)
        await task.asave()

        # Notify via WebSocket
        await broadcast(f"project_{project_id}", {
            "type": "task_updated",
            "task": TaskSchema.from_orm(task).dict(),
        })

        return TaskSchema.from_orm(task)

    @api.delete("/{task_id}")
    async def delete(self, request, project_id: int, task_id: int):
        """Delete a task."""
        await self.get_project(project_id, request)

        deleted, _ = await Task.objects.filter(
            id=task_id,
            project_id=project_id
        ).adelete()

        if not deleted:
            raise NotFoundAPIError("Task not found")

        # Notify via WebSocket
        await broadcast(f"project_{project_id}", {
            "type": "task_deleted",
            "task_id": task_id,
        })

        return {"success": True}

    @api.post("/{task_id}/assign")
    async def assign(self, request, project_id: int, task_id: int, assignee_id: int):
        """Assign a task to a user."""
        await self.get_project(project_id, request)

        task = await Task.objects.filter(
            id=task_id,
            project_id=project_id
        ).afirst()

        if not task:
            raise NotFoundAPIError("Task not found")

        task.assignee_id = assignee_id
        await task.asave()

        # Send notification to assignee
        from .tasks import send_task_assignment_notification
        send_task_assignment_notification.delay(task.id, assignee_id)

        return TaskSchema.from_orm(task)
```

## URL Configuration

```python
# urls.py
from django.urls import path
from .api import api

urlpatterns = [
    path("api/", api.urls),
]
```

## What This Demonstrates

- CRUD operations with proper validation
- Organization-scoped access control
- Real-time WebSocket notifications
- Background task processing
- Comprehensive error handling

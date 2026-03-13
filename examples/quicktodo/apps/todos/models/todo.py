import uuid
from enum import Enum

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Todo(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    todo_list = models.ForeignKey(
        "todos.TodoList",
        on_delete=models.CASCADE,
        related_name="todos",
    )
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.value) for s in TodoStatus],
        default=TodoStatus.PENDING.value,
    )
    priority = models.CharField(
        max_length=20,
        choices=[(p.value, p.value) for p in TodoPriority],
        default=TodoPriority.MEDIUM.value,
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_todos",
    )
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "todos"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

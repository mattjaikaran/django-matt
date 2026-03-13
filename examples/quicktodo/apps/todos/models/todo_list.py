import uuid

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class TodoList(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="todo_lists",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_todo_lists",
    )

    class Meta:
        db_table = "todo_lists"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

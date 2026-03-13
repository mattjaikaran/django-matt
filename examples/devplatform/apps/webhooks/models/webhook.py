import uuid

from django.db import models

from apps.core.models import BaseModel
from apps.projects.models import Project


class Webhook(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="webhooks",
    )
    url = models.URLField()
    secret = models.CharField(max_length=255)
    events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Webhook {self.url} ({self.project})"

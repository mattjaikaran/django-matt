import uuid

from django.db import models

from apps.core.models import BaseModel


class RequestLog(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="request_logs",
    )
    api_key = models.ForeignKey(
        "keys.APIKey",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_logs",
    )
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.IntegerField()
    response_time_ms = models.IntegerField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")
    request_body_size = models.IntegerField(default=0)
    response_body_size = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["project", "status_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.path} -> {self.status_code}"

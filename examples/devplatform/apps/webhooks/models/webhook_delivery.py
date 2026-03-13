import uuid

from django.db import models

from apps.core.models import BaseModel

from .webhook import Webhook


class WebhookDelivery(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    status_code = models.IntegerField(null=True)
    response_body = models.TextField(blank=True, default="")
    success = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)
    duration_ms = models.IntegerField(null=True)

    class Meta:
        ordering = ["-attempted_at"]

    def __str__(self) -> str:
        status = "OK" if self.success else "FAILED"
        return f"Delivery {self.event_type} -> {status}"

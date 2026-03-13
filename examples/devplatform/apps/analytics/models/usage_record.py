import uuid

from django.db import models


class UsageRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="usage_records",
    )
    metric_name = models.CharField(max_length=100)
    value = models.BigIntegerField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "metric_name", "recorded_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.metric_name}: {self.value}"

import uuid

from django.db import models


class DailyMetric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="daily_metrics",
    )
    date = models.DateField()
    total_requests = models.IntegerField(default=0)
    successful_requests = models.IntegerField(default=0)
    failed_requests = models.IntegerField(default=0)
    avg_response_time_ms = models.FloatField(default=0)
    p95_response_time_ms = models.FloatField(default=0)
    total_bandwidth_bytes = models.BigIntegerField(default=0)
    unique_ips = models.IntegerField(default=0)

    class Meta:
        unique_together = [("project", "date")]
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.project} - {self.date}"

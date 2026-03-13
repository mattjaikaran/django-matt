import uuid

from django.db import models

from apps.core.models import BaseModel
from apps.organizations.models import Organization


class Subscription(BaseModel):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("cancelled", "Cancelled"),
        ("trialing", "Trialing"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    plan = models.CharField(max_length=50, choices=PLAN_CHOICES, default="free")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="active")
    current_period_start = models.DateTimeField(null=True)
    current_period_end = models.DateTimeField(null=True)
    api_calls_limit = models.IntegerField(default=10000)
    api_calls_used = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.organization} - {self.plan} ({self.status})"

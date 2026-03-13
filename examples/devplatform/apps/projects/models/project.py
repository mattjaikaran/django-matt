import uuid

from django.db import models

from apps.core.models import BaseModel
from apps.organizations.models import Organization


class Project(BaseModel):
    ENVIRONMENT_CHOICES = [
        ("development", "Development"),
        ("staging", "Staging"),
        ("production", "Production"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True, default="")
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default="development",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "slug")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.environment})"

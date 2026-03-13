import uuid

from django.db import models

from apps.core.models import BaseModel


class Team(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(
        "organizations.Membership",
        related_name="teams",
        blank=True,
    )

    class Meta:
        db_table = "teams"
        unique_together = [("organization", "slug")]

    def __str__(self) -> str:
        return f"{self.organization.name} / {self.name}"

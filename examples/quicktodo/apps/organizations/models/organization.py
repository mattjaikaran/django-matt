import uuid

from django.db import models

from apps.core.models import BaseModel


class Organization(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "organizations"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

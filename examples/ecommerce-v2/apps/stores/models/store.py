import uuid

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Store(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stores",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    logo_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Store"
        verbose_name_plural = "Stores"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

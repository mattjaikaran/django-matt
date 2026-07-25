import uuid

from django.db import models

from apps.core.models import BaseModel


class Variant(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="variants",
    )
    name = models.CharField(max_length=255)  # e.g. "Size: L"
    sku = models.CharField(max_length=100, unique=True)
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Variant"
        verbose_name_plural = "Variants"
        ordering = ["product", "name"]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.name}"

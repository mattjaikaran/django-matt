import uuid

from django.db import models

from apps.core.models import BaseModel


class Inventory(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.OneToOneField(
        "catalog.Variant",
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)

    class Meta:
        verbose_name = "Inventory"
        verbose_name_plural = "Inventory"

    def __str__(self) -> str:
        return f"{self.variant} - qty: {self.quantity}"

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.low_stock_threshold

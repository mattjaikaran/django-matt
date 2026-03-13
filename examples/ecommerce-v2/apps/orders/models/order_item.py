from django.db import models

from apps.core.models import BaseModel


class OrderItem(BaseModel):
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="order_items",
    )
    variant = models.ForeignKey(
        "catalog.Variant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self) -> str:
        return f"{self.product} x{self.quantity} @ {self.unit_price}"

from django.db import models

from apps.core.models import BaseModel


class CartItem(BaseModel):
    cart = models.ForeignKey(
        "cart.Cart",
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    variant = models.ForeignKey(
        "catalog.Variant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        unique_together = [("cart", "product", "variant")]

    def __str__(self) -> str:
        return f"{self.product} x{self.quantity}"

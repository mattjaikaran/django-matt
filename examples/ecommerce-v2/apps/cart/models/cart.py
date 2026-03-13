from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Cart(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self) -> str:
        return f"Cart for {self.user}"

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class Review(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    is_verified_purchase = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        unique_together = [("user", "product")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Review by {self.user_id} on {self.product_id} ({self.rating}/5)"

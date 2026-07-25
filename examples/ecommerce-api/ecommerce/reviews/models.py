"""Review models for e-commerce."""

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """Product review model."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="reviews")
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )

    # Review content
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()

    # Pros and cons (optional)
    pros = models.JSONField(default=list, blank=True)  # ["Good quality", "Fast shipping"]
    cons = models.JSONField(default=list, blank=True)  # ["A bit expensive"]

    # Verification
    verified_purchase = models.BooleanField(default=False)

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Moderation
    moderation_notes = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_reviews",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    # Helpfulness voting
    helpful_votes = models.PositiveIntegerField(default=0)
    not_helpful_votes = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ["-created_at"]
        unique_together = ["product", "user"]  # One review per product per user
        indexes = [
            models.Index(fields=["product", "status"]),
            models.Index(fields=["rating"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.product.name} ({self.rating}/5)"

    @property
    def helpfulness_score(self) -> float:
        """Calculate helpfulness score."""
        total = self.helpful_votes + self.not_helpful_votes
        if total == 0:
            return 0.0
        return self.helpful_votes / total


class ReviewImage(models.Model):
    """Review image model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="reviews/")
    caption = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review Image"
        verbose_name_plural = "Review Images"
        ordering = ["display_order"]

    def __str__(self) -> str:
        return f"Image for review {self.review.id}"


class ReviewVote(models.Model):
    """Track helpful/not helpful votes on reviews."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="review_votes")
    is_helpful = models.BooleanField()

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review Vote"
        verbose_name_plural = "Review Votes"
        unique_together = ["review", "user"]  # One vote per review per user

    def __str__(self) -> str:
        vote_type = "helpful" if self.is_helpful else "not helpful"
        return f"{self.user.email} voted {vote_type} on {self.review.id}"

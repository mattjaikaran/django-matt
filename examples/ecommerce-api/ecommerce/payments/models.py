"""Payment models for e-commerce."""

import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone


class Payment(models.Model):
    """Payment model."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"

    class PaymentMethod(models.TextChoices):
        CARD = "card", "Credit/Debit Card"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        PAYPAL = "paypal", "PayPal"
        APPLE_PAY = "apple_pay", "Apple Pay"
        GOOGLE_PAY = "google_pay", "Google Pay"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="payments"
    )

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Payment details
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CARD
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Stripe details
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)

    # Card details (masked)
    card_brand = models.CharField(max_length=50, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.PositiveSmallIntegerField(null=True, blank=True)
    card_exp_year = models.PositiveSmallIntegerField(null=True, blank=True)

    # Error handling
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stripe_payment_intent_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["order", "status"]),
        ]

    def __str__(self) -> str:
        return f"Payment {self.id} - {self.status}"

    def mark_succeeded(self) -> None:
        """Mark payment as succeeded."""
        self.status = self.Status.SUCCEEDED
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at", "updated_at"])

    def mark_failed(self, error_code: str = "", error_message: str = "") -> None:
        """Mark payment as failed."""
        self.status = self.Status.FAILED
        self.error_code = error_code
        self.error_message = error_message
        self.save(update_fields=["status", "error_code", "error_message", "updated_at"])


class Refund(models.Model):
    """Refund model."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Reason(models.TextChoices):
        REQUESTED_BY_CUSTOMER = "requested_by_customer", "Requested by Customer"
        DUPLICATE = "duplicate", "Duplicate"
        FRAUDULENT = "fraudulent", "Fraudulent"
        ORDER_CANCELLED = "order_cancelled", "Order Cancelled"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="refunds")
    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="refunds"
    )

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Refund details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(
        max_length=30, choices=Reason.choices, default=Reason.REQUESTED_BY_CUSTOMER
    )
    notes = models.TextField(blank=True)

    # Stripe details
    stripe_refund_id = models.CharField(max_length=255, blank=True, db_index=True)

    # Error handling
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    # Created by
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_refunds",
    )

    class Meta:
        verbose_name = "Refund"
        verbose_name_plural = "Refunds"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Refund {self.id} - {self.amount} {self.payment.currency}"


class PaymentWebhookLog(models.Model):
    """Log incoming payment webhooks for debugging."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=50)  # stripe, paypal, etc.
    event_type = models.CharField(max_length=100)
    event_id = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField()

    # Processing status
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Payment Webhook Log"
        verbose_name_plural = "Payment Webhook Logs"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["provider", "event_type"]),
            models.Index(fields=["event_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider} - {self.event_type} - {self.event_id}"

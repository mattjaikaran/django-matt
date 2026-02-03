"""
Billing models for SaaS Starter.

Includes:
- Subscription management
- Invoice tracking
- Usage metering
- Payment methods
"""

import uuid
from django.db import models
from django.utils import timezone

from core.models import User, Organization


class SubscriptionStatus(models.TextChoices):
    """Subscription status choices."""
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past Due"
    CANCELED = "canceled", "Canceled"
    TRIALING = "trialing", "Trialing"
    PAUSED = "paused", "Paused"
    INCOMPLETE = "incomplete", "Incomplete"


class Subscription(models.Model):
    """
    Subscription model for organization billing.

    Features:
    - Stripe integration
    - Status tracking
    - Trial management
    - Cancellation handling
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="subscription"
    )

    # Stripe references
    stripe_subscription_id = models.CharField(max_length=255, unique=True, db_index=True)
    stripe_price_id = models.CharField(max_length=255)
    stripe_product_id = models.CharField(max_length=255, blank=True)

    # Plan details
    plan_name = models.CharField(max_length=100)
    plan_interval = models.CharField(
        max_length=20,
        choices=[
            ("month", "Monthly"),
            ("year", "Yearly"),
        ],
        default="month",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
    )

    # Billing cycle
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()

    # Trial
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    # Cancellation
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    # Quantity (for per-seat pricing)
    quantity = models.IntegerField(default=1)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization.name} - {self.plan_name}"

    @property
    def is_active(self):
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]

    @property
    def is_trialing(self):
        return self.status == SubscriptionStatus.TRIALING

    @property
    def days_until_renewal(self):
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return 0


class InvoiceStatus(models.TextChoices):
    """Invoice status choices."""
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    PAID = "paid", "Paid"
    VOID = "void", "Void"
    UNCOLLECTIBLE = "uncollectible", "Uncollectible"


class Invoice(models.Model):
    """
    Invoice model for tracking payments.

    Features:
    - Stripe sync
    - Line items
    - PDF storage
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invoices"
    )
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, related_name="invoices"
    )

    # Stripe references
    stripe_invoice_id = models.CharField(max_length=255, unique=True, db_index=True)

    # Invoice details
    number = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
        db_index=True,
    )

    # Amounts (in cents)
    subtotal = models.IntegerField(default=0)
    tax = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    amount_paid = models.IntegerField(default=0)
    amount_due = models.IntegerField(default=0)
    currency = models.CharField(max_length=3, default="usd")

    # Line items
    line_items = models.JSONField(default=list)

    # Dates
    invoice_date = models.DateTimeField()
    due_date = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # PDF
    invoice_pdf_url = models.URLField(max_length=500, blank=True)
    hosted_invoice_url = models.URLField(max_length=500, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoices"
        ordering = ["-invoice_date"]

    def __str__(self):
        return f"Invoice {self.number} - {self.organization.name}"

    @property
    def total_dollars(self):
        return self.total / 100

    @property
    def is_paid(self):
        return self.status == InvoiceStatus.PAID


class PaymentMethod(models.Model):
    """
    Payment method for organizations.

    Features:
    - Multiple payment methods per org
    - Default method tracking
    - Card details (masked)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="payment_methods"
    )

    # Stripe references
    stripe_payment_method_id = models.CharField(max_length=255, unique=True, db_index=True)

    # Type
    type = models.CharField(
        max_length=20,
        choices=[
            ("card", "Card"),
            ("bank_account", "Bank Account"),
            ("sepa_debit", "SEPA Debit"),
        ],
        default="card",
    )

    # Card details (masked)
    card_brand = models.CharField(max_length=50, blank=True)  # visa, mastercard, etc.
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)

    # Billing address
    billing_name = models.CharField(max_length=255, blank=True)
    billing_email = models.EmailField(blank=True)
    billing_address = models.JSONField(default=dict)

    # Status
    is_default = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_methods"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        if self.type == "card":
            return f"{self.card_brand} ****{self.card_last4}"
        return f"{self.type}"

    def save(self, *args, **kwargs):
        # Ensure only one default payment method per org
        if self.is_default:
            PaymentMethod.objects.filter(
                organization=self.organization, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class UsageRecord(models.Model):
    """
    Usage metering for consumption-based billing.

    Features:
    - Quantity tracking
    - Aggregation support
    - Stripe metering sync
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="usage_records"
    )
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="usage_records"
    )

    # Usage details
    metric = models.CharField(max_length=100, db_index=True)  # "api_calls", "storage_gb", etc.
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    action = models.CharField(
        max_length=20,
        choices=[
            ("increment", "Increment"),
            ("set", "Set"),
        ],
        default="increment",
    )

    # Stripe reference
    stripe_usage_record_id = models.CharField(max_length=255, blank=True)

    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "usage_records"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["organization", "metric", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.metric}: {self.quantity}"


class Coupon(models.Model):
    """
    Coupon/discount codes.

    Features:
    - Percentage or fixed amount
    - Usage limits
    - Expiration
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Stripe references
    stripe_coupon_id = models.CharField(max_length=255, unique=True, db_index=True)

    # Code
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)

    # Discount
    discount_type = models.CharField(
        max_length=20,
        choices=[
            ("percent", "Percentage"),
            ("amount", "Fixed Amount"),
        ],
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")

    # Duration
    duration = models.CharField(
        max_length=20,
        choices=[
            ("once", "Once"),
            ("repeating", "Repeating"),
            ("forever", "Forever"),
        ],
        default="once",
    )
    duration_months = models.IntegerField(null=True, blank=True)  # For repeating

    # Limits
    max_redemptions = models.IntegerField(null=True, blank=True)
    times_redeemed = models.IntegerField(default=0)

    # Validity
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)

    # Restrictions
    applies_to_plans = models.JSONField(default=list)  # Empty = all plans
    minimum_amount = models.IntegerField(null=True, blank=True)  # In cents

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "coupons"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.valid_until and timezone.now() > self.valid_until:
            return False
        if self.max_redemptions and self.times_redeemed >= self.max_redemptions:
            return False
        return True


class CouponRedemption(models.Model):
    """
    Coupon redemption tracking.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="redemptions")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="coupon_redemptions"
    )
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, related_name="coupon_redemptions"
    )
    redeemed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="coupon_redemptions"
    )

    # Stripe reference
    stripe_discount_id = models.CharField(max_length=255, blank=True)

    # Timestamps
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "coupon_redemptions"
        ordering = ["-redeemed_at"]

    def __str__(self):
        return f"{self.coupon.code} redeemed by {self.organization.name}"

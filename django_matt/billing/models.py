# file-length-max: 650
"""
Django models for billing/subscription management.

These models provide local storage and tracking of billing data
synchronized from payment providers (Stripe, PayPal, Polar).
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class BillingCustomer(models.Model):
    """
    Links a Django user to their billing provider customer ID(s).

    A user can have customer IDs with multiple providers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billing_customers",
    )

    # Provider-specific customer IDs
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    paypal_customer_id = models.CharField(max_length=255, blank=True, null=True)
    polar_customer_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    # Default provider for this customer
    default_provider = models.CharField(
        max_length=50,
        default="stripe",
        choices=[
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("polar", "Polar"),
        ],
    )

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_customer"
        verbose_name = "Billing Customer"
        verbose_name_plural = "Billing Customers"

    def __str__(self):
        return f"BillingCustomer({self.user}, {self.default_provider})"

    def get_customer_id(self, provider: str | None = None) -> str | None:
        """Get customer ID for a specific provider."""
        provider = provider or self.default_provider
        return getattr(self, f"{provider}_customer_id", None)

    def set_customer_id(self, provider: str, customer_id: str) -> None:
        """Set customer ID for a specific provider."""
        setattr(self, f"{provider}_customer_id", customer_id)
        self.save(update_fields=[f"{provider}_customer_id", "updated_at"])


class BillingProduct(models.Model):
    """
    Local representation of a product from the billing provider.

    Products define what you're selling (e.g., "Pro Plan", "Enterprise Plan").
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Provider information
    provider = models.CharField(
        max_length=50,
        choices=[
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("polar", "Polar"),
        ],
    )
    provider_product_id = models.CharField(max_length=255)

    # Product details
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    # Features and metadata
    features = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_product"
        verbose_name = "Billing Product"
        verbose_name_plural = "Billing Products"
        unique_together = [("provider", "provider_product_id")]

    def __str__(self):
        return f"{self.name} ({self.provider})"


class BillingPrice(models.Model):
    """
    Local representation of a price/plan from the billing provider.

    Prices define how much to charge (amount, currency, interval).
    """

    class Interval(models.TextChoices):
        DAY = "day", "Daily"
        WEEK = "week", "Weekly"
        MONTH = "month", "Monthly"
        YEAR = "year", "Yearly"
        ONE_TIME = "one_time", "One Time"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Provider information
    provider = models.CharField(
        max_length=50,
        choices=[
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("polar", "Polar"),
        ],
    )
    provider_price_id = models.CharField(max_length=255)

    # Link to product
    product = models.ForeignKey(
        BillingProduct,
        on_delete=models.CASCADE,
        related_name="prices",
        null=True,
        blank=True,
    )

    # Pricing details
    currency = models.CharField(max_length=3, default="usd")
    unit_amount = models.PositiveIntegerField(help_text="Amount in smallest currency unit (cents)")
    interval = models.CharField(max_length=20, choices=Interval.choices, default=Interval.MONTH)
    interval_count = models.PositiveSmallIntegerField(default=1)
    trial_period_days = models.PositiveSmallIntegerField(null=True, blank=True)

    # Status
    active = models.BooleanField(default=True)

    # Display name for this price (e.g., "Monthly", "Annual")
    nickname = models.CharField(max_length=100, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_price"
        verbose_name = "Billing Price"
        verbose_name_plural = "Billing Prices"
        unique_together = [("provider", "provider_price_id")]

    def __str__(self):
        return f"{self.display_amount} {self.currency.upper()}/{self.interval}"

    @property
    def display_amount(self) -> str:
        """Return formatted amount (e.g., '$9.99')."""
        amount = self.unit_amount / 100
        return f"{amount:.2f}"


class Subscription(models.Model):
    """
    Local representation of a subscription.

    Tracks the relationship between a customer and their active subscriptions.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELED = "canceled", "Canceled"
        INCOMPLETE = "incomplete", "Incomplete"
        INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete Expired"
        PAST_DUE = "past_due", "Past Due"
        PAUSED = "paused", "Paused"
        TRIALING = "trialing", "Trialing"
        UNPAID = "unpaid", "Unpaid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Links
    customer = models.ForeignKey(
        BillingCustomer,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    price = models.ForeignKey(
        BillingPrice,
        on_delete=models.SET_NULL,
        related_name="subscriptions",
        null=True,
        blank=True,
    )

    # Provider information
    provider = models.CharField(
        max_length=50,
        choices=[
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("polar", "Polar"),
        ],
    )
    provider_subscription_id = models.CharField(max_length=255)

    # Status
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ACTIVE)
    quantity = models.PositiveIntegerField(default=1)

    # Billing period
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    # Cancellation
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)

    # Trial
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_subscription"
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        unique_together = [("provider", "provider_subscription_id")]

    def __str__(self):
        return f"Subscription({self.customer.user}, {self.status})"

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status in (self.Status.ACTIVE, self.Status.TRIALING)

    @property
    def is_trialing(self) -> bool:
        """Check if subscription is in trial period."""
        return self.status == self.Status.TRIALING

    @property
    def will_cancel(self) -> bool:
        """Check if subscription will cancel at period end."""
        return self.cancel_at_period_end and self.status == self.Status.ACTIVE


class Invoice(models.Model):
    """
    Local representation of an invoice.

    Tracks billing history and payment status.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        PAID = "paid", "Paid"
        UNCOLLECTIBLE = "uncollectible", "Uncollectible"
        VOID = "void", "Void"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Links
    customer = models.ForeignKey(
        BillingCustomer,
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        related_name="invoices",
        null=True,
        blank=True,
    )

    # Provider information
    provider = models.CharField(
        max_length=50,
        choices=[
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("polar", "Polar"),
        ],
    )
    provider_invoice_id = models.CharField(max_length=255)

    # Status and amounts
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    currency = models.CharField(max_length=3, default="usd")
    amount_due = models.PositiveIntegerField(default=0)
    amount_paid = models.PositiveIntegerField(default=0)
    amount_remaining = models.PositiveIntegerField(default=0)

    # URLs
    invoice_pdf = models.URLField(blank=True, null=True)
    hosted_invoice_url = models.URLField(blank=True, null=True)

    # Dates
    due_date = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_invoice"
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        unique_together = [("provider", "provider_invoice_id")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice({self.provider_invoice_id}, {self.status})"

    @property
    def display_amount_due(self) -> str:
        """Return formatted amount due."""
        amount = self.amount_due / 100
        return f"{amount:.2f}"


class WebhookEvent(models.Model):
    """
    Log of webhook events received from billing providers.

    Useful for debugging, auditing, and replay.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Provider information
    provider = models.CharField(
        max_length=50,
        choices=[
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("polar", "Polar"),
        ],
    )
    provider_event_id = models.CharField(max_length=255)

    # Event details
    event_type = models.CharField(max_length=100)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)

    # Raw data
    payload = models.JSONField(default=dict)

    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_webhook_event"
        verbose_name = "Webhook Event"
        verbose_name_plural = "Webhook Events"
        unique_together = [("provider", "provider_event_id")]
        ordering = ["-received_at"]

    def __str__(self):
        return f"WebhookEvent({self.event_type}, {self.provider})"

    def mark_processed(self, error: str = "") -> None:
        """Mark this event as processed."""
        self.processed = True
        self.processed_at = timezone.now()
        if error:
            self.processing_error = error
        self.save(update_fields=["processed", "processed_at", "processing_error"])

    async def amark_processed(self, error: str = "") -> None:
        """Async version of mark_processed. Safe to use in async handlers."""
        self.processed = True
        self.processed_at = timezone.now()
        if error:
            self.processing_error = error
        await self.asave(update_fields=["processed", "processed_at", "processing_error"])


class ConnectedAccount(models.Model):
    """
    Stripe Connect connected account.

    Tracks marketplace sellers/service providers connected to the platform.
    """

    class AccountType(models.TextChoices):
        STANDARD = "standard", "Standard"
        EXPRESS = "express", "Express"
        CUSTOM = "custom", "Custom"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        RESTRICTED = "restricted", "Restricted"
        DISABLED = "disabled", "Disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connected_accounts",
    )

    stripe_account_id = models.CharField(max_length=255, unique=True)
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.STANDARD,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Onboarding state
    charges_enabled = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    details_submitted = models.BooleanField(default=False)

    # Business info
    business_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    country = models.CharField(max_length=2, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_connected_account"
        verbose_name = "Connected Account"
        verbose_name_plural = "Connected Accounts"

    def __str__(self):
        return f"ConnectedAccount({self.stripe_account_id}, {self.account_type})"

    @property
    def is_fully_onboarded(self) -> bool:
        return self.charges_enabled and self.payouts_enabled and self.details_submitted


class Transfer(models.Model):
    """
    Stripe Connect transfer record.

    Tracks money movement from platform to connected accounts.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    connected_account = models.ForeignKey(
        ConnectedAccount,
        on_delete=models.CASCADE,
        related_name="transfers",
    )

    stripe_transfer_id = models.CharField(max_length=255, unique=True)
    amount = models.PositiveIntegerField(help_text="Amount in smallest currency unit")
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    description = models.TextField(blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_transfer"
        verbose_name = "Transfer"
        verbose_name_plural = "Transfers"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transfer({self.stripe_transfer_id}, {self.amount})"


class ApplicationFee(models.Model):
    """
    Stripe Connect application fee record.

    Tracks platform fees collected from connected account payments.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    connected_account = models.ForeignKey(
        ConnectedAccount,
        on_delete=models.CASCADE,
        related_name="application_fees",
    )

    stripe_fee_id = models.CharField(max_length=255, unique=True)
    amount = models.PositiveIntegerField(help_text="Fee amount in smallest currency unit")
    currency = models.CharField(max_length=3, default="usd")
    charge_id = models.CharField(max_length=255, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_application_fee"
        verbose_name = "Application Fee"
        verbose_name_plural = "Application Fees"
        ordering = ["-created_at"]

    def __str__(self):
        return f"ApplicationFee({self.stripe_fee_id}, {self.amount})"


class UsageRecord(models.Model):
    """
    Usage records for metered/usage-based billing.

    Track usage events for billing purposes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Links
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="usage_records",
    )

    # Usage details
    quantity = models.PositiveIntegerField(default=1)
    action = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=255, blank=True)

    # Provider sync
    synced_to_provider = models.BooleanField(default=False)
    provider_record_id = models.CharField(max_length=255, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_matt"
        db_table = "billing_usage_record"
        verbose_name = "Usage Record"
        verbose_name_plural = "Usage Records"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"UsageRecord({self.subscription_id}, {self.quantity})"

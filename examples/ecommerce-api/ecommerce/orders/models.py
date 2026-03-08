"""Order models for e-commerce."""

import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone

from ecommerce.catalog.models import Product, ProductVariant
from ecommerce.users.models import User


class Coupon(models.Model):
    """Discount coupon model."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed Amount"
        FREE_SHIPPING = "free_shipping", "Free Shipping"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    # Discount details
    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)

    # Constraints
    minimum_purchase = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    maximum_discount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # Usage limits
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_limit_per_user = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    # Validity period
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Restrictions (optional)
    applicable_products = models.ManyToManyField(
        Product, blank=True, related_name="applicable_coupons"
    )
    applicable_categories = models.ManyToManyField(
        "catalog.Category", blank=True, related_name="applicable_coupons"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code

    @property
    def is_valid(self) -> bool:
        """Check if coupon is currently valid."""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.usage_limit and self.times_used >= self.usage_limit:
            return False
        return True

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """Calculate discount amount for given subtotal."""
        if not self.is_valid:
            return Decimal("0.00")
        if subtotal < self.minimum_purchase:
            return Decimal("0.00")

        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = subtotal * (self.discount_value / 100)
        elif self.discount_type == self.DiscountType.FIXED:
            discount = self.discount_value
        else:  # Free shipping - handled separately
            return Decimal("0.00")

        # Apply maximum discount cap
        if self.maximum_discount:
            discount = min(discount, self.maximum_discount)

        # Don't exceed subtotal
        return min(discount, subtotal).quantize(Decimal("0.01"))


class Order(models.Model):
    """Order model."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="orders")

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Addresses (snapshots)
    billing_address = models.JSONField()
    shipping_address = models.JSONField()

    # Contact
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)

    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Applied coupon
    coupon = models.ForeignKey(
        Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    coupon_code = models.CharField(max_length=50, blank=True)  # Snapshot

    # Shipping details
    shipping_method = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=200, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Notes
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    # Currency
    currency = models.CharField(max_length=3, default="USD")

    # IP address for fraud detection
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return self.order_number

    def save(self, *args, **kwargs):
        """Generate order number if not set."""
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_number() -> str:
        """Generate a unique order number."""
        import random
        import string

        timestamp = timezone.now().strftime("%Y%m%d")
        random_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ORD-{timestamp}-{random_suffix}"

    def confirm(self) -> None:
        """Confirm the order."""
        self.status = self.Status.CONFIRMED
        self.save(update_fields=["status", "updated_at"])

    def ship(self, tracking_number: str = "") -> None:
        """Mark order as shipped."""
        self.status = self.Status.SHIPPED
        self.tracking_number = tracking_number
        self.shipped_at = timezone.now()
        self.save(update_fields=["status", "tracking_number", "shipped_at", "updated_at"])

    def deliver(self) -> None:
        """Mark order as delivered."""
        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at", "updated_at"])

    def cancel(self) -> None:
        """Cancel the order."""
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])


class OrderItem(models.Model):
    """Order item model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name="order_items"
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )

    # Snapshot of product details at time of order
    product_name = models.CharField(max_length=255)
    variant_name = models.CharField(max_length=255, blank=True)
    sku = models.CharField(max_length=100)

    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Product snapshot for reference
    product_snapshot = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.product_name} x {self.quantity}"

    @property
    def line_total(self) -> Decimal:
        """Calculate line total."""
        return (self.unit_price * self.quantity) - self.discount_amount


class OrderStatusHistory(models.Model):
    """Track order status changes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    notes = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_changes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Order Status History"
        verbose_name_plural = "Order Status History"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order.order_number} - {self.status}"

"""Cart models for e-commerce."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from ecommerce.catalog.models import Product, ProductVariant


class Cart(models.Model):
    """Shopping cart model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # User or session-based cart
    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
    )
    session_key = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    # Applied coupon
    coupon = models.ForeignKey(
        "orders.Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="carts",
    )

    # Notes
    notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        if self.user:
            return f"Cart for {self.user.email}"
        return f"Cart {self.session_key}"

    @property
    def item_count(self) -> int:
        """Return total number of items in cart."""
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self) -> Decimal:
        """Calculate cart subtotal before discounts."""
        return sum(item.line_total for item in self.items.all())

    @property
    def discount_amount(self) -> Decimal:
        """Calculate discount amount."""
        if not self.coupon:
            return Decimal("0.00")
        return self.coupon.calculate_discount(self.subtotal)

    @property
    def tax_amount(self) -> Decimal:
        """Calculate tax amount (placeholder)."""
        taxable_amount = self.subtotal - self.discount_amount
        tax_rate = Decimal(str(getattr(settings, "TAX_RATE_DEFAULT", 0.0875)))
        return (taxable_amount * tax_rate).quantize(Decimal("0.01"))

    @property
    def shipping_amount(self) -> Decimal:
        """Calculate shipping amount (placeholder)."""
        subtotal_after_discount = self.subtotal - self.discount_amount
        free_shipping_threshold = Decimal(str(getattr(settings, "FREE_SHIPPING_THRESHOLD", 50.00)))
        if subtotal_after_discount >= free_shipping_threshold:
            return Decimal("0.00")
        return Decimal(str(getattr(settings, "SHIPPING_FLAT_RATE", 5.99)))

    @property
    def total(self) -> Decimal:
        """Calculate cart total."""
        return self.subtotal - self.discount_amount + self.tax_amount + self.shipping_amount

    def add_item(
        self,
        product: Product,
        quantity: int = 1,
        variant: ProductVariant | None = None,
    ) -> "CartItem":
        """Add item to cart."""
        item, created = CartItem.objects.get_or_create(
            cart=self,
            product=product,
            variant=variant,
            defaults={"quantity": quantity},
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=["quantity", "updated_at"])
        return item

    def remove_item(self, product: Product, variant: ProductVariant | None = None) -> None:
        """Remove item from cart."""
        CartItem.objects.filter(cart=self, product=product, variant=variant).delete()

    def clear(self) -> None:
        """Clear all items from cart."""
        self.items.all().delete()
        self.coupon = None
        self.save(update_fields=["coupon", "updated_at"])

    def merge(self, other_cart: "Cart") -> None:
        """Merge another cart into this one."""
        for item in other_cart.items.all():
            self.add_item(item.product, item.quantity, item.variant)
        other_cart.delete()


class CartItem(models.Model):
    """Cart item model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart_items",
    )

    # Quantity
    quantity = models.PositiveIntegerField(default=1)

    # Price snapshot (optional, for price comparison)
    price_at_add = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        unique_together = ["cart", "product", "variant"]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        variant_str = f" - {self.variant.name}" if self.variant else ""
        return f"{self.product.name}{variant_str} x {self.quantity}"

    @property
    def unit_price(self) -> Decimal:
        """Return unit price (variant price or product price)."""
        if self.variant and self.variant.price:
            return self.variant.price
        return self.product.price

    @property
    def line_total(self) -> Decimal:
        """Calculate line total."""
        return self.unit_price * self.quantity

    @property
    def price_changed(self) -> bool:
        """Check if price has changed since item was added."""
        if self.price_at_add is None:
            return False
        return self.price_at_add != self.unit_price

    def save(self, *args, **kwargs):
        """Capture price at add time."""
        if not self.price_at_add:
            self.price_at_add = self.unit_price
        super().save(*args, **kwargs)

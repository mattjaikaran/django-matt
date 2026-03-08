"""Catalog models for e-commerce."""

import uuid
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.text import slugify
from mptt.models import MPTTModel, TreeForeignKey


class Category(MPTTModel):
    """Hierarchical product category using MPTT."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)

    # MPTT fields
    parent = TreeForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ["display_order", "name"]

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def full_path(self) -> str:
        """Return full category path."""
        ancestors = self.get_ancestors(include_self=True)
        return " > ".join(a.name for a in ancestors)


class Product(models.Model):
    """Product model with full-text search support."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)

    # Categorization
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    tags = models.JSONField(default=list, blank=True)

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # SKU and inventory
    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=100, blank=True)

    # Physical attributes
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, default="kg")
    dimensions = models.JSONField(
        default=dict, blank=True
    )  # {"length": 10, "width": 5, "height": 3}

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)

    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)

    # Product attributes (for filtering)
    attributes = models.JSONField(
        default=dict, blank=True
    )  # {"color": "red", "size": "L"}

    # Full-text search vector
    search_vector = SearchVectorField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["search_vector"]),
            models.Index(fields=["status", "category"]),
            models.Index(fields=["price"]),
            models.Index(fields=["sku"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def is_on_sale(self) -> bool:
        """Check if product is on sale."""
        return bool(self.compare_at_price and self.compare_at_price > self.price)

    @property
    def discount_percentage(self) -> int:
        """Calculate discount percentage."""
        if not self.is_on_sale or not self.compare_at_price:
            return 0
        return int(
            ((self.compare_at_price - self.price) / self.compare_at_price) * 100
        )

    @property
    def primary_image(self) -> "ProductImage | None":
        """Return primary product image."""
        return self.images.filter(is_primary=True).first() or self.images.first()

    @property
    def stock_quantity(self) -> int:
        """Return total stock across all inventory locations."""
        return sum(inv.quantity for inv in self.inventory.all())

    @property
    def in_stock(self) -> bool:
        """Check if product is in stock."""
        return self.stock_quantity > 0


class ProductImage(models.Model):
    """Product image model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"
        ordering = ["-is_primary", "display_order"]

    def __str__(self) -> str:
        return f"{self.product.name} - Image {self.display_order}"

    def save(self, *args, **kwargs):
        """Ensure only one primary image per product."""
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(
                pk=self.pk
            ).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    """Product variant model (e.g., different sizes, colors)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )

    # Variant details
    name = models.CharField(max_length=255)  # e.g., "Red - Large"
    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=100, blank=True)

    # Options
    options = models.JSONField(default=dict)  # {"color": "red", "size": "L"}

    # Pricing (override product price if set)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Physical attributes
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Image
    image = models.ForeignKey(
        ProductImage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variants",
    )

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Variant"
        verbose_name_plural = "Product Variants"
        ordering = ["product", "name"]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.name}"

    @property
    def effective_price(self) -> Decimal:
        """Return variant price or fall back to product price."""
        return self.price if self.price is not None else self.product.price


class Inventory(models.Model):
    """Inventory tracking model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="inventory"
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inventory",
    )

    # Location (for multi-warehouse)
    location = models.CharField(max_length=100, default="default")

    # Quantities
    quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)  # Reserved for pending orders
    reorder_level = models.IntegerField(default=10)
    reorder_quantity = models.IntegerField(default=50)

    # Tracking
    last_restocked_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventory"
        verbose_name_plural = "Inventory"
        unique_together = ["product", "variant", "location"]
        ordering = ["product", "location"]

    def __str__(self) -> str:
        variant_str = f" - {self.variant.name}" if self.variant else ""
        return f"{self.product.name}{variant_str} @ {self.location}"

    @property
    def available_quantity(self) -> int:
        """Return quantity minus reserved."""
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def needs_reorder(self) -> bool:
        """Check if inventory is below reorder level."""
        return self.available_quantity <= self.reorder_level

    def reserve(self, quantity: int) -> bool:
        """Reserve inventory for an order."""
        if self.available_quantity >= quantity:
            self.reserved_quantity += quantity
            self.save(update_fields=["reserved_quantity", "updated_at"])
            return True
        return False

    def release(self, quantity: int) -> None:
        """Release reserved inventory."""
        self.reserved_quantity = max(0, self.reserved_quantity - quantity)
        self.save(update_fields=["reserved_quantity", "updated_at"])

    def commit(self, quantity: int) -> None:
        """Commit reserved inventory (order confirmed)."""
        self.reserved_quantity = max(0, self.reserved_quantity - quantity)
        self.quantity = max(0, self.quantity - quantity)
        self.save(update_fields=["reserved_quantity", "quantity", "updated_at"])


class InventoryMovement(models.Model):
    """Track inventory movements for audit."""

    class MovementType(models.TextChoices):
        RECEIVED = "received", "Received"
        SOLD = "sold", "Sold"
        RETURNED = "returned", "Returned"
        ADJUSTED = "adjusted", "Adjusted"
        RESERVED = "reserved", "Reserved"
        RELEASED = "released", "Released"
        TRANSFERRED = "transferred", "Transferred"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(
        Inventory, on_delete=models.CASCADE, related_name="movements"
    )

    # Movement details
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.IntegerField()  # Positive for in, negative for out
    quantity_before = models.IntegerField()
    quantity_after = models.IntegerField()

    # Reference
    reference = models.CharField(max_length=255, blank=True)  # Order ID, etc.
    notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
    )

    class Meta:
        verbose_name = "Inventory Movement"
        verbose_name_plural = "Inventory Movements"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.movement_type} {self.quantity} for {self.inventory}"

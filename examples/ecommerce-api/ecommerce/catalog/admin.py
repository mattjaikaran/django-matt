"""Django admin configuration for catalog app."""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display

from ecommerce.catalog.models import (
    Category,
    Inventory,
    InventoryMovement,
    Product,
    ProductImage,
    ProductVariant,
)


class ProductImageInline(TabularInline):
    """Inline for product images."""

    model = ProductImage
    extra = 1
    fields = ["image", "alt_text", "is_primary", "display_order"]


class ProductVariantInline(TabularInline):
    """Inline for product variants."""

    model = ProductVariant
    extra = 0
    fields = ["name", "sku", "options", "price", "is_active"]


class InventoryInline(TabularInline):
    """Inline for inventory."""

    model = Inventory
    extra = 0
    fields = ["location", "quantity", "reserved_quantity", "reorder_level"]
    readonly_fields = ["reserved_quantity"]


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    """Admin for Category model."""

    list_display = ["name", "parent", "is_active", "display_order", "product_count"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["tree_id", "lft"]

    @display(description="Products")
    def product_count(self, obj):
        return obj.products.filter(status="active").count()


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    """Admin for Product model."""

    list_display = [
        "name",
        "sku",
        "display_price",
        "display_stock",
        "status",
        "is_featured",
        "created_at",
    ]
    list_filter = ["status", "is_featured", "category", "created_at"]
    search_fields = ["name", "sku", "description"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ProductImageInline, ProductVariantInline, InventoryInline]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": [
                    "name",
                    "slug",
                    "description",
                    "short_description",
                    "category",
                    "tags",
                ]
            },
        ),
        (
            "Pricing",
            {
                "fields": [
                    "price",
                    "compare_at_price",
                    "cost_price",
                ]
            },
        ),
        (
            "Inventory",
            {
                "fields": [
                    "sku",
                    "barcode",
                ]
            },
        ),
        (
            "Physical Attributes",
            {
                "fields": [
                    "weight",
                    "weight_unit",
                    "dimensions",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Status",
            {
                "fields": [
                    "status",
                    "is_featured",
                ]
            },
        ),
        (
            "SEO",
            {
                "fields": [
                    "meta_title",
                    "meta_description",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Attributes",
            {
                "fields": ["attributes"],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": [
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    @display(description="Price")
    def display_price(self, obj):
        if obj.is_on_sale:
            return format_html(
                '<span style="text-decoration: line-through;">${}</span> '
                '<span style="color: green;">${}</span>',
                obj.compare_at_price,
                obj.price,
            )
        return f"${obj.price}"

    @display(description="Stock")
    def display_stock(self, obj):
        stock = obj.stock_quantity
        if stock == 0:
            return format_html('<span style="color: red;">Out of Stock</span>')
        elif stock <= 10:
            return format_html(
                '<span style="color: orange;">{} (Low)</span>', stock
            )
        return stock

    @action(description="Mark as featured")
    def make_featured(self, request, queryset):
        queryset.update(is_featured=True)

    @action(description="Mark as not featured")
    def remove_featured(self, request, queryset):
        queryset.update(is_featured=False)

    @action(description="Activate products")
    def activate(self, request, queryset):
        queryset.update(status="active")

    @action(description="Archive products")
    def archive(self, request, queryset):
        queryset.update(status="archived")

    actions = ["make_featured", "remove_featured", "activate", "archive"]


@admin.register(Inventory)
class InventoryAdmin(ModelAdmin):
    """Admin for Inventory model."""

    list_display = [
        "product",
        "variant",
        "location",
        "quantity",
        "reserved_quantity",
        "available_display",
        "needs_reorder_display",
    ]
    list_filter = ["location"]
    search_fields = ["product__name", "product__sku", "variant__name", "variant__sku"]
    readonly_fields = ["created_at", "updated_at"]

    @display(description="Available")
    def available_display(self, obj):
        return obj.available_quantity

    @display(description="Needs Reorder", boolean=True)
    def needs_reorder_display(self, obj):
        return obj.needs_reorder


@admin.register(InventoryMovement)
class InventoryMovementAdmin(ModelAdmin):
    """Admin for InventoryMovement model."""

    list_display = [
        "inventory",
        "movement_type",
        "quantity",
        "quantity_before",
        "quantity_after",
        "reference",
        "created_at",
    ]
    list_filter = ["movement_type", "created_at"]
    search_fields = ["inventory__product__name", "reference"]
    readonly_fields = [
        "inventory",
        "movement_type",
        "quantity",
        "quantity_before",
        "quantity_after",
        "created_at",
    ]
    date_hierarchy = "created_at"


@admin.register(ProductImage)
class ProductImageAdmin(ModelAdmin):
    """Admin for ProductImage model."""

    list_display = ["product", "alt_text", "is_primary", "display_order"]
    list_filter = ["is_primary"]
    search_fields = ["product__name", "alt_text"]


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    """Admin for ProductVariant model."""

    list_display = ["product", "name", "sku", "price", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["product__name", "name", "sku"]

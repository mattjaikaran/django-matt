"""Django admin configuration for orders app."""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display

from ecommerce.orders.models import Coupon, Order, OrderItem, OrderStatusHistory


class OrderItemInline(TabularInline):
    """Inline for order items."""

    model = OrderItem
    extra = 0
    readonly_fields = [
        "product",
        "variant",
        "product_name",
        "variant_name",
        "sku",
        "unit_price",
        "quantity",
        "discount_amount",
        "total",
    ]
    can_delete = False


class OrderStatusHistoryInline(TabularInline):
    """Inline for order status history."""

    model = OrderStatusHistory
    extra = 0
    readonly_fields = ["status", "notes", "changed_by", "created_at"]
    can_delete = False
    ordering = ["-created_at"]


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    """Admin for Order model."""

    list_display = [
        "order_number",
        "user_email",
        "status_display",
        "total_display",
        "item_count",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["order_number", "email", "user__email"]
    readonly_fields = [
        "order_number",
        "user",
        "subtotal",
        "discount_amount",
        "tax_amount",
        "shipping_amount",
        "total",
        "coupon",
        "coupon_code",
        "ip_address",
        "created_at",
        "updated_at",
    ]
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    date_hierarchy = "created_at"
    fieldsets = [
        (
            "Order Information",
            {
                "fields": [
                    "order_number",
                    "user",
                    "status",
                    "email",
                    "phone",
                ]
            },
        ),
        (
            "Totals",
            {
                "fields": [
                    "subtotal",
                    "discount_amount",
                    "tax_amount",
                    "shipping_amount",
                    "total",
                    "currency",
                ]
            },
        ),
        (
            "Coupon",
            {
                "fields": [
                    "coupon",
                    "coupon_code",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Shipping",
            {
                "fields": [
                    "shipping_method",
                    "tracking_number",
                    "shipped_at",
                    "delivered_at",
                ]
            },
        ),
        (
            "Addresses",
            {
                "fields": [
                    "billing_address",
                    "shipping_address",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Notes",
            {
                "fields": [
                    "customer_notes",
                    "internal_notes",
                ]
            },
        ),
        (
            "Metadata",
            {
                "fields": [
                    "ip_address",
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    @display(description="Customer")
    def user_email(self, obj):
        return obj.email

    @display(description="Status")
    def status_display(self, obj):
        colors = {
            "pending": "gray",
            "confirmed": "blue",
            "processing": "orange",
            "shipped": "purple",
            "delivered": "green",
            "cancelled": "red",
            "refunded": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @display(description="Total")
    def total_display(self, obj):
        return f"${obj.total}"

    @display(description="Items")
    def item_count(self, obj):
        return obj.items.count()

    @action(description="Mark as confirmed")
    def confirm_orders(self, request, queryset):
        from ecommerce.orders.models import OrderStatusHistory

        for order in queryset.filter(status="pending"):
            order.status = Order.Status.CONFIRMED
            order.save()
            OrderStatusHistory.objects.create(
                order=order,
                status=Order.Status.CONFIRMED,
                notes="Confirmed via admin",
                changed_by=request.user,
            )

    @action(description="Mark as shipped")
    def ship_orders(self, request, queryset):
        from django.utils import timezone

        from ecommerce.orders.models import OrderStatusHistory

        for order in queryset.filter(status__in=["confirmed", "processing"]):
            order.status = Order.Status.SHIPPED
            order.shipped_at = timezone.now()
            order.save()
            OrderStatusHistory.objects.create(
                order=order,
                status=Order.Status.SHIPPED,
                notes="Shipped via admin",
                changed_by=request.user,
            )

    @action(description="Mark as delivered")
    def deliver_orders(self, request, queryset):
        from django.utils import timezone

        from ecommerce.orders.models import OrderStatusHistory

        for order in queryset.filter(status="shipped"):
            order.status = Order.Status.DELIVERED
            order.delivered_at = timezone.now()
            order.save()
            OrderStatusHistory.objects.create(
                order=order,
                status=Order.Status.DELIVERED,
                notes="Delivered via admin",
                changed_by=request.user,
            )

    actions = ["confirm_orders", "ship_orders", "deliver_orders"]


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    """Admin for Coupon model."""

    list_display = [
        "code",
        "discount_display",
        "times_used",
        "usage_limit",
        "valid_display",
        "is_active",
    ]
    list_filter = ["discount_type", "is_active"]
    search_fields = ["code", "description"]
    readonly_fields = ["times_used", "created_at", "updated_at"]
    fieldsets = [
        (
            "Basic",
            {
                "fields": [
                    "code",
                    "description",
                    "is_active",
                ]
            },
        ),
        (
            "Discount",
            {
                "fields": [
                    "discount_type",
                    "discount_value",
                    "minimum_purchase",
                    "maximum_discount",
                ]
            },
        ),
        (
            "Usage Limits",
            {
                "fields": [
                    "usage_limit",
                    "usage_limit_per_user",
                    "times_used",
                ]
            },
        ),
        (
            "Validity",
            {
                "fields": [
                    "valid_from",
                    "valid_until",
                ]
            },
        ),
        (
            "Restrictions",
            {
                "fields": [
                    "applicable_products",
                    "applicable_categories",
                ],
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
    filter_horizontal = ["applicable_products", "applicable_categories"]

    @display(description="Discount")
    def discount_display(self, obj):
        if obj.discount_type == "percentage":
            return f"{obj.discount_value}%"
        elif obj.discount_type == "fixed":
            return f"${obj.discount_value}"
        return "Free Shipping"

    @display(description="Valid", boolean=True)
    def valid_display(self, obj):
        return obj.is_valid

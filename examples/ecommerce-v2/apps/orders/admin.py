from django.contrib import admin

from apps.orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "store",
        "status",
        "subtotal",
        "total",
        "created_at",
    )
    list_filter = ("status", "created_at", "store")
    search_fields = ("user__email", "stripe_payment_intent_id")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "product",
        "variant",
        "quantity",
        "unit_price",
        "total_price",
    )
    list_filter = ("created_at",)
    search_fields = ("product__name",)
    readonly_fields = ("id", "created_at", "updated_at")

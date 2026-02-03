"""Django admin configuration for cart app."""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from ecommerce.cart.models import Cart, CartItem


class CartItemInline(TabularInline):
    """Inline for cart items."""

    model = CartItem
    extra = 0
    fields = ["product", "variant", "quantity", "unit_price", "line_total"]
    readonly_fields = ["unit_price", "line_total"]

    @display(description="Unit Price")
    def unit_price(self, obj):
        return f"${obj.unit_price}"

    @display(description="Line Total")
    def line_total(self, obj):
        return f"${obj.line_total}"


@admin.register(Cart)
class CartAdmin(ModelAdmin):
    """Admin for Cart model."""

    list_display = [
        "id_short",
        "user",
        "session_key_short",
        "item_count_display",
        "total_display",
        "updated_at",
    ]
    list_filter = ["updated_at"]
    search_fields = ["user__email", "session_key"]
    readonly_fields = [
        "user",
        "session_key",
        "coupon",
        "created_at",
        "updated_at",
    ]
    inlines = [CartItemInline]

    @display(description="ID")
    def id_short(self, obj):
        return str(obj.id)[:8]

    @display(description="Session")
    def session_key_short(self, obj):
        if obj.session_key:
            return obj.session_key[:12] + "..."
        return "-"

    @display(description="Items")
    def item_count_display(self, obj):
        return obj.item_count

    @display(description="Total")
    def total_display(self, obj):
        return f"${obj.total}"


@admin.register(CartItem)
class CartItemAdmin(ModelAdmin):
    """Admin for CartItem model."""

    list_display = [
        "cart",
        "product",
        "variant",
        "quantity",
        "unit_price_display",
        "line_total_display",
    ]
    list_filter = ["created_at"]
    search_fields = ["cart__user__email", "product__name"]
    readonly_fields = ["created_at", "updated_at"]

    @display(description="Unit Price")
    def unit_price_display(self, obj):
        return f"${obj.unit_price}"

    @display(description="Total")
    def line_total_display(self, obj):
        return f"${obj.line_total}"

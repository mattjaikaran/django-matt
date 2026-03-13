from django.contrib import admin

from apps.cart.models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("user__email",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "variant", "quantity", "created_at")
    list_filter = ("created_at",)
    search_fields = ("product__name",)
    readonly_fields = ("id", "created_at", "updated_at")

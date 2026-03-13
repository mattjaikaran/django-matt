from django.contrib import admin

from apps.catalog.models import Category, Inventory, Product, Variant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ["parent"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "store", "category", "price", "is_active", "created_at"]
    list_filter = ["is_active", "category", "created_at"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ["store", "category"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "product", "price_override", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "sku"]
    raw_id_fields = ["product"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ["variant", "quantity", "low_stock_threshold", "is_low_stock"]
    list_filter = ["low_stock_threshold"]
    raw_id_fields = ["variant"]
    readonly_fields = ["id", "created_at", "updated_at"]

    @admin.display(boolean=True, description="Low Stock")
    def is_low_stock(self, obj):
        return obj.is_low_stock

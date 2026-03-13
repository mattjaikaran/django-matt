from django.contrib import admin

from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "product", "rating", "is_verified_purchase", "created_at"]
    list_filter = ["rating", "is_verified_purchase", "created_at"]
    search_fields = ["title", "body", "user__email"]
    raw_id_fields = ["user", "product"]
    readonly_fields = ["id", "created_at", "updated_at"]

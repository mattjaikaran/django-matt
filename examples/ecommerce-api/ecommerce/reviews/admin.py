"""Django admin configuration for reviews app."""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display

from ecommerce.reviews.models import Review, ReviewImage, ReviewVote


class ReviewImageInline(TabularInline):
    """Inline for review images."""

    model = ReviewImage
    extra = 0
    fields = ["image", "caption", "display_order"]


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    """Admin for Review model."""

    list_display = [
        "product",
        "user",
        "rating_display",
        "status_display",
        "verified_purchase",
        "helpful_display",
        "created_at",
    ]
    list_filter = ["status", "rating", "verified_purchase", "created_at"]
    search_fields = ["product__name", "user__email", "title", "content"]
    readonly_fields = [
        "product",
        "user",
        "order",
        "verified_purchase",
        "helpful_votes",
        "not_helpful_votes",
        "created_at",
        "updated_at",
        "moderated_by",
        "moderated_at",
    ]
    inlines = [ReviewImageInline]
    date_hierarchy = "created_at"
    fieldsets = [
        (
            "Review",
            {
                "fields": [
                    "product",
                    "user",
                    "order",
                    "verified_purchase",
                ]
            },
        ),
        (
            "Content",
            {
                "fields": [
                    "rating",
                    "title",
                    "content",
                    "pros",
                    "cons",
                ]
            },
        ),
        (
            "Status",
            {
                "fields": [
                    "status",
                    "moderation_notes",
                    "moderated_by",
                    "moderated_at",
                ]
            },
        ),
        (
            "Engagement",
            {
                "fields": [
                    "helpful_votes",
                    "not_helpful_votes",
                ]
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

    @display(description="Rating")
    def rating_display(self, obj):
        stars = "★" * obj.rating + "☆" * (5 - obj.rating)
        return format_html('<span style="color: gold;">{}</span>', stars)

    @display(description="Status")
    def status_display(self, obj):
        colors = {
            "pending": "orange",
            "approved": "green",
            "rejected": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display(),
        )

    @display(description="Helpful")
    def helpful_display(self, obj):
        total = obj.helpful_votes + obj.not_helpful_votes
        if total == 0:
            return "-"
        percentage = int((obj.helpful_votes / total) * 100)
        return f"{obj.helpful_votes}/{total} ({percentage}%)"

    @action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        from django.utils import timezone

        updated = queryset.filter(status="pending").update(
            status="approved",
            moderated_by=request.user,
            moderated_at=timezone.now(),
        )
        self.message_user(request, f"{updated} reviews approved.")

    @action(description="Reject selected reviews")
    def reject_reviews(self, request, queryset):
        from django.utils import timezone

        updated = queryset.filter(status="pending").update(
            status="rejected",
            moderated_by=request.user,
            moderated_at=timezone.now(),
        )
        self.message_user(request, f"{updated} reviews rejected.")

    actions = ["approve_reviews", "reject_reviews"]


@admin.register(ReviewImage)
class ReviewImageAdmin(ModelAdmin):
    """Admin for ReviewImage model."""

    list_display = ["review", "caption", "display_order"]
    search_fields = ["review__product__name", "caption"]


@admin.register(ReviewVote)
class ReviewVoteAdmin(ModelAdmin):
    """Admin for ReviewVote model."""

    list_display = ["review", "user", "is_helpful", "created_at"]
    list_filter = ["is_helpful", "created_at"]
    search_fields = ["review__product__name", "user__email"]

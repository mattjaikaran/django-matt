"""
Django admin integration for experiments.

Provides admin classes for managing experiments through Django admin.
Compatible with Django Unfold admin theme.

Usage:
    # In your admin.py
    from django.contrib import admin
    from django_matt.experiments.admin import (
        ExperimentAdmin,
        VariantAdmin,
        ExperimentAssignmentAdmin,
    )
    from django_matt.experiments.models import (
        Experiment,
        Variant,
        ExperimentAssignment,
    )

    admin.site.register(Experiment, ExperimentAdmin)
    admin.site.register(Variant, VariantAdmin)
    admin.site.register(ExperimentAssignment, ExperimentAssignmentAdmin)
"""

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html


class VariantInline(admin.TabularInline):
    """Inline admin for variants within an experiment."""

    model = None  # Set dynamically
    extra = 0
    fields = ["key", "name", "is_control", "weight", "payload"]
    readonly_fields = []

    def __init__(self, parent_model, admin_site):
        from django_matt.experiments.models import Variant

        self.model = Variant
        super().__init__(parent_model, admin_site)


class ExperimentAdmin(admin.ModelAdmin):
    """Admin for Experiment model."""

    list_display = [
        "key",
        "name",
        "status_badge",
        "strategy",
        "total_participants",
        "winner_badge",
        "created_at",
    ]
    list_filter = ["status", "strategy", "exclusion_group", "created_at"]
    search_fields = ["key", "name", "description"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "start_date",
        "end_date",
        "winner_variant_id",
        "winner_confidence",
        "winner_detected_at",
        "total_participants",
    ]
    fieldsets = [
        (None, {"fields": ["key", "name", "description", "status"]}),
        ("Strategy", {"fields": ["strategy", "epsilon", "exploration_weight"]}),
        (
            "Statistics",
            {
                "fields": [
                    "min_sample_size",
                    "target_confidence",
                    "primary_metric",
                    "secondary_metrics",
                ]
            },
        ),
        (
            "Targeting",
            {
                "fields": [
                    "exclusion_group",
                    "holdout_percentage",
                    "targeting_rules",
                    "feature_flag_key",
                ]
            },
        ),
        (
            "Timing",
            {
                "fields": ["start_date", "end_date"],
                "classes": ["collapse"],
            },
        ),
        (
            "Winner",
            {
                "fields": [
                    "winner_variant_id",
                    "winner_confidence",
                    "winner_detected_at",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Metadata",
            {
                "fields": ["metadata", "created_at", "updated_at", "created_by"],
                "classes": ["collapse"],
            },
        ),
    ]
    actions = ["start_experiments", "pause_experiments", "complete_experiments"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_participant_count=Count("assignments"))

    def total_participants(self, obj):
        return getattr(obj, "_participant_count", obj.total_participants)

    total_participants.short_description = "Participants"
    total_participants.admin_order_field = "_participant_count"

    def status_badge(self, obj):
        colors = {
            "draft": "#6c757d",
            "running": "#28a745",
            "paused": "#ffc107",
            "completed": "#007bff",
            "archived": "#6c757d",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"

    def winner_badge(self, obj):
        if obj.has_winner:
            return format_html('<span style="color: #28a745;">Winner Found</span>')
        return "-"

    winner_badge.short_description = "Winner"

    @admin.action(description="Start selected experiments")
    def start_experiments(self, request, queryset):
        from django_matt.experiments.models import ExperimentStatus

        count = 0
        for exp in queryset.filter(status=ExperimentStatus.DRAFT.value):
            try:
                exp.start()
                count += 1
            except ValueError:
                pass
        self.message_user(request, f"Started {count} experiments.")

    @admin.action(description="Pause selected experiments")
    def pause_experiments(self, request, queryset):
        from django_matt.experiments.models import ExperimentStatus

        count = 0
        for exp in queryset.filter(status=ExperimentStatus.RUNNING.value):
            try:
                exp.pause()
                count += 1
            except ValueError:
                pass
        self.message_user(request, f"Paused {count} experiments.")

    @admin.action(description="Complete selected experiments")
    def complete_experiments(self, request, queryset):
        count = 0
        for exp in queryset:
            try:
                exp.complete()
                count += 1
            except ValueError:
                pass
        self.message_user(request, f"Completed {count} experiments.")


class VariantAdmin(admin.ModelAdmin):
    """Admin for Variant model."""

    list_display = [
        "key",
        "experiment",
        "name",
        "is_control",
        "weight",
        "assignment_count",
        "conversion_rate_display",
    ]
    list_filter = ["is_control", "experiment"]
    search_fields = ["key", "name", "experiment__key"]
    readonly_fields = ["id", "created_at", "assignment_count", "conversion_count"]

    def assignment_count(self, obj):
        return obj.assignments.count()

    assignment_count.short_description = "Assignments"

    def conversion_rate_display(self, obj):
        rate = obj.conversion_rate
        return f"{rate:.2%}"

    conversion_rate_display.short_description = "Conversion Rate"


class ExperimentAssignmentAdmin(admin.ModelAdmin):
    """Admin for ExperimentAssignment model."""

    list_display = [
        "experiment",
        "variant",
        "user_display",
        "is_holdout",
        "assigned_at",
    ]
    list_filter = ["is_holdout", "experiment", "assigned_at"]
    search_fields = ["experiment__key", "user__email", "anonymous_id"]
    readonly_fields = [
        "id",
        "experiment",
        "variant",
        "user",
        "anonymous_id",
        "assigned_at",
        "context",
    ]
    raw_id_fields = ["user"]

    def user_display(self, obj):
        if obj.user:
            return obj.user.email or str(obj.user)
        return f"Anonymous: {obj.anonymous_id[:12]}..."

    user_display.short_description = "User"


class ExperimentResultAdmin(admin.ModelAdmin):
    """Admin for ExperimentResult model."""

    list_display = [
        "assignment",
        "metric_name",
        "metric_type",
        "value",
        "timestamp",
    ]
    list_filter = ["metric_type", "metric_name", "timestamp"]
    search_fields = ["assignment__experiment__key", "metric_name"]
    readonly_fields = ["id", "assignment", "variant", "timestamp"]


class ExperimentAuditLogAdmin(admin.ModelAdmin):
    """Admin for ExperimentAuditLog model."""

    list_display = [
        "experiment_key",
        "action",
        "user",
        "created_at",
    ]
    list_filter = ["action", "created_at"]
    search_fields = ["experiment_key", "action"]
    readonly_fields = [
        "id",
        "experiment",
        "experiment_key",
        "action",
        "changes",
        "old_values",
        "new_values",
        "user",
        "ip_address",
        "created_at",
    ]


# Auto-register if models are available
def register_admin():
    """Register experiment models with Django admin."""
    from django_matt.experiments.models import (
        Experiment,
        ExperimentAssignment,
        ExperimentAuditLog,
        ExperimentResult,
        Variant,
    )

    # Only register if not already registered
    if Experiment not in admin.site._registry:
        admin.site.register(Experiment, ExperimentAdmin)

    if Variant not in admin.site._registry:
        admin.site.register(Variant, VariantAdmin)

    if ExperimentAssignment not in admin.site._registry:
        admin.site.register(ExperimentAssignment, ExperimentAssignmentAdmin)

    if ExperimentResult not in admin.site._registry:
        admin.site.register(ExperimentResult, ExperimentResultAdmin)

    if ExperimentAuditLog not in admin.site._registry:
        admin.site.register(ExperimentAuditLog, ExperimentAuditLogAdmin)


__all__ = [
    "ExperimentAdmin",
    "VariantAdmin",
    "ExperimentAssignmentAdmin",
    "ExperimentResultAdmin",
    "ExperimentAuditLogAdmin",
    "VariantInline",
    "register_admin",
]

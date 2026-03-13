from django.contrib import admin

from apps.projects.models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "organization", "environment", "is_active", "created_at"]
    list_filter = ["environment", "is_active", "created_at"]
    search_fields = ["name", "slug", "description"]
    raw_id_fields = ["organization"]
    readonly_fields = ["id", "created_at", "updated_at"]

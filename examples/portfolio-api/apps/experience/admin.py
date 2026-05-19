from django.contrib import admin

from apps.experience.models import Experience


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("role", "company", "location", "start_date", "end_date", "is_current", "order")
    list_filter = ("is_current",)
    search_fields = ("company", "role", "description")
    ordering = ("order", "-start_date")

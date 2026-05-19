from django.contrib import admin

from apps.skills.models import Skill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "level", "order")
    list_filter = ("category",)
    search_fields = ("name",)
    ordering = ("category", "order", "name")

"""Admin configuration for users app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin

from blog.users.models import AuthorProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ["email", "username", "full_name", "is_staff", "is_active", "date_joined"]
    list_filter = ["is_staff", "is_active", "date_joined"]
    search_fields = ["email", "username", "first_name", "last_name"]
    ordering = ["-date_joined"]
    fieldsets = BaseUserAdmin.fieldsets + (("Profile", {"fields": ()}),)


@admin.register(AuthorProfile)
class AuthorProfileAdmin(ModelAdmin):
    list_display = ["user", "location", "website"]
    search_fields = ["user__email", "user__username", "bio"]
    raw_id_fields = ["user"]

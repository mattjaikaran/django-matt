from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "name", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_active")
    search_fields = ("email", "name")
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {"fields": ("name", "bio", "avatar_url", "github_url", "linkedin_url", "website_url")},
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "password1", "password2"),
            },
        ),
    )

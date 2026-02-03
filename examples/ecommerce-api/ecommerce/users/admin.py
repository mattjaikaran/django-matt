"""Django admin configuration for users app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from ecommerce.users.models import Address, User, Wishlist, WishlistItem


class AddressInline(TabularInline):
    """Inline for user addresses."""

    model = Address
    extra = 0
    fields = [
        "address_type",
        "is_default",
        "address_line_1",
        "city",
        "state",
        "postal_code",
        "country",
    ]


class WishlistInline(TabularInline):
    """Inline for user wishlists."""

    model = Wishlist
    extra = 0
    fields = ["name", "is_public"]
    readonly_fields = ["name"]


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    """Admin for User model."""

    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = [
        "email",
        "full_name",
        "is_active",
        "is_staff",
        "order_count",
        "created_at",
    ]
    list_filter = ["is_active", "is_staff", "is_superuser", "created_at"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["-created_at"]
    inlines = [AddressInline, WishlistInline]

    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        (
            "Personal Info",
            {
                "fields": [
                    "first_name",
                    "last_name",
                    "phone",
                    "date_of_birth",
                    "avatar",
                ]
            },
        ),
        (
            "Preferences",
            {
                "fields": [
                    "accepts_marketing",
                ]
            },
        ),
        (
            "Permissions",
            {
                "fields": [
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Important dates",
            {
                "fields": [
                    "last_login",
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                ],
            },
        ),
    ]

    readonly_fields = ["created_at", "updated_at", "last_login"]

    @display(description="Orders")
    def order_count(self, obj):
        return obj.orders.count()


@admin.register(Address)
class AddressAdmin(ModelAdmin):
    """Admin for Address model."""

    list_display = [
        "user",
        "address_type",
        "is_default",
        "city",
        "state",
        "country",
    ]
    list_filter = ["address_type", "is_default", "country"]
    search_fields = ["user__email", "address_line_1", "city"]


@admin.register(Wishlist)
class WishlistAdmin(ModelAdmin):
    """Admin for Wishlist model."""

    list_display = ["user", "name", "is_public", "item_count", "created_at"]
    list_filter = ["is_public", "created_at"]
    search_fields = ["user__email", "name"]

    @display(description="Items")
    def item_count(self, obj):
        return obj.items.count()


@admin.register(WishlistItem)
class WishlistItemAdmin(ModelAdmin):
    """Admin for WishlistItem model."""

    list_display = ["wishlist", "product", "priority", "added_at"]
    list_filter = ["added_at"]
    search_fields = ["wishlist__name", "product__name"]

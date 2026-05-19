"""Admin configuration for posts app."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from blog.posts.models import Category, Post, PostView, Tag


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "slug", "parent"]
    list_filter = ["parent"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ["parent"]


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "status", "featured", "view_count", "published_at", "created_at"]
    list_filter = ["status", "featured", "category", "tags"]
    search_fields = ["title", "content", "excerpt"]
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ["author", "category"]
    filter_horizontal = ["tags"]
    readonly_fields = ["view_count", "created_at", "updated_at"]
    date_hierarchy = "published_at"
    fieldsets = (
        (None, {"fields": ("title", "slug", "author", "status", "featured")}),
        ("Content", {"fields": ("content", "excerpt", "cover_image")}),
        ("Taxonomy", {"fields": ("category", "tags")}),
        ("SEO", {"fields": ("seo_title", "seo_description")}),
        ("Dates", {"fields": ("published_at", "created_at", "updated_at")}),
        ("Analytics", {"fields": ("view_count",)}),
    )


@admin.register(PostView)
class PostViewAdmin(ModelAdmin):
    list_display = ["post", "session_key", "ip_address", "created_at"]
    list_filter = ["created_at"]
    readonly_fields = ["post", "session_key", "ip_address", "created_at"]
    date_hierarchy = "created_at"

"""Django admin for SiteConfig."""

from django.contrib import admin

from .models import SiteConfig


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    """Admin panel for site configuration."""

    fieldsets = (
        ("Site Info", {"fields": ("site_name", "tagline", "description", "about_text")}),
        ("Contact", {"fields": ("email", "phone", "location")}),
        ("Social Links", {"fields": ("github_url", "linkedin_url", "twitter_url", "resume_url")}),
        ("SEO", {"fields": ("meta_description", "meta_keywords", "google_analytics_id")}),
    )

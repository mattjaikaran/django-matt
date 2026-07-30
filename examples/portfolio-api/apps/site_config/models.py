"""Site configuration model for portfolio metadata."""

from django.db import models

from apps.core.models import BaseModel


class SiteConfig(BaseModel):
    """Singleton model for site-wide configuration.

    Stores metadata displayed in the portfolio header, SEO tags,
    and social media previews. Only one instance should exist.
    """

    site_name = models.CharField(max_length=100, default="My Portfolio")
    tagline = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    about_text = models.TextField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    location = models.CharField(max_length=255, blank=True, default="")

    # Social links
    github_url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")
    twitter_url = models.URLField(blank=True, default="")
    resume_url = models.URLField(blank=True, default="")

    # SEO
    meta_description = models.CharField(max_length=160, blank=True, default="")
    meta_keywords = models.CharField(max_length=255, blank=True, default="")
    google_analytics_id = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configuration"

    def __str__(self) -> str:
        return self.site_name

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteConfig":
        """Get the site config, creating defaults if none exists."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

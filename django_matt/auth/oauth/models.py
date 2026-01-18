"""
Django models for storing OAuth connections.
"""

from django.conf import settings
from django.db import models


class OAuthConnection(models.Model):
    """
    Stores a user's connection to an OAuth provider.

    Each user can have multiple connections (e.g., connected to both
    Google and GitHub).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_connections",
    )

    # Provider information
    provider = models.CharField(
        max_length=50,
        db_index=True,
        help_text="OAuth provider name (e.g., 'google', 'github')",
    )
    provider_user_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="User ID from the OAuth provider",
    )

    # User info from provider (may be updated on each login)
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email from OAuth provider",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Name from OAuth provider",
    )
    picture = models.URLField(
        blank=True,
        default="",
        help_text="Profile picture URL from OAuth provider",
    )

    # Tokens (optional - only store if you need to make API calls)
    access_token = models.TextField(
        blank=True,
        default="",
        help_text="OAuth access token (encrypted in production)",
    )
    refresh_token = models.TextField(
        blank=True,
        default="",
        help_text="OAuth refresh token (encrypted in production)",
    )
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the access token expires",
    )

    # Raw data from provider (for debugging/auditing)
    raw_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw user data from OAuth provider",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "django_matt_oauth_connections"
        verbose_name = "OAuth Connection"
        verbose_name_plural = "OAuth Connections"
        # Each user can only have one connection per provider
        unique_together = [("user", "provider")]
        # Also index provider + provider_user_id for lookups
        indexes = [
            models.Index(fields=["provider", "provider_user_id"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.provider}"

    @classmethod
    def get_or_none(cls, provider: str, provider_user_id: str):
        """Get an OAuth connection by provider and provider user ID."""
        try:
            return cls.objects.select_related("user").get(
                provider=provider,
                provider_user_id=provider_user_id,
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_for_user(cls, user, provider: str):
        """Get a user's connection to a specific provider."""
        try:
            return cls.objects.get(user=user, provider=provider)
        except cls.DoesNotExist:
            return None

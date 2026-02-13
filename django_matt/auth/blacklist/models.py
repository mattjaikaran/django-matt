"""Token blacklist database model."""

from django.db import models


class BlacklistedToken(models.Model):
    """Stores blacklisted JWT tokens for revocation."""

    jti = models.CharField(max_length=255, unique=True, db_index=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        app_label = "django_matt"

    def __str__(self):
        return f"BlacklistedToken({self.jti})"

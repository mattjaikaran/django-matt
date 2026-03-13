import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.projects.models import Project


class APIKey(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=255)
    key_prefix = models.CharField(max_length=8)
    key_hash = models.CharField(max_length=255)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self) -> str:
        return f"{self.name} ({self.key_prefix}...)"

    @classmethod
    def generate_key(cls, prefix: str = "sk_live_") -> tuple[str, str, str]:
        """Generate a new API key.

        Returns:
            Tuple of (full_key, key_prefix, key_hash).
        """
        key = prefix + secrets.token_hex(24)
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return key, prefix, key_hash

    @classmethod
    def verify_key(cls, full_key: str, key_hash: str) -> bool:
        """Verify a full key against a stored hash."""
        return hashlib.sha256(full_key.encode()).hexdigest() == key_hash

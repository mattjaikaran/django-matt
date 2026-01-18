"""
Django models for storing WebAuthn/Passkey credentials.
"""

from django.conf import settings
from django.db import models


class PasskeyCredential(models.Model):
    """
    Stores a WebAuthn credential (passkey) for a user.

    Each user can have multiple credentials (e.g., Touch ID on laptop,
    Face ID on phone, hardware security key, etc.)
    """

    # The user this credential belongs to
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passkey_credentials",
    )

    # Credential identifier (base64url encoded)
    credential_id = models.CharField(
        max_length=512,
        unique=True,
        db_index=True,
        help_text="Unique identifier for this credential (base64url encoded)",
    )

    # Public key (COSE format, base64 encoded)
    public_key = models.TextField(
        help_text="Public key in COSE format (base64 encoded)",
    )

    # Signature counter for replay attack prevention
    sign_count = models.BigIntegerField(
        default=0,
        help_text="Signature counter to prevent replay attacks",
    )

    # Credential device type
    device_type = models.CharField(
        max_length=32,
        choices=[
            ("single_device", "Single Device (device-bound)"),
            ("multi_device", "Multi-Device (synced)"),
        ],
        default="single_device",
        help_text="Whether this credential is device-bound or synced",
    )

    # Whether the credential is backed up (for synced credentials)
    backed_up = models.BooleanField(
        default=False,
        help_text="Whether this credential is backed up (synced credentials)",
    )

    # Transports this credential supports
    transports = models.JSONField(
        default=list,
        blank=True,
        help_text="Transports this credential supports (e.g., usb, nfc, ble, internal)",
    )

    # AAGUID of the authenticator (for identifying authenticator type)
    aaguid = models.CharField(
        max_length=36,
        blank=True,
        default="",
        help_text="Authenticator Attestation GUID",
    )

    # Human-readable name for this credential
    name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="User-provided name for this credential (e.g., 'MacBook Pro', 'YubiKey')",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "django_matt"
        db_table = "django_matt_passkey_credentials"
        verbose_name = "Passkey Credential"
        verbose_name_plural = "Passkey Credentials"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["credential_id"]),
        ]

    def __str__(self):
        name = self.name or f"Credential {self.credential_id[:8]}..."
        return f"{self.user} - {name}"

    def update_sign_count(self, new_count: int) -> bool:
        """
        Update the signature counter.

        Returns:
            True if the counter was valid and updated, False if replay detected
        """
        if new_count > self.sign_count:
            self.sign_count = new_count
            self.save(update_fields=["sign_count", "last_used_at"])
            return True
        elif new_count == 0 and self.sign_count == 0:
            # Some authenticators don't implement counters
            return True
        else:
            # Possible cloned authenticator / replay attack
            return False


class PasskeyChallenge(models.Model):
    """
    Temporary storage for WebAuthn challenges.

    Challenges are short-lived and should be cleaned up regularly.
    For production, consider using cache instead of database.
    """

    # Challenge identifier
    challenge_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
    )

    # The challenge bytes (base64 encoded)
    challenge = models.CharField(max_length=128)

    # Type of challenge
    challenge_type = models.CharField(
        max_length=20,
        choices=[
            ("registration", "Registration"),
            ("authentication", "Authentication"),
        ],
    )

    # Associated user (optional for authentication)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="passkey_challenges",
    )

    # When this challenge expires
    expires_at = models.DateTimeField()

    # Created timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_matt"
        db_table = "django_matt_passkey_challenges"
        verbose_name = "Passkey Challenge"
        verbose_name_plural = "Passkey Challenges"
        indexes = [
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.challenge_type} challenge for {self.user or 'anonymous'}"

    @property
    def is_expired(self) -> bool:
        """Check if this challenge has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at

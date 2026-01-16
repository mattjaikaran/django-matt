"""
Configuration for Passkeys/WebAuthn authentication.
"""

from dataclasses import dataclass, field
from typing import Literal

from django.conf import settings


@dataclass
class PasskeyConfig:
    """
    Configuration for WebAuthn/Passkey authentication.

    Attributes:
        rp_id: Relying Party ID (your domain, e.g., "example.com")
        rp_name: Human-readable name of your application
        origin: The origin URL (e.g., "https://example.com")
        challenge_timeout: How long challenges are valid (milliseconds)
        user_verification: Whether to require user verification
        resident_key: Whether to require resident keys (for usernameless auth)
        attestation: Attestation conveyance preference
        authenticator_attachment: Preferred authenticator type
        supported_algorithms: List of supported COSE algorithm identifiers
    """

    rp_id: str = ""
    rp_name: str = ""
    origin: str = ""
    challenge_timeout: int = 60000  # 60 seconds
    user_verification: Literal["required", "preferred", "discouraged"] = "preferred"
    resident_key: Literal["required", "preferred", "discouraged"] = "preferred"
    attestation: Literal["none", "indirect", "direct", "enterprise"] = "none"
    authenticator_attachment: Literal["platform", "cross-platform"] | None = None
    supported_algorithms: list[int] = field(default_factory=lambda: [-7, -257])  # ES256, RS256

    # Storage settings
    credential_model: str = "django_matt.auth.passkeys.PasskeyCredential"
    challenge_cache_prefix: str = "passkey_challenge"
    challenge_cache_timeout: int = 300  # 5 minutes

    # Security settings
    allow_multiple_credentials: bool = True
    max_credentials_per_user: int = 10

    @classmethod
    def from_settings(cls) -> "PasskeyConfig":
        """
        Create a PasskeyConfig from Django settings.

        Settings should be in DJANGO_MATT_PASSKEY dict:

        DJANGO_MATT_PASSKEY = {
            "RP_ID": "example.com",
            "RP_NAME": "My Application",
            "ORIGIN": "https://example.com",
            ...
        }
        """
        config_dict = getattr(settings, "DJANGO_MATT_PASSKEY", {})

        return cls(
            rp_id=config_dict.get("RP_ID", cls.rp_id),
            rp_name=config_dict.get("RP_NAME", cls.rp_name),
            origin=config_dict.get("ORIGIN", cls.origin),
            challenge_timeout=config_dict.get("CHALLENGE_TIMEOUT", cls.challenge_timeout),
            user_verification=config_dict.get("USER_VERIFICATION", cls.user_verification),
            resident_key=config_dict.get("RESIDENT_KEY", cls.resident_key),
            attestation=config_dict.get("ATTESTATION", cls.attestation),
            authenticator_attachment=config_dict.get("AUTHENTICATOR_ATTACHMENT", cls.authenticator_attachment),
            supported_algorithms=config_dict.get("SUPPORTED_ALGORITHMS", cls.supported_algorithms),
            credential_model=config_dict.get("CREDENTIAL_MODEL", cls.credential_model),
            challenge_cache_prefix=config_dict.get("CHALLENGE_CACHE_PREFIX", cls.challenge_cache_prefix),
            challenge_cache_timeout=config_dict.get("CHALLENGE_CACHE_TIMEOUT", cls.challenge_cache_timeout),
            allow_multiple_credentials=config_dict.get("ALLOW_MULTIPLE_CREDENTIALS", cls.allow_multiple_credentials),
            max_credentials_per_user=config_dict.get("MAX_CREDENTIALS_PER_USER", cls.max_credentials_per_user),
        )

    def validate(self) -> list[str]:
        """
        Validate the configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.rp_id:
            errors.append("RP_ID is required. Set it in DJANGO_MATT_PASSKEY settings.")

        if not self.rp_name:
            errors.append("RP_NAME is required. Set it in DJANGO_MATT_PASSKEY settings.")

        if not self.origin:
            errors.append("ORIGIN is required. Set it in DJANGO_MATT_PASSKEY settings.")

        if self.origin and not self.origin.startswith(("http://", "https://")):
            errors.append("ORIGIN must be a valid URL starting with http:// or https://")

        if self.user_verification not in ("required", "preferred", "discouraged"):
            errors.append("USER_VERIFICATION must be 'required', 'preferred', or 'discouraged'")

        if self.resident_key not in ("required", "preferred", "discouraged"):
            errors.append("RESIDENT_KEY must be 'required', 'preferred', or 'discouraged'")

        return errors


# Global config instance (lazy-loaded from settings)
_passkey_config: PasskeyConfig | None = None


def get_passkey_config() -> PasskeyConfig:
    """Get the global passkey configuration."""
    global _passkey_config
    if _passkey_config is None:
        _passkey_config = PasskeyConfig.from_settings()
    return _passkey_config


def passkey_config() -> PasskeyConfig:
    """Alias for get_passkey_config()."""
    return get_passkey_config()

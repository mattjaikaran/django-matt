"""
Configuration for Enterprise SSO authentication.
"""

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings


@dataclass
class SSOProviderSettings:
    """
    Settings for a specific SSO provider type.

    These are global defaults that can be overridden per-organization.
    """

    enabled: bool = True
    # Default settings for this provider type
    defaults: dict[str, Any] = field(default_factory=dict)


@dataclass
class SSOConfig:
    """
    Global SSO configuration.

    Attributes:
        enabled: Whether SSO is enabled globally
        callback_url_base: Base URL for SSO callbacks
        allowed_providers: List of allowed SSO provider types
        require_email_verification: Whether to require verified email from IdP
        auto_create_user: Whether to create new users on first SSO login
        auto_update_user: Whether to update user info from IdP on each login
        default_role: Default role for new SSO users
        session_timeout: SSO session timeout in seconds
    """

    enabled: bool = True
    callback_url_base: str = ""
    allowed_providers: list[str] = field(
        default_factory=lambda: ["saml", "oidc", "okta", "azure_ad", "google_workspace"]
    )
    require_email_verification: bool = True
    auto_create_user: bool = True
    auto_update_user: bool = True
    default_role: str = "member"
    session_timeout: int = 86400  # 24 hours

    # Provider-specific settings
    saml: SSOProviderSettings = field(default_factory=SSOProviderSettings)
    oidc: SSOProviderSettings = field(default_factory=SSOProviderSettings)

    # State/nonce storage
    state_cache_prefix: str = "sso_state"
    state_timeout: int = 600  # 10 minutes

    @classmethod
    def from_settings(cls) -> "SSOConfig":
        """
        Create SSOConfig from Django settings.

        Settings should be in DJANGO_MATT_SSO dict:

        DJANGO_MATT_SSO = {
            "ENABLED": True,
            "CALLBACK_URL_BASE": "https://example.com",
            "ALLOWED_PROVIDERS": ["saml", "oidc", "okta", "azure_ad"],
            "AUTO_CREATE_USER": True,
            "DEFAULT_ROLE": "member",
            "SAML": {
                "enabled": True,
                "defaults": {
                    "want_assertions_signed": True,
                },
            },
        }
        """
        config_dict = getattr(settings, "DJANGO_MATT_SSO", {})

        # Build a default instance to safely read default values from field(default_factory=...)
        _defaults = cls()

        config = cls(
            enabled=config_dict.get("ENABLED", _defaults.enabled),
            callback_url_base=config_dict.get("CALLBACK_URL_BASE", ""),
            allowed_providers=config_dict.get("ALLOWED_PROVIDERS", _defaults.allowed_providers),
            require_email_verification=config_dict.get(
                "REQUIRE_EMAIL_VERIFICATION", _defaults.require_email_verification
            ),
            auto_create_user=config_dict.get("AUTO_CREATE_USER", _defaults.auto_create_user),
            auto_update_user=config_dict.get("AUTO_UPDATE_USER", _defaults.auto_update_user),
            default_role=config_dict.get("DEFAULT_ROLE", _defaults.default_role),
            session_timeout=config_dict.get("SESSION_TIMEOUT", _defaults.session_timeout),
            state_cache_prefix=config_dict.get("STATE_CACHE_PREFIX", _defaults.state_cache_prefix),
            state_timeout=config_dict.get("STATE_TIMEOUT", _defaults.state_timeout),
        )

        # Load provider settings
        if "SAML" in config_dict:
            config.saml = SSOProviderSettings(
                enabled=config_dict["SAML"].get("enabled", True),
                defaults=config_dict["SAML"].get("defaults", {}),
            )

        if "OIDC" in config_dict:
            config.oidc = SSOProviderSettings(
                enabled=config_dict["OIDC"].get("enabled", True),
                defaults=config_dict["OIDC"].get("defaults", {}),
            )

        return config

    def is_provider_allowed(self, provider_type: str) -> bool:
        """Check if a provider type is allowed."""
        return provider_type.lower() in [p.lower() for p in self.allowed_providers]

    def validate(self) -> list[str]:
        """Validate the configuration."""
        errors = []

        if not self.callback_url_base:
            errors.append("CALLBACK_URL_BASE is required for SSO")

        if not self.allowed_providers:
            errors.append("At least one SSO provider type must be allowed")

        return errors


# Global config instance (lazy-loaded)
_sso_config: SSOConfig | None = None


def get_sso_config() -> SSOConfig:
    """Get the global SSO configuration."""
    global _sso_config
    if _sso_config is None:
        _sso_config = SSOConfig.from_settings()
    return _sso_config


def sso_config() -> SSOConfig:
    """Alias for get_sso_config()."""
    return get_sso_config()


def reset_sso_config():
    """Reset the config (useful for testing)."""
    global _sso_config
    _sso_config = None

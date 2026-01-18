"""
Configuration for OAuth authentication providers.
"""

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings


@dataclass
class OAuthProviderConfig:
    """
    Configuration for a single OAuth provider.

    Attributes:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        scopes: List of OAuth scopes to request
        enabled: Whether this provider is enabled
        extra: Provider-specific extra configuration
    """

    client_id: str = ""
    client_secret: str = ""
    scopes: list[str] = field(default_factory=list)
    enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class OAuthConfig:
    """
    Global OAuth configuration.

    Attributes:
        redirect_uri_base: Base URL for OAuth callbacks (e.g., "https://example.com")
        success_redirect: Where to redirect after successful login
        failure_redirect: Where to redirect after failed login
        auto_create_user: Whether to create new users on first OAuth login
        link_existing_user: Whether to link OAuth to existing user with same email
        providers: Dictionary of provider configurations
    """

    redirect_uri_base: str = ""
    success_redirect: str = "/"
    failure_redirect: str = "/login?error=oauth_failed"
    auto_create_user: bool = True
    link_existing_user: bool = True
    session_state_key: str = "oauth_state"
    state_timeout: int = 600  # 10 minutes

    # Provider configurations
    google: OAuthProviderConfig = field(
        default_factory=lambda: OAuthProviderConfig(scopes=["openid", "email", "profile"])
    )
    github: OAuthProviderConfig = field(
        default_factory=lambda: OAuthProviderConfig(scopes=["user:email", "read:user"])
    )
    apple: OAuthProviderConfig = field(
        default_factory=lambda: OAuthProviderConfig(scopes=["name", "email"])
    )
    microsoft: OAuthProviderConfig = field(
        default_factory=lambda: OAuthProviderConfig(
            scopes=["openid", "email", "profile", "User.Read"]
        )
    )

    @classmethod
    def from_settings(cls) -> "OAuthConfig":
        """
        Create OAuthConfig from Django settings.

        Settings should be in DJANGO_MATT_OAUTH dict:

        DJANGO_MATT_OAUTH = {
            "REDIRECT_URI_BASE": "https://example.com",
            "SUCCESS_REDIRECT": "/dashboard",
            "FAILURE_REDIRECT": "/login?error=oauth",
            "AUTO_CREATE_USER": True,
            "LINK_EXISTING_USER": True,
            "GOOGLE": {
                "client_id": "...",
                "client_secret": "...",
                "scopes": ["openid", "email", "profile"],
            },
            "GITHUB": {
                "client_id": "...",
                "client_secret": "...",
            },
            "APPLE": {
                "client_id": "...",
                "team_id": "...",
                "key_id": "...",
                "private_key": "...",
            },
        }
        """
        config_dict = getattr(settings, "DJANGO_MATT_OAUTH", {})

        config = cls(
            redirect_uri_base=config_dict.get("REDIRECT_URI_BASE", ""),
            success_redirect=config_dict.get("SUCCESS_REDIRECT", cls.success_redirect),
            failure_redirect=config_dict.get("FAILURE_REDIRECT", cls.failure_redirect),
            auto_create_user=config_dict.get("AUTO_CREATE_USER", cls.auto_create_user),
            link_existing_user=config_dict.get("LINK_EXISTING_USER", cls.link_existing_user),
            session_state_key=config_dict.get("SESSION_STATE_KEY", cls.session_state_key),
            state_timeout=config_dict.get("STATE_TIMEOUT", cls.state_timeout),
        )

        # Load provider configs
        if "GOOGLE" in config_dict:
            config.google = cls._load_provider_config(config_dict["GOOGLE"], config.google)

        if "GITHUB" in config_dict:
            config.github = cls._load_provider_config(config_dict["GITHUB"], config.github)

        if "APPLE" in config_dict:
            apple_config = config_dict["APPLE"]
            config.apple = cls._load_provider_config(apple_config, config.apple)
            # Apple-specific extras
            config.apple.extra = {
                "team_id": apple_config.get("team_id", ""),
                "key_id": apple_config.get("key_id", ""),
                "private_key": apple_config.get("private_key", ""),
            }

        if "MICROSOFT" in config_dict:
            config.microsoft = cls._load_provider_config(config_dict["MICROSOFT"], config.microsoft)

        return config

    @staticmethod
    def _load_provider_config(
        config_dict: dict[str, Any], default: OAuthProviderConfig
    ) -> OAuthProviderConfig:
        """Load a provider config from a dictionary."""
        return OAuthProviderConfig(
            client_id=config_dict.get("client_id", default.client_id),
            client_secret=config_dict.get("client_secret", default.client_secret),
            scopes=config_dict.get("scopes", default.scopes),
            enabled=config_dict.get("enabled", default.enabled),
            extra=config_dict.get("extra", default.extra),
        )

    def get_provider_config(self, provider: str) -> OAuthProviderConfig | None:
        """Get configuration for a specific provider."""
        provider = provider.lower()
        if hasattr(self, provider):
            config = getattr(self, provider)
            if isinstance(config, OAuthProviderConfig) and config.enabled and config.client_id:
                return config
        return None

    def get_enabled_providers(self) -> list[str]:
        """Get list of enabled provider names."""
        providers = []
        for name in ["google", "github", "apple", "microsoft"]:
            config = getattr(self, name)
            if config.enabled and config.client_id:
                providers.append(name)
        return providers

    def validate(self) -> list[str]:
        """Validate the configuration."""
        errors = []

        if not self.redirect_uri_base:
            errors.append("REDIRECT_URI_BASE is required for OAuth")

        enabled = self.get_enabled_providers()
        if not enabled:
            errors.append("At least one OAuth provider must be configured")

        return errors


# Global config instance (lazy-loaded)
_oauth_config: OAuthConfig | None = None


def get_oauth_config() -> OAuthConfig:
    """Get the global OAuth configuration."""
    global _oauth_config
    if _oauth_config is None:
        _oauth_config = OAuthConfig.from_settings()
    return _oauth_config


def oauth_config() -> OAuthConfig:
    """Alias for get_oauth_config()."""
    return get_oauth_config()


def reset_oauth_config():
    """Reset the config (useful for testing)."""
    global _oauth_config
    _oauth_config = None

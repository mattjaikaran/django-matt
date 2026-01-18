"""
OAuth providers for social authentication.
"""

from django_matt.auth.oauth.providers.apple import AppleOAuthProvider
from django_matt.auth.oauth.providers.base import (
    OAuthAuthenticationError,
    OAuthConfigError,
    OAuthError,
    OAuthProvider,
    OAuthToken,
    OAuthUserInfo,
    OAuthUserInfoError,
)
from django_matt.auth.oauth.providers.github import GitHubOAuthProvider
from django_matt.auth.oauth.providers.google import GoogleOAuthProvider
from django_matt.auth.oauth.providers.microsoft import MicrosoftOAuthProvider

__all__ = [
    # Base
    "OAuthProvider",
    "OAuthUserInfo",
    "OAuthToken",
    "OAuthError",
    "OAuthConfigError",
    "OAuthAuthenticationError",
    "OAuthUserInfoError",
    # Providers
    "GoogleOAuthProvider",
    "GitHubOAuthProvider",
    "AppleOAuthProvider",
    "MicrosoftOAuthProvider",
]


# Provider registry
PROVIDERS: dict[str, type[OAuthProvider]] = {
    "google": GoogleOAuthProvider,
    "github": GitHubOAuthProvider,
    "apple": AppleOAuthProvider,
    "microsoft": MicrosoftOAuthProvider,
}


def get_provider(name: str) -> type[OAuthProvider] | None:
    """Get a provider class by name."""
    return PROVIDERS.get(name.lower())


def get_provider_instance(name: str) -> OAuthProvider | None:
    """Get an instantiated provider by name."""
    provider_class = get_provider(name)
    if provider_class:
        return provider_class()
    return None

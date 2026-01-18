"""
Enterprise SSO providers.
"""

from django_matt.auth.sso.providers.base import (
    SSOAuthenticationError,
    SSOConfigError,
    SSOError,
    SSOProvider,
    SSOUserInfo,
)
from django_matt.auth.sso.providers.oidc import OIDCProvider
from django_matt.auth.sso.providers.saml import SAMLProvider

__all__ = [
    # Base
    "SSOProvider",
    "SSOUserInfo",
    "SSOError",
    "SSOConfigError",
    "SSOAuthenticationError",
    # Providers
    "SAMLProvider",
    "OIDCProvider",
]


# Provider registry
PROVIDERS: dict[str, type[SSOProvider]] = {
    "saml": SAMLProvider,
    "oidc": OIDCProvider,
    "okta": OIDCProvider,  # Okta uses OIDC
    "azure_ad": OIDCProvider,  # Azure AD uses OIDC
    "google_workspace": OIDCProvider,  # Google Workspace uses OIDC
    "onelogin": SAMLProvider,  # OneLogin commonly uses SAML
    "auth0": OIDCProvider,  # Auth0 uses OIDC
}


def get_provider_class(provider_type: str) -> type[SSOProvider] | None:
    """Get a provider class by type."""
    return PROVIDERS.get(provider_type.lower())


def get_provider_for_connection(connection) -> SSOProvider | None:
    """Get an instantiated provider for an SSO connection."""
    provider_class = get_provider_class(connection.provider_type)
    if provider_class:
        return provider_class(connection)
    return None

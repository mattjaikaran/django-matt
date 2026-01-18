"""
Django Matt Enterprise SSO - SAML and OIDC authentication for B2B.

Provides:
- SAML 2.0 authentication (Okta, Azure AD, OneLogin, etc.)
- OpenID Connect authentication (Okta, Azure AD, Google Workspace, Auth0)
- Per-organization SSO configuration
- Automatic user provisioning
- Attribute mapping from IdP

Requires:
- SAML: pip install python3-saml
- OIDC: pip install httpx

Example:
    from django_matt.auth.sso import SSOController

    # Add to your API
    api.register_controller(SSOController, prefix="/auth")

Configuration:
    # settings.py
    DJANGO_MATT_SSO = {
        "ENABLED": True,
        "CALLBACK_URL_BASE": "https://example.com",
        "ALLOWED_PROVIDERS": ["saml", "oidc", "okta", "azure_ad"],
        "AUTO_CREATE_USER": True,
    }

    # Then configure per-organization via API or admin
"""

from django_matt.auth.sso.config import (
    SSOConfig,
    SSOProviderSettings,
    get_sso_config,
    sso_config,
)
from django_matt.auth.sso.controllers import (
    SSOController,
)
from django_matt.auth.sso.providers import (
    OIDCProvider,
    SAMLProvider,
    SSOAuthenticationError,
    SSOConfigError,
    SSOError,
    SSOProvider,
    SSOUserInfo,
    get_provider_class,
    get_provider_for_connection,
)
from django_matt.auth.sso.schemas import (
    SPMetadataResponse,
    SSOCallbackResponse,
    SSOConnectionBase,
    SSOConnectionCreateRequest,
    SSOConnectionOIDCConfig,
    SSOConnectionResponse,
    SSOConnectionSAMLConfig,
    SSOConnectionUpdateRequest,
    SSODomainCheckRequest,
    SSOErrorResponse,
    SSOLoginRequest,
    SSOLoginResponse,
    SSOStatusResponse,
)

__all__ = [
    # Config
    "SSOConfig",
    "SSOProviderSettings",
    "get_sso_config",
    "sso_config",
    # Providers
    "SSOProvider",
    "SSOUserInfo",
    "SSOError",
    "SSOConfigError",
    "SSOAuthenticationError",
    "SAMLProvider",
    "OIDCProvider",
    "get_provider_class",
    "get_provider_for_connection",
    # Schemas
    "SSOConnectionBase",
    "SSOConnectionSAMLConfig",
    "SSOConnectionOIDCConfig",
    "SSOConnectionCreateRequest",
    "SSOConnectionUpdateRequest",
    "SSOConnectionResponse",
    "SSOLoginRequest",
    "SSOLoginResponse",
    "SSOCallbackResponse",
    "SPMetadataResponse",
    "SSOStatusResponse",
    "SSODomainCheckRequest",
    "SSOErrorResponse",
    # Controllers
    "SSOController",
]

"""
Django Matt OAuth - Social authentication with OAuth providers.

Provides:
- Google, GitHub, Apple, Microsoft OAuth login
- OAuth connection management
- Automatic user creation/linking
- JWT tokens after OAuth authentication

Requires: pip install httpx

Example:
    from django_matt.auth.oauth import OAuthController

    # Add to your API
    api.register_controller(OAuthController, prefix="/auth")

Configuration:
    # settings.py
    DJANGO_MATT_OAUTH = {
        "REDIRECT_URI_BASE": "https://example.com",
        "GOOGLE": {
            "client_id": "...",
            "client_secret": "...",
        },
        "GITHUB": {
            "client_id": "...",
            "client_secret": "...",
        },
    }
"""

from django_matt.auth.oauth.config import (
    OAuthConfig,
    OAuthProviderConfig,
    get_oauth_config,
    oauth_config,
)
from django_matt.auth.oauth.controllers import (
    OAuthController,
)
from django_matt.auth.oauth.providers import (
    AppleOAuthProvider,
    GitHubOAuthProvider,
    GoogleOAuthProvider,
    MicrosoftOAuthProvider,
    OAuthAuthenticationError,
    OAuthConfigError,
    OAuthError,
    OAuthProvider,
    OAuthToken,
    OAuthUserInfo,
    OAuthUserInfoError,
    get_provider,
    get_provider_instance,
)
from django_matt.auth.oauth.schemas import (
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    OAuthConnectionListResponse,
    OAuthConnectionResponse,
    OAuthDisconnectRequest,
    OAuthErrorResponse,
    OAuthLoginRequest,
    OAuthLoginResponse,
    OAuthProviderInfo,
    OAuthProvidersResponse,
)

__all__ = [
    # Config
    "OAuthConfig",
    "OAuthProviderConfig",
    "get_oauth_config",
    "oauth_config",
    # Base provider
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
    "get_provider",
    "get_provider_instance",
    # Schemas
    "OAuthProviderInfo",
    "OAuthProvidersResponse",
    "OAuthLoginRequest",
    "OAuthLoginResponse",
    "OAuthCallbackRequest",
    "OAuthCallbackResponse",
    "OAuthConnectionResponse",
    "OAuthConnectionListResponse",
    "OAuthDisconnectRequest",
    "OAuthErrorResponse",
    # Controllers
    "OAuthController",
]

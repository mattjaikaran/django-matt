"""
Base OAuth provider class and common utilities.
"""

import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from django.core.cache import cache

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class OAuthToken:
    """OAuth token response."""

    access_token: str
    token_type: str = "Bearer"
    refresh_token: str | None = None
    expires_in: int | None = None
    scope: str | None = None
    id_token: str | None = None  # For OIDC providers
    raw: dict[str, Any] | None = None


@dataclass
class OAuthUserInfo:
    """Normalized user info from OAuth provider."""

    provider: str
    provider_user_id: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    locale: str | None = None
    raw: dict[str, Any] | None = None


# =============================================================================
# Exceptions
# =============================================================================


class OAuthError(Exception):
    """Base OAuth error."""

    def __init__(self, message: str, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class OAuthConfigError(OAuthError):
    """OAuth configuration error."""


class OAuthAuthenticationError(OAuthError):
    """OAuth authentication failed."""


class OAuthUserInfoError(OAuthError):
    """Failed to get user info from provider."""


# =============================================================================
# Base Provider
# =============================================================================


class OAuthProvider(ABC):
    """
    Base class for OAuth providers.

    Subclasses must implement:
    - name: Provider name (e.g., "google")
    - authorization_url: URL to start OAuth flow
    - token_url: URL to exchange code for token
    - userinfo_url: URL to get user info (optional for OIDC)
    - get_user_info(): Parse user info from provider response
    """

    name: str = ""
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""

    # OIDC providers can get user info from id_token
    supports_oidc: bool = False

    def __init__(self):
        from django_matt.auth.oauth.config import get_oauth_config

        self.config = get_oauth_config()
        self.provider_config = self.config.get_provider_config(self.name)

    def _ensure_configured(self):
        """Ensure provider is properly configured."""
        if not self.provider_config:
            raise OAuthConfigError(f"OAuth provider '{self.name}' is not configured")

        if not self.provider_config.client_id:
            raise OAuthConfigError(f"client_id not set for OAuth provider '{self.name}'")

        if not self.provider_config.client_secret:
            raise OAuthConfigError(f"client_secret not set for OAuth provider '{self.name}'")

    def get_redirect_uri(self) -> str:
        """Get the OAuth callback URL for this provider."""
        base = self.config.redirect_uri_base.rstrip("/")
        return f"{base}/auth/oauth/{self.name}/callback"

    def generate_state(self, extra_data: dict | None = None) -> str:
        """
        Generate a secure state parameter and store it.

        Args:
            extra_data: Optional extra data to store with the state

        Returns:
            The state token
        """
        state = secrets.token_urlsafe(32)
        cache_key = f"oauth_state:{state}"

        data = {"provider": self.name}
        if extra_data:
            data.update(extra_data)

        cache.set(cache_key, data, self.config.state_timeout)
        return state

    def verify_state(self, state: str) -> dict | None:
        """
        Verify a state parameter and return stored data.

        Args:
            state: The state token to verify

        Returns:
            The stored data, or None if invalid/expired
        """
        cache_key = f"oauth_state:{state}"
        data = cache.get(cache_key)

        if data:
            # Delete after use (one-time use)
            cache.delete(cache_key)

        return data

    def get_authorization_url(
        self,
        state: str | None = None,
        extra_params: dict | None = None,
    ) -> tuple[str, str]:
        """
        Get the authorization URL to redirect the user to.

        Args:
            state: Optional state parameter (generated if not provided)
            extra_params: Optional extra query parameters

        Returns:
            Tuple of (authorization_url, state)
        """
        self._ensure_configured()

        if state is None:
            state = self.generate_state()

        params = {
            "client_id": self.provider_config.client_id,
            "redirect_uri": self.get_redirect_uri(),
            "response_type": "code",
            "state": state,
        }

        if self.provider_config.scopes:
            params["scope"] = " ".join(self.provider_config.scopes)

        if extra_params:
            params.update(extra_params)

        # Allow subclasses to modify params
        params = self._customize_auth_params(params)

        url = f"{self.authorization_url}?{urlencode(params)}"
        return url, state

    def _customize_auth_params(self, params: dict) -> dict:
        """
        Hook for subclasses to customize authorization parameters.

        Override in subclasses to add provider-specific parameters.
        """
        return params

    async def exchange_code(self, code: str) -> OAuthToken:
        """
        Exchange authorization code for access token.

        Args:
            code: The authorization code from the callback

        Returns:
            OAuthToken with access token and optional refresh token
        """
        self._ensure_configured()

        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for OAuth. Install with: uv add httpx "
                "or install the oauth extra: uv add django-matt[oauth]"
            )

        data = {
            "client_id": self.provider_config.client_id,
            "client_secret": self.provider_config.client_secret,
            "code": code,
            "redirect_uri": self.get_redirect_uri(),
            "grant_type": "authorization_code",
        }

        # Allow subclasses to modify token request
        data = self._customize_token_request(data)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                error_data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                raise OAuthAuthenticationError(
                    f"Failed to exchange code: {error_data.get('error_description', response.text)}",
                    error_code=error_data.get("error"),
                )

            token_data = response.json()

        return OAuthToken(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
            scope=token_data.get("scope"),
            id_token=token_data.get("id_token"),
            raw=token_data,
        )

    def _customize_token_request(self, data: dict) -> dict:
        """
        Hook for subclasses to customize token request.

        Override in subclasses to add provider-specific parameters.
        """
        return data

    async def fetch_user_info(self, token: OAuthToken) -> OAuthUserInfo:
        """
        Fetch user info from the provider.

        Args:
            token: The OAuth token

        Returns:
            Normalized OAuthUserInfo
        """
        self._ensure_configured()

        # For OIDC providers, try to get info from id_token first
        if self.supports_oidc and token.id_token:
            try:
                return self._parse_id_token(token.id_token)
            except Exception:
                pass  # Fall back to userinfo endpoint

        if not self.userinfo_url:
            raise OAuthUserInfoError(f"No userinfo URL configured for {self.name}")

        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for OAuth. Install with: uv add httpx "
                "or install the oauth extra: uv add django-matt[oauth]"
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={
                    "Authorization": f"{token.token_type} {token.access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                raise OAuthUserInfoError(f"Failed to fetch user info: {response.text}")

            user_data = response.json()

        return self.get_user_info(user_data)

    def _parse_id_token(self, id_token: str) -> OAuthUserInfo:
        """
        Parse user info from OIDC id_token.

        Override in subclasses if needed.
        """
        import base64
        import json

        # Decode JWT payload (without verification - token was just received)
        parts = id_token.split(".")
        if len(parts) != 3:
            raise OAuthUserInfoError("Invalid id_token format")

        # Add padding if needed
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        try:
            data = json.loads(base64.urlsafe_b64decode(payload))
        except Exception as e:
            raise OAuthUserInfoError(f"Failed to decode id_token: {e}")

        return self.get_user_info(data)

    @abstractmethod
    def get_user_info(self, data: dict) -> OAuthUserInfo:
        """
        Parse provider-specific user data into normalized OAuthUserInfo.

        Args:
            data: Raw user data from provider

        Returns:
            Normalized OAuthUserInfo
        """


def sync_exchange_code(provider: OAuthProvider, code: str) -> OAuthToken:
    """Sync wrapper for exchange_code."""
    import asyncio

    return asyncio.run(provider.exchange_code(code))


def sync_fetch_user_info(provider: OAuthProvider, token: OAuthToken) -> OAuthUserInfo:
    """Sync wrapper for fetch_user_info."""
    import asyncio

    return asyncio.run(provider.fetch_user_info(token))

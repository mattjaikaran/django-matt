"""
OpenID Connect (OIDC) SSO provider.

Supports OIDC-based identity providers like:
- Okta
- Azure AD / Microsoft Entra ID
- Google Workspace
- Auth0
- Any OIDC compliant IdP

Requires: pip install httpx PyJWT
"""

import hashlib
import secrets
from urllib.parse import urlencode

from django.core.cache import cache

from django_matt.auth.sso.providers.base import (
    SSOProvider,
    SSOUserInfo,
    SSOConfigError,
    SSOAuthenticationError,
)


class OIDCProvider(SSOProvider):
    """
    OpenID Connect SSO provider.

    Uses OIDC discovery to automatically configure endpoints,
    or manual configuration if discovery URL is not provided.
    """

    provider_type = "oidc"

    def __init__(self, connection):
        super().__init__(connection)
        self._discovered_config: dict | None = None

    async def _discover_config(self) -> dict:
        """
        Fetch OIDC configuration from discovery endpoint.

        Returns:
            OIDC configuration dict
        """
        if self._discovered_config:
            return self._discovered_config

        # Check cache first
        cache_key = f"oidc_discovery:{self.connection.id}"
        cached = cache.get(cache_key)
        if cached:
            self._discovered_config = cached
            return cached

        discovery_url = self.connection.discovery_url
        if not discovery_url:
            raise SSOConfigError("OIDC discovery URL or manual endpoints required")

        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(discovery_url)
            if response.status_code != 200:
                raise SSOConfigError(f"Failed to fetch OIDC discovery: {response.text}")

            config = response.json()

        # Cache for 1 hour
        cache.set(cache_key, config, 3600)
        self._discovered_config = config
        return config

    def _get_discovery_config_sync(self) -> dict:
        """Synchronous version of discovery (for login URL generation)."""
        if self._discovered_config:
            return self._discovered_config

        cache_key = f"oidc_discovery:{self.connection.id}"
        cached = cache.get(cache_key)
        if cached:
            self._discovered_config = cached
            return cached

        discovery_url = self.connection.discovery_url
        if not discovery_url:
            # Return manual config
            return {
                "authorization_endpoint": self.connection.authorization_url,
                "token_endpoint": self.connection.token_url,
                "userinfo_endpoint": self.connection.userinfo_url,
            }

        import httpx

        with httpx.Client() as client:
            response = client.get(discovery_url)
            if response.status_code != 200:
                raise SSOConfigError(f"Failed to fetch OIDC discovery: {response.text}")

            config = response.json()

        cache.set(cache_key, config, 3600)
        self._discovered_config = config
        return config

    def _get_authorization_url(self) -> str:
        """Get the authorization endpoint URL."""
        if self.connection.authorization_url:
            return self.connection.authorization_url

        config = self._get_discovery_config_sync()
        return config.get("authorization_endpoint", "")

    async def _get_token_url(self) -> str:
        """Get the token endpoint URL."""
        if self.connection.token_url:
            return self.connection.token_url

        config = await self._discover_config()
        return config.get("token_endpoint", "")

    async def _get_userinfo_url(self) -> str:
        """Get the userinfo endpoint URL."""
        if self.connection.userinfo_url:
            return self.connection.userinfo_url

        config = await self._discover_config()
        return config.get("userinfo_endpoint", "")

    def _generate_code_verifier(self) -> tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = (
            code_challenge.hex()
            .replace("+", "-")
            .replace("/", "_")
            .rstrip("=")
        )
        # Actually use base64url encoding
        import base64
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")

        return code_verifier, code_challenge

    def get_login_url(self, relay_state: str | None = None) -> str:
        """
        Generate OIDC authorization URL.

        Args:
            relay_state: Optional state parameter

        Returns:
            URL to redirect user to IdP
        """
        self._validate_connection()

        if not self.connection.client_id:
            raise SSOConfigError("OIDC client_id is required")

        authorization_url = self._get_authorization_url()
        if not authorization_url:
            raise SSOConfigError("OIDC authorization URL not configured")

        # Generate state and nonce
        state = relay_state or self.generate_state()
        nonce = secrets.token_urlsafe(32)

        # Generate PKCE if supported
        code_verifier, code_challenge = self._generate_code_verifier()

        # Store code_verifier with state
        cache_key = f"{self.config.state_cache_prefix}:pkce:{state}"
        cache.set(cache_key, code_verifier, self.config.state_timeout)

        # Store nonce
        cache_key = f"{self.config.state_cache_prefix}:nonce:{state}"
        cache.set(cache_key, nonce, self.config.state_timeout)

        # Get scopes
        extra = self.connection.extra_config or {}
        scopes = extra.get("scopes", ["openid", "email", "profile"])
        if isinstance(scopes, list):
            scopes = " ".join(scopes)

        params = {
            "client_id": self.connection.client_id,
            "redirect_uri": self.get_callback_url(),
            "response_type": "code",
            "scope": scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        # Add any extra params from config
        extra_params = extra.get("authorization_params", {})
        params.update(extra_params)

        return f"{authorization_url}?{urlencode(params)}"

    async def process_callback(self, request) -> SSOUserInfo:
        """
        Process OIDC callback from IdP.

        Args:
            request: Django HTTP request with code and state

        Returns:
            Normalized SSOUserInfo

        Raises:
            SSOAuthenticationError: If authentication fails
        """
        self._validate_connection()

        # Get code and state from request
        code = request.GET.get("code")
        state = request.GET.get("state")
        error = request.GET.get("error")
        error_description = request.GET.get("error_description")

        if error:
            raise SSOAuthenticationError(
                error_description or f"OIDC error: {error}"
            )

        if not code:
            raise SSOAuthenticationError("No authorization code in callback")

        if not state:
            raise SSOAuthenticationError("No state parameter in callback")

        # Verify state
        state_data = self.verify_state(state)
        if not state_data:
            raise SSOAuthenticationError("Invalid or expired state")

        # Get PKCE code verifier
        pkce_key = f"{self.config.state_cache_prefix}:pkce:{state}"
        code_verifier = cache.get(pkce_key)
        cache.delete(pkce_key)

        # Get stored nonce
        nonce_key = f"{self.config.state_cache_prefix}:nonce:{state}"
        expected_nonce = cache.get(nonce_key)
        cache.delete(nonce_key)

        # Exchange code for tokens
        token_url = await self._get_token_url()
        if not token_url:
            raise SSOConfigError("OIDC token URL not configured")

        import httpx

        token_data = {
            "grant_type": "authorization_code",
            "client_id": self.connection.client_id,
            "client_secret": self.connection.client_secret,
            "code": code,
            "redirect_uri": self.get_callback_url(),
        }

        if code_verifier:
            token_data["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=token_data,
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                error_data = response.json() if "json" in response.headers.get("content-type", "") else {}
                raise SSOAuthenticationError(
                    f"Token exchange failed: {error_data.get('error_description', response.text)}"
                )

            tokens = response.json()

        # Get user info from id_token or userinfo endpoint
        id_token = tokens.get("id_token")
        access_token = tokens.get("access_token")

        user_data = {}

        # Parse id_token if available
        if id_token:
            try:
                user_data = self._decode_id_token(id_token)

                # Verify nonce
                if expected_nonce and user_data.get("nonce") != expected_nonce:
                    raise SSOAuthenticationError("Invalid nonce in id_token")

            except Exception as e:
                # Fall back to userinfo endpoint
                pass

        # Fetch from userinfo endpoint if needed
        if not user_data.get("sub"):
            userinfo_url = await self._get_userinfo_url()
            if userinfo_url and access_token:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        userinfo_url,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    if response.status_code == 200:
                        user_data.update(response.json())

        if not user_data.get("sub"):
            raise SSOAuthenticationError("Could not get user info from IdP")

        # Map to SSOUserInfo
        return self.map_attributes(user_data)

    def _decode_id_token(self, id_token: str) -> dict:
        """
        Decode an OIDC id_token (without full verification).

        In production, you should verify the signature using the IdP's JWKS.
        This simplified version just decodes the payload.

        Args:
            id_token: The JWT id_token

        Returns:
            Decoded token payload
        """
        import base64
        import json

        parts = id_token.split(".")
        if len(parts) != 3:
            raise SSOAuthenticationError("Invalid id_token format")

        # Decode payload
        payload = parts[1]
        # Add padding
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        try:
            return json.loads(base64.urlsafe_b64decode(payload))
        except Exception as e:
            raise SSOAuthenticationError(f"Failed to decode id_token: {e}")

    def get_logout_url(self, relay_state: str | None = None) -> str | None:
        """
        Generate OIDC logout URL.

        Args:
            relay_state: Optional post-logout redirect URL

        Returns:
            Logout URL, or None if not supported
        """
        config = self._get_discovery_config_sync()
        end_session_endpoint = config.get("end_session_endpoint")

        if not end_session_endpoint:
            return None

        params = {}
        if self.connection.client_id:
            params["client_id"] = self.connection.client_id
        if relay_state:
            params["post_logout_redirect_uri"] = relay_state

        if params:
            return f"{end_session_endpoint}?{urlencode(params)}"
        return end_session_endpoint

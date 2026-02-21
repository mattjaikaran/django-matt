"""
OpenID Connect (OIDC) SSO provider.

Supports OIDC-based identity providers like:
- Okta
- Azure AD / Microsoft Entra ID
- Google Workspace
- Auth0
- Any OIDC compliant IdP

Requires: uv add httpx
"""

import base64
import hashlib
import hmac
import logging
import secrets
from urllib.parse import urlencode

from django.core.cache import cache

import orjson

from django_matt.auth.sso.providers.base import (
    SSOAuthenticationError,
    SSOConfigError,
    SSOProvider,
    SSOUserInfo,
)

logger = logging.getLogger(__name__)


def _b64url_decode(data: str) -> bytes:
    """Decode base64url-encoded data with padding correction."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def _verify_rs256_signature(header_payload: bytes, signature: bytes, jwk: dict) -> bool:
    """
    Verify an RS256 (RSASSA-PKCS1-v1_5 with SHA-256) JWT signature.

    Attempts to use the ``cryptography`` library for robust verification.
    Falls back to a pure-Python raw RSA implementation when ``cryptography``
    is not installed (e.g. when the ``jwt-asymmetric`` extra is not present).

    Args:
        header_payload: The ``header.payload`` portion of the JWT (bytes).
        signature: The decoded signature bytes.
        jwk: The JWK dict containing ``n`` (modulus) and ``e`` (exponent).

    Returns:
        True if signature is valid.
    """
    n_bytes = _b64url_decode(jwk["n"])
    e_bytes = _b64url_decode(jwk["e"])

    n = int.from_bytes(n_bytes, "big")
    e = int.from_bytes(e_bytes, "big")

    try:
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
        from cryptography.hazmat.primitives.hashes import SHA256

        public_numbers = RSAPublicNumbers(e, n)
        public_key = public_numbers.public_key()

        try:
            public_key.verify(signature, header_payload, padding.PKCS1v15(), SHA256())
            return True
        except Exception:
            return False

    except ImportError:
        # Pure-Python fallback: raw RSA + PKCS1-v1.5 verification
        # 1. RSA public operation: m = sig^e mod n
        sig_int = int.from_bytes(signature, "big")
        m_int = pow(sig_int, e, n)

        # Determine key size in bytes
        key_size = (n.bit_length() + 7) // 8
        try:
            m_bytes = m_int.to_bytes(key_size, "big")
        except OverflowError:
            return False

        # 2. PKCS1-v1.5 DigestInfo for SHA-256
        # DER encoding: SEQUENCE { SEQUENCE { OID sha256, NULL }, OCTET STRING hash }
        sha256_digest_info_prefix = bytes([
            0x30, 0x31, 0x30, 0x0D, 0x06, 0x09, 0x60, 0x86,
            0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01, 0x05,
            0x00, 0x04, 0x20,
        ])

        digest = hashlib.sha256(header_payload).digest()
        expected_em = (
            b"\x00\x01"
            + b"\xff" * (key_size - len(sha256_digest_info_prefix) - len(digest) - 3)
            + b"\x00"
            + sha256_digest_info_prefix
            + digest
        )

        return hmac.compare_digest(m_bytes, expected_em)


def _verify_hs256_signature(header_payload: bytes, signature: bytes, secret: str) -> bool:
    """
    Verify an HS256 (HMAC-SHA256) JWT signature.

    Args:
        header_payload: The ``header.payload`` portion of the JWT (bytes).
        signature: The decoded signature bytes.
        secret: The shared secret (client_secret).

    Returns:
        True if signature is valid.
    """
    expected = hmac.new(secret.encode("utf-8"), header_payload, hashlib.sha256).digest()
    return hmac.compare_digest(expected, signature)


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

        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for OIDC SSO. Install with: uv add httpx "
                "or install the oauth extra: uv add django-matt[oauth]"
            )

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

        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for OIDC SSO. Install with: uv add httpx "
                "or install the oauth extra: uv add django-matt[oauth]"
            )

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

    async def _get_jwks(self) -> dict:
        """
        Fetch the IdP's JWKS (JSON Web Key Set) for signature verification.

        Returns:
            JWKS dict with ``keys`` list.
        """
        # Try cache first
        cache_key = f"oidc_jwks:{self.connection.id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        config = await self._discover_config()
        jwks_uri = config.get("jwks_uri")
        if not jwks_uri:
            raise SSOConfigError("OIDC provider does not expose a jwks_uri in discovery config")

        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for OIDC SSO. Install with: uv add httpx "
                "or install the oauth extra: uv add django-matt[oauth]"
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_uri)
            if response.status_code != 200:
                raise SSOConfigError(f"Failed to fetch JWKS from {jwks_uri}: {response.text}")
            jwks = response.json()

        # Cache for 1 hour (keys rotate infrequently)
        cache.set(cache_key, jwks, 3600)
        return jwks

    def _generate_code_verifier(self) -> tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = code_challenge.hex().replace("+", "-").replace("/", "_").rstrip("=")
        # Actually use base64url encoding
        import base64

        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )

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
            raise SSOAuthenticationError(error_description or f"OIDC error: {error}")

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

        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for OIDC SSO. Install with: uv add httpx "
                "or install the oauth extra: uv add django-matt[oauth]"
            )

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
                error_data = (
                    response.json() if "json" in response.headers.get("content-type", "") else {}
                )
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
                user_data = await self._decode_id_token(id_token)

                # Verify nonce
                if expected_nonce and user_data.get("nonce") != expected_nonce:
                    raise SSOAuthenticationError("Invalid nonce in id_token")

            except SSOAuthenticationError:
                raise
            except Exception:
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

    async def _decode_id_token(self, id_token: str) -> dict:
        """
        Decode and verify an OIDC id_token JWT signature.

        Verification steps:
        1. Parse the JWT header to extract ``kid`` and ``alg``.
        2. Fetch the IdP's JWKS and find the matching key.
        3. Verify the cryptographic signature (RS256 or HS256).
        4. Return the decoded payload only if signature is valid.

        Args:
            id_token: The JWT id_token string.

        Returns:
            Decoded and verified token payload dict.

        Raises:
            SSOAuthenticationError: If the token is malformed or
                signature verification fails.
        """
        parts = id_token.split(".")
        if len(parts) != 3:
            raise SSOAuthenticationError("Invalid id_token format")

        header_b64, payload_b64, signature_b64 = parts

        # Decode header to get kid and alg
        try:
            header = orjson.loads(_b64url_decode(header_b64))
        except Exception as e:
            raise SSOAuthenticationError(f"Failed to decode id_token header: {e}")

        alg = header.get("alg", "RS256")
        kid = header.get("kid")

        # The data that was signed is "header.payload" as raw bytes
        signed_data = f"{header_b64}.{payload_b64}".encode("ascii")

        # Decode signature
        try:
            signature = _b64url_decode(signature_b64)
        except Exception as e:
            raise SSOAuthenticationError(f"Failed to decode id_token signature: {e}")

        # Verify based on algorithm
        if alg == "RS256":
            # Fetch JWKS and find matching key
            jwks = await self._get_jwks()
            keys = jwks.get("keys", [])

            matching_key = None
            if kid:
                matching_key = next((k for k in keys if k.get("kid") == kid), None)
            elif len(keys) == 1:
                # If no kid in header and only one key, use it
                matching_key = keys[0]

            if not matching_key:
                raise SSOAuthenticationError(
                    f"No matching JWK found for kid={kid!r} in IdP JWKS"
                )

            if not _verify_rs256_signature(signed_data, signature, matching_key):
                raise SSOAuthenticationError(
                    "id_token RS256 signature verification failed"
                )

        elif alg == "HS256":
            # HS256 uses the client_secret as the HMAC key
            client_secret = self.connection.client_secret
            if not client_secret:
                raise SSOAuthenticationError(
                    "HS256 id_token verification requires client_secret"
                )
            if not _verify_hs256_signature(signed_data, signature, client_secret):
                raise SSOAuthenticationError(
                    "id_token HS256 signature verification failed"
                )

        else:
            raise SSOAuthenticationError(
                f"Unsupported id_token signing algorithm: {alg}. "
                f"Only RS256 and HS256 are supported."
            )

        # Signature valid -- decode payload
        try:
            payload = orjson.loads(_b64url_decode(payload_b64))
        except Exception as e:
            raise SSOAuthenticationError(f"Failed to decode id_token payload: {e}")

        return payload

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

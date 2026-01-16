"""
Apple OAuth provider (Sign in with Apple).

Apple uses OAuth 2.0 with OpenID Connect, but with some unique requirements:
- Uses JWT for client authentication (not client_secret directly)
- Only provides user info on FIRST login (must be stored)
- Requires special handling for web vs native apps

Setup:
1. Go to https://developer.apple.com/account/resources/identifiers
2. Create an App ID with "Sign in with Apple" capability
3. Create a Services ID for web authentication
4. Create a Key for Sign in with Apple
5. Configure the settings below

Settings:
    DJANGO_MATT_OAUTH = {
        "APPLE": {
            "client_id": "com.yourdomain.yourapp",  # Services ID
            "team_id": "ABCD1234",  # Your Apple Team ID
            "key_id": "KEYID1234",  # Key ID from Apple
            "private_key": '''-----BEGIN PRIVATE KEY-----
            ...your .p8 file contents...
            -----END PRIVATE KEY-----''',
            "scopes": ["name", "email"],  # optional, these are defaults
        },
    }

Note: Apple only sends the user's name on the FIRST authorization.
      You must store it immediately or it will be lost.
"""

import time
from django_matt.auth.oauth.providers.base import (
    OAuthProvider,
    OAuthUserInfo,
    OAuthAuthenticationError,
)


class AppleOAuthProvider(OAuthProvider):
    """Apple Sign In (OAuth 2.0 + OIDC) provider."""

    name = "apple"
    authorization_url = "https://appleid.apple.com/auth/authorize"
    token_url = "https://appleid.apple.com/auth/token"
    userinfo_url = ""  # Apple doesn't have a userinfo endpoint
    supports_oidc = True

    def _ensure_configured(self):
        """Ensure Apple-specific configuration is present."""
        super()._ensure_configured()

        extra = self.provider_config.extra
        if not extra.get("team_id"):
            from django_matt.auth.oauth.providers.base import OAuthConfigError
            raise OAuthConfigError("team_id is required for Apple OAuth")

        if not extra.get("key_id"):
            from django_matt.auth.oauth.providers.base import OAuthConfigError
            raise OAuthConfigError("key_id is required for Apple OAuth")

        if not extra.get("private_key"):
            from django_matt.auth.oauth.providers.base import OAuthConfigError
            raise OAuthConfigError("private_key is required for Apple OAuth")

    def _generate_client_secret(self) -> str:
        """
        Generate a JWT client secret for Apple.

        Apple requires a JWT signed with your private key instead of
        a static client secret.
        """
        try:
            import jwt
        except ImportError:
            raise OAuthAuthenticationError(
                "PyJWT is required for Apple Sign In. Install with: pip install PyJWT"
            )

        extra = self.provider_config.extra
        now = int(time.time())

        headers = {
            "alg": "ES256",
            "kid": extra["key_id"],
        }

        payload = {
            "iss": extra["team_id"],
            "iat": now,
            "exp": now + 86400 * 180,  # 180 days max
            "aud": "https://appleid.apple.com",
            "sub": self.provider_config.client_id,
        }

        return jwt.encode(
            payload,
            extra["private_key"],
            algorithm="ES256",
            headers=headers,
        )

    def _customize_auth_params(self, params: dict) -> dict:
        """Add Apple-specific parameters."""
        # Apple requires response_mode for web
        params["response_mode"] = "form_post"
        return params

    def _customize_token_request(self, data: dict) -> dict:
        """Use generated JWT as client secret."""
        data["client_secret"] = self._generate_client_secret()
        return data

    def get_user_info(self, data: dict) -> OAuthUserInfo:
        """
        Parse Apple user info from id_token.

        Apple's id_token contains:
        {
            "iss": "https://appleid.apple.com",
            "sub": "unique-user-id",
            "aud": "com.yourdomain.yourapp",
            "email": "user@example.com",
            "email_verified": "true",  # String, not boolean!
            ...
        }

        Note: User's name is ONLY sent in the first authorization response,
        not in the id_token. It comes in the POST body as a "user" JSON string.
        """
        # Handle email_verified as string (Apple quirk)
        email_verified = data.get("email_verified")
        if isinstance(email_verified, str):
            email_verified = email_verified.lower() == "true"

        # Check for user info in raw data (first login only)
        user_data = data.get("user", {})
        if isinstance(user_data, str):
            import json
            try:
                user_data = json.loads(user_data)
            except (json.JSONDecodeError, TypeError):
                user_data = {}

        name_data = user_data.get("name", {})

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=data.get("sub", ""),
            email=data.get("email"),
            email_verified=email_verified or False,
            name=None,  # Apple doesn't provide full name in id_token
            first_name=name_data.get("firstName"),
            last_name=name_data.get("lastName"),
            picture=None,  # Apple doesn't provide profile picture
            locale=None,
            raw=data,
        )

    async def exchange_code(self, code: str, user_data: dict | None = None):
        """
        Exchange code for token.

        Args:
            code: Authorization code
            user_data: Optional user data from Apple's form_post response
                       (contains name on first login)
        """
        token = await super().exchange_code(code)

        # If user_data provided (first login), include it in raw token data
        if user_data and token.raw:
            token.raw["user"] = user_data

        return token

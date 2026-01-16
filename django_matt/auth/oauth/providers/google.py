"""
Google OAuth provider.

Google uses OAuth 2.0 with OpenID Connect (OIDC).

Setup:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID
3. Add authorized redirect URI: https://yourdomain.com/auth/oauth/google/callback
4. Copy client ID and client secret to settings

Settings:
    DJANGO_MATT_OAUTH = {
        "GOOGLE": {
            "client_id": "your-client-id.apps.googleusercontent.com",
            "client_secret": "your-client-secret",
            "scopes": ["openid", "email", "profile"],  # optional, these are defaults
        },
    }
"""

from django_matt.auth.oauth.providers.base import OAuthProvider, OAuthUserInfo


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth 2.0 + OIDC provider."""

    name = "google"
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    supports_oidc = True

    def _customize_auth_params(self, params: dict) -> dict:
        """Add Google-specific parameters."""
        # Request offline access for refresh token
        params["access_type"] = "offline"
        # Force consent screen to get refresh token
        params["prompt"] = "consent"
        return params

    def get_user_info(self, data: dict) -> OAuthUserInfo:
        """
        Parse Google user info.

        Google returns:
        {
            "sub": "1234567890",
            "email": "user@gmail.com",
            "email_verified": true,
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "picture": "https://...",
            "locale": "en"
        }
        """
        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=data.get("sub", data.get("id", "")),
            email=data.get("email"),
            email_verified=data.get("email_verified", False),
            name=data.get("name"),
            first_name=data.get("given_name"),
            last_name=data.get("family_name"),
            picture=data.get("picture"),
            locale=data.get("locale"),
            raw=data,
        )

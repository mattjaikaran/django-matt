"""
Microsoft OAuth provider (Microsoft Entra ID / Azure AD).

Microsoft uses OAuth 2.0 with OpenID Connect.

Setup:
1. Go to https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps
2. Register a new application
3. Add a Web redirect URI: https://yourdomain.com/auth/oauth/microsoft/callback
4. Create a client secret under "Certificates & secrets"
5. Copy Application (client) ID and client secret to settings

For consumer accounts (personal Microsoft accounts), use "common" tenant.
For work/school accounts only, use your tenant ID or "organizations".
For both, use "common".

Settings:
    DJANGO_MATT_OAUTH = {
        "MICROSOFT": {
            "client_id": "your-application-client-id",
            "client_secret": "your-client-secret",
            "scopes": ["openid", "email", "profile", "User.Read"],
            "extra": {
                "tenant": "common",  # or "organizations", "consumers", or tenant ID
            },
        },
    }
"""

from django_matt.auth.oauth.providers.base import OAuthProvider, OAuthUserInfo


class MicrosoftOAuthProvider(OAuthProvider):
    """Microsoft OAuth 2.0 + OIDC provider."""

    name = "microsoft"
    supports_oidc = True

    @property
    def tenant(self) -> str:
        """Get the Azure AD tenant."""
        if self.provider_config and self.provider_config.extra:
            return self.provider_config.extra.get("tenant", "common")
        return "common"

    @property
    def authorization_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/authorize"

    @property
    def token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"

    @property
    def userinfo_url(self) -> str:
        return "https://graph.microsoft.com/v1.0/me"

    def _customize_auth_params(self, params: dict) -> dict:
        """Add Microsoft-specific parameters."""
        # Request offline access for refresh token
        params["response_mode"] = "query"
        return params

    def get_user_info(self, data: dict) -> OAuthUserInfo:
        """
        Parse Microsoft user info.

        From id_token (OIDC):
        {
            "sub": "unique-id",
            "email": "user@example.com",
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "preferred_username": "user@example.com",
            ...
        }

        From Graph API (/me):
        {
            "id": "unique-id",
            "mail": "user@example.com",
            "displayName": "John Doe",
            "givenName": "John",
            "surname": "Doe",
            "userPrincipalName": "user@example.com",
            ...
        }
        """
        # Handle both OIDC and Graph API response formats
        user_id = data.get("sub") or data.get("id") or data.get("oid", "")
        email = (
            data.get("email")
            or data.get("mail")
            or data.get("preferred_username")
            or data.get("userPrincipalName")
        )
        name = data.get("name") or data.get("displayName")
        first_name = data.get("given_name") or data.get("givenName")
        last_name = data.get("family_name") or data.get("surname")

        # Microsoft doesn't always return email_verified
        email_verified = data.get("email_verified", False)
        if email and "@" in email:
            # If email looks valid, assume it's verified for Microsoft accounts
            email_verified = True

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=str(user_id),
            email=email,
            email_verified=email_verified,
            name=name,
            first_name=first_name,
            last_name=last_name,
            picture=None,  # Requires separate Graph API call
            locale=data.get("locale"),
            raw=data,
        )

"""
GitHub OAuth provider.

GitHub uses OAuth 2.0 (not OIDC).

Setup:
1. Go to https://github.com/settings/developers
2. Create a new OAuth App
3. Set Authorization callback URL: https://yourdomain.com/auth/oauth/github/callback
4. Copy client ID and client secret to settings

Settings:
    DJANGO_MATT_OAUTH = {
        "GITHUB": {
            "client_id": "your-client-id",
            "client_secret": "your-client-secret",
            "scopes": ["user:email", "read:user"],  # optional, these are defaults
        },
    }

Note: GitHub requires a separate API call to get user emails if email is private.
"""

from django_matt.auth.oauth.providers.base import (
    OAuthProvider,
    OAuthUserInfo,
    OAuthToken,
    OAuthUserInfoError,
)


class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth 2.0 provider."""

    name = "github"
    authorization_url = "https://github.com/login/oauth/authorize"
    token_url = "https://github.com/login/oauth/access_token"
    userinfo_url = "https://api.github.com/user"
    emails_url = "https://api.github.com/user/emails"
    supports_oidc = False

    async def fetch_user_info(self, token: OAuthToken) -> OAuthUserInfo:
        """
        Fetch user info from GitHub.

        GitHub requires a separate call to get emails if the user's email is private.
        """
        self._ensure_configured()

        import httpx

        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient() as client:
            # Get basic user info
            response = await client.get(self.userinfo_url, headers=headers)

            if response.status_code != 200:
                raise OAuthUserInfoError(
                    f"Failed to fetch GitHub user info: {response.text}"
                )

            user_data = response.json()

            # If email is not in user data, fetch from emails endpoint
            if not user_data.get("email"):
                email_response = await client.get(self.emails_url, headers=headers)
                if email_response.status_code == 200:
                    emails = email_response.json()
                    # Find primary email
                    for email_obj in emails:
                        if email_obj.get("primary"):
                            user_data["email"] = email_obj.get("email")
                            user_data["email_verified"] = email_obj.get("verified", False)
                            break
                    # Fallback to first verified email
                    if not user_data.get("email"):
                        for email_obj in emails:
                            if email_obj.get("verified"):
                                user_data["email"] = email_obj.get("email")
                                user_data["email_verified"] = True
                                break

        return self.get_user_info(user_data)

    def get_user_info(self, data: dict) -> OAuthUserInfo:
        """
        Parse GitHub user info.

        GitHub returns:
        {
            "id": 1234567,
            "login": "username",
            "email": "user@example.com",  # May be null if private
            "name": "John Doe",
            "avatar_url": "https://...",
            "bio": "...",
            ...
        }
        """
        # Parse name into first/last
        name = data.get("name", "")
        first_name = ""
        last_name = ""
        if name:
            parts = name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=str(data.get("id", "")),
            email=data.get("email"),
            email_verified=data.get("email_verified", False),
            name=name or data.get("login"),
            first_name=first_name,
            last_name=last_name,
            picture=data.get("avatar_url"),
            locale=None,  # GitHub doesn't provide locale
            raw=data,
        )

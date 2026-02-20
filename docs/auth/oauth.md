# OAuth Social Login

Social authentication with Google, GitHub, Apple, and Microsoft.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "OAUTH": {
        "PROVIDERS": {
            "google": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "redirect_uri": "https://myapp.com/auth/google/callback",
            },
            "github": {
                "client_id": os.environ["GITHUB_CLIENT_ID"],
                "client_secret": os.environ["GITHUB_CLIENT_SECRET"],
                "redirect_uri": "https://myapp.com/auth/github/callback",
            },
            "apple": {
                "client_id": os.environ["APPLE_CLIENT_ID"],
                "team_id": os.environ["APPLE_TEAM_ID"],
                "key_id": os.environ["APPLE_KEY_ID"],
                "private_key": os.environ["APPLE_PRIVATE_KEY"],
                "redirect_uri": "https://myapp.com/auth/apple/callback",
            },
            "microsoft": {
                "client_id": os.environ["MICROSOFT_CLIENT_ID"],
                "client_secret": os.environ["MICROSOFT_CLIENT_SECRET"],
                "tenant_id": os.environ.get("MICROSOFT_TENANT_ID", "common"),
                "redirect_uri": "https://myapp.com/auth/microsoft/callback",
            },
        },
    },
}
```

## OAuthController

Use the pre-built controller:

```python
from django_matt.auth.oauth import OAuthController

api.register_controller(OAuthController)

# Provides:
# GET /auth/{provider}/authorize - Redirect to provider
# GET /auth/{provider}/callback - Handle callback
# POST /auth/{provider}/token - Exchange code for tokens (SPA flow)
```

## OAuth Flow

### Server-Side Flow (Recommended)

1. **Redirect to provider:**
```
GET /auth/google/authorize
→ Redirects to Google login
```

2. **Handle callback:**
```
GET /auth/google/callback?code=xxx&state=yyy
→ Exchanges code for tokens
→ Creates/updates user
→ Returns JWT tokens
```

### SPA Flow

1. **Get auth URL:**
```python
@api.get("/auth/{provider}/url")
async def get_auth_url(request, provider: str):
    oauth = get_provider_instance(provider)
    url, state = oauth.get_authorization_url()
    return {"url": url, "state": state}
```

2. **Exchange code:**
```python
@api.post("/auth/{provider}/token")
async def exchange_token(request, provider: str, data: OAuthCallback):
    oauth = get_provider_instance(provider)
    user_info = await oauth.get_user_info(data.code)
    user = await get_or_create_user(user_info)
    return create_token_pair(user)
```

## Providers

### Google

```python
from django_matt.auth.oauth import GoogleOAuthProvider

google = GoogleOAuthProvider(
    client_id="...",
    client_secret="...",
    redirect_uri="...",
)

# Get authorization URL
url, state = google.get_authorization_url(
    scopes=["email", "profile"],
)

# Exchange code for user info
user_info = await google.get_user_info(code)
# Returns: OAuthUserInfo(id, email, name, picture, ...)
```

### GitHub

```python
from django_matt.auth.oauth import GitHubOAuthProvider

github = GitHubOAuthProvider(
    client_id="...",
    client_secret="...",
    redirect_uri="...",
)

user_info = await github.get_user_info(code)
```

### Apple

```python
from django_matt.auth.oauth import AppleOAuthProvider

apple = AppleOAuthProvider(
    client_id="...",  # Service ID
    team_id="...",
    key_id="...",
    private_key="...",  # .p8 file contents
    redirect_uri="...",
)

user_info = await apple.get_user_info(code)
```

### Microsoft

```python
from django_matt.auth.oauth import MicrosoftOAuthProvider

microsoft = MicrosoftOAuthProvider(
    client_id="...",
    client_secret="...",
    tenant_id="common",  # or specific tenant
    redirect_uri="...",
)

user_info = await microsoft.get_user_info(code)
```

## User Creation

```python
from django_matt.auth.oauth import OAuthUserInfo

async def get_or_create_user(info: OAuthUserInfo):
    user, created = await User.objects.aget_or_create(
        email=info.email,
        defaults={
            "first_name": info.first_name or "",
            "last_name": info.last_name or "",
            "is_active": True,
        },
    )

    # Store OAuth connection
    await OAuthConnection.objects.aupdate_or_create(
        user=user,
        provider=info.provider,
        defaults={
            "provider_user_id": info.id,
            "access_token": info.access_token,
            "refresh_token": info.refresh_token,
        },
    )

    return user
```

## Custom Provider

```python
from django_matt.auth.oauth import OAuthProvider, OAuthUserInfo

class CustomOAuthProvider(OAuthProvider):
    name = "custom"
    authorization_url = "https://custom.com/oauth/authorize"
    token_url = "https://custom.com/oauth/token"
    user_info_url = "https://custom.com/api/user"

    async def get_user_info(self, code: str) -> OAuthUserInfo:
        token = await self.exchange_code(code)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.user_info_url,
                headers={"Authorization": f"Bearer {token.access_token}"},
            )
            data = response.json()

        return OAuthUserInfo(
            id=data["id"],
            email=data["email"],
            name=data["name"],
            provider=self.name,
            access_token=token.access_token,
        )
```

## Error Handling

```python
from django_matt.auth.oauth import (
    OAuthError,
    OAuthConfigError,
    OAuthAuthenticationError,
    OAuthUserInfoError,
)

@api.get("/auth/{provider}/callback")
async def callback(request, provider: str, code: str, state: str):
    try:
        oauth = get_provider_instance(provider)
        user_info = await oauth.get_user_info(code)
        user = await get_or_create_user(user_info)
        return create_token_pair(user)
    except OAuthAuthenticationError as e:
        raise AuthenticationAPIError(f"OAuth failed: {e}")
    except OAuthUserInfoError as e:
        raise APIError(f"Failed to get user info: {e}")
```

## Security Considerations

1. **Validate state parameter** - Prevent CSRF attacks
2. **Use HTTPS** - OAuth requires secure connections
3. **Verify tokens** - Don't trust user-provided tokens
4. **Handle email changes** - Users may change email on provider
5. **Link accounts carefully** - Prevent account takeover

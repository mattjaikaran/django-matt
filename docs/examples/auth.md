# Authentication Examples

## Complete Auth Flow with JWT

```python
# auth_api.py
from django_matt import MattAPI
from django_matt.auth import jwt_required, create_token_pair
from django_matt.auth.schemas import RefreshTokenRequest
from django_matt.core import Schema
from django_matt.core.errors import AuthenticationAPIError, ValidationAPIError

from django.contrib.auth import authenticate, get_user_model
from pydantic import EmailStr, field_validator

User = get_user_model()
api = MattAPI(title="Auth API")

class RegisterSchema(Schema):
    email: EmailStr
    password: str
    password_confirm: str
    name: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

class LoginSchema(Schema):
    email: EmailStr
    password: str

class TokenResponse(Schema):
    access: str
    refresh: str
    user: dict

@api.post("/auth/register", tags=["Auth"])
async def register(request, data: RegisterSchema):
    """Register a new user."""
    if data.password != data.password_confirm:
        raise ValidationAPIError(
            message="Passwords don't match",
            errors={"password_confirm": ["Passwords don't match"]}
        )

    if await User.objects.filter(email=data.email).aexists():
        raise ValidationAPIError(
            message="Email already registered",
            errors={"email": ["Email already registered"]}
        )

    user = await User.objects.acreate_user(
        email=data.email,
        password=data.password,
        name=data.name,
    )

    tokens = create_token_pair(user)
    return TokenResponse(
        access=tokens.access_token,
        refresh=tokens.refresh_token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )

@api.post("/auth/login", tags=["Auth"])
async def login(request, data: LoginSchema):
    """Login with email and password."""
    user = await User.objects.filter(email=data.email).afirst()

    if not user or not user.check_password(data.password):
        raise AuthenticationAPIError("Invalid email or password")

    if not user.is_active:
        raise AuthenticationAPIError("Account is disabled")

    tokens = create_token_pair(user)
    return TokenResponse(
        access=tokens.access_token,
        refresh=tokens.refresh_token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )

@api.post("/auth/refresh", tags=["Auth"])
async def refresh(request, data: RefreshTokenRequest):
    """Refresh access token."""
    from django_matt.auth.jwt import async_refresh_tokens
    try:
        tokens = await async_refresh_tokens(data.refresh_token)
        return {"access": tokens.access_token}
    except Exception:
        raise AuthenticationAPIError("Invalid refresh token")

@api.get("/auth/me", tags=["Auth"])
@jwt_required
async def me(request):
    """Get current user profile."""
    user = request.user
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": user.date_joined.isoformat(),
    }

@api.post("/auth/logout", tags=["Auth"])
@jwt_required
async def logout(request):
    """Logout (client should discard tokens)."""
    # Optionally blacklist the token
    return {"success": True}
```

## OAuth Social Login

```python
# oauth_example.py
from django_matt import MattAPI
from django_matt.auth.oauth import (
    OAuthController,
    GoogleOAuthProvider,
    GitHubOAuthProvider,
)

api = MattAPI()

# Register OAuth controller (provides /oauth/* endpoints)
api.register_controller(OAuthController)

# Configure in settings.py
"""
MATT_OAUTH = {
    "google": {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": "http://localhost:8000/auth/oauth/google/callback",
    },
    "github": {
        "client_id": os.environ["GITHUB_CLIENT_ID"],
        "client_secret": os.environ["GITHUB_CLIENT_SECRET"],
        "redirect_uri": "http://localhost:8000/auth/oauth/github/callback",
    },
}
"""

# Frontend usage:
# 1. Redirect user to: GET /auth/oauth/google/authorize
# 2. User authorizes on Google
# 3. Google redirects to: /auth/oauth/google/callback?code=...
# 4. Backend exchanges code for tokens and creates/logs in user
# 5. Backend redirects to frontend with JWT tokens
```

## Passkey/WebAuthn Authentication

```python
# passkey_example.py
from django_matt import MattAPI
from django_matt.auth.passkeys import PasskeyController

api = MattAPI()

# Register passkey controller
api.register_controller(PasskeyController)

# Endpoints provided:
# POST /auth/passkeys/register/options - Get WebAuthn registration options
# POST /auth/passkeys/register/verify  - Complete registration
# POST /auth/passkeys/authenticate/options - Get authentication options
# POST /auth/passkeys/authenticate/verify  - Complete authentication

# Frontend example (using @simplewebauthn/browser):
"""
import { startRegistration, startAuthentication } from '@simplewebauthn/browser';

// Registration
async function registerPasskey() {
  // 1. Get options from server
  const optionsRes = await fetch('/auth/passkeys/register/options', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
  });
  const options = await optionsRes.json();

  // 2. Create credential
  const credential = await startRegistration(options);

  // 3. Verify with server
  const verifyRes = await fetch('/auth/passkeys/register/verify', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(credential),
  });

  return verifyRes.json();
}

// Authentication
async function loginWithPasskey(email) {
  // 1. Get options
  const optionsRes = await fetch('/auth/passkeys/authenticate/options', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  const options = await optionsRes.json();

  // 2. Get assertion
  const credential = await startAuthentication(options);

  // 3. Verify
  const verifyRes = await fetch('/auth/passkeys/authenticate/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credential),
  });

  return verifyRes.json(); // Returns JWT tokens
}
"""
```

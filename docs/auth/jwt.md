# JWT Authentication

JSON Web Token authentication for APIs.

## Configuration

```python
# settings.py
from datetime import timedelta

DJANGO_MATT_JWT = {
    "SECRET_KEY": os.environ.get("JWT_SECRET_KEY", SECRET_KEY),
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "ISSUER": "my-app",         # Optional
    "AUDIENCE": "my-app",       # Optional
    "USER_ID_FIELD": "id",      # Model field for user ID
    "USER_ID_CLAIM": "sub",     # JWT claim for user ID
    "AUTH_HEADER_TYPES": ["Bearer"],
    "AUTH_HEADER_NAME": "Authorization",
}
```

## Token Functions

### Creating Tokens

```python
from django_matt.auth import (
    create_token_pair,
    create_access_token,
    create_refresh_token,
)

# Create both access and refresh tokens
tokens = create_token_pair(user)
# Returns: TokenPair(access_token="...", refresh_token="...", token_type="bearer")

# Create individual tokens
access_token = create_access_token(user)
refresh_token = create_refresh_token(user)
```

### Verifying Tokens

```python
from django_matt.auth import (
    verify_access_token,
    verify_refresh_token,
    decode_token,
)

# Verify and decode — returns TokenPayload (not a user)
payload = verify_access_token(token)   # TokenPayload with sub, exp, iat, etc.
payload = verify_refresh_token(token)  # Verifies type="refresh"

# Decode with optional type verification
payload = decode_token(token, verify_type="access")

# Get user from token
from django_matt.auth import get_user_from_token
from django_matt.auth.jwt import aget_user_from_token

user = get_user_from_token(token)           # sync
user = await aget_user_from_token(token)    # async
```

### Refreshing Tokens

```python
from django_matt.auth import refresh_tokens
from django_matt.auth.jwt import async_refresh_tokens

# Get new token pair from refresh token (sync)
new_tokens = refresh_tokens(refresh_token_str)

# Async version — use from async controllers
new_tokens = await async_refresh_tokens(refresh_token_str)
```

## Middleware

```python
# settings.py
MIDDLEWARE = [
    # ... other middleware
    "django_matt.auth.JWTAuthenticationMiddleware",
]
```

The middleware:
- Extracts JWT from `Authorization: Bearer <token>` header
- Validates the token
- Sets `request.user` to the authenticated user
- Sets `request.auth` to the decoded token payload

### Async Middleware

For ASGI applications:

```python
MIDDLEWARE = [
    "django_matt.auth.JWTAuthenticationMiddlewareAsync",
]
```

### Strict Middleware

Returns 401 for all requests without valid JWT:

```python
MIDDLEWARE = [
    "django_matt.auth.JWTStrictAuthenticationMiddleware",
]
```

## Decorators

### @jwt_required

Requires a valid JWT:

```python
from django_matt.auth import jwt_required

@api.get("/profile")
@jwt_required
async def get_profile(request):
    # request.user is guaranteed to be authenticated
    return {"email": request.user.email}
```

### @jwt_optional

JWT is optional but validated if present:

```python
from django_matt.auth import jwt_optional

@api.get("/posts")
@jwt_optional
async def list_posts(request):
    if request.user.is_authenticated:
        # Show user's posts
        return await Post.objects.filter(user=request.user)
    else:
        # Show public posts
        return await Post.objects.filter(is_public=True)
```

## Custom Claims

Add custom claims to tokens via the `extra_claims` parameter:

```python
from django_matt.auth import create_token_pair, create_access_token

# Add extra claims when creating tokens
tokens = create_token_pair(user, extra_claims={
    "org_id": str(user.organization_id),
    "plan": "premium",
})

# Or for individual tokens
access = create_access_token(user, extra_claims={"org_id": str(user.organization_id)})
```

Note: `email`, `username`, and `roles` (from Django groups) are automatically included
in access tokens by default.

## Token Blacklisting

Django Matt includes a built-in token blacklist system with pluggable storage backends.

```python
from django_matt.auth import (
    blacklist_token,
    ablacklist_token,
    is_token_blacklisted,
    ais_token_blacklisted,
    prune_expired_tokens,
    BlacklistConfig,
    DatabaseBlacklistBackend,
    CacheBlacklistBackend,
    NullBlacklistBackend,
)
```

### Configuration

```python
# settings.py
from django_matt.auth.blacklist import BlacklistConfig, DatabaseBlacklistBackend

DJANGO_MATT_BLACKLIST = BlacklistConfig(
    backend=DatabaseBlacklistBackend(),  # or CacheBlacklistBackend(), NullBlacklistBackend()
)
```

### Revoking Tokens

```python
# On logout — synchronous
blacklist_token(token)

# On logout — async (from async controllers)
await ablacklist_token(token)

# Check if a token is blacklisted
if is_token_blacklisted(token):
    raise AuthenticationAPIError("Token has been revoked")

# Async check
if await ais_token_blacklisted(token):
    raise AuthenticationAPIError("Token has been revoked")

# Clean up expired entries
prune_expired_tokens()
```

### Storage Backends

| Backend | Description |
|---------|-------------|
| `DatabaseBlacklistBackend` | Stores revoked tokens in the database (default) |
| `CacheBlacklistBackend` | Stores in Django cache (Redis recommended) |
| `NullBlacklistBackend` | No-op — disables blacklisting |

## Asymmetric Keys (RS256/ES256)

For microservices or when public key verification is needed:

```python
# settings.py
DJANGO_MATT_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": open("private.pem").read(),
    "VERIFYING_KEY": open("public.pem").read(),
}
```

!!! note
    Asymmetric algorithms require the `cryptography` package:
    ```bash
    uv add "django-matt[jwt-asymmetric]"
    ```

## Error Handling

JWT errors return appropriate HTTP status codes:

| Error | Status | Code |
|-------|--------|------|
| Missing token | 401 | `MISSING_TOKEN` |
| Invalid token | 401 | `INVALID_TOKEN` |
| Expired token | 401 | `TOKEN_EXPIRED` |
| Invalid signature | 401 | `INVALID_SIGNATURE` |

```python
from django_matt.core import AuthenticationAPIError

@api.get("/protected")
@jwt_required
async def protected(request):
    # If token is invalid, AuthenticationAPIError is raised automatically
    # with appropriate error code
    pass
```

## Security Considerations

1. **Keep secrets secure** - Never commit JWT secrets to version control
2. **Use short-lived access tokens** - Minimize impact of token theft
3. **Implement token refresh** - Use refresh tokens for long sessions
4. **Use HTTPS** - JWTs should only be transmitted over TLS
5. **Consider token blacklisting** - For immediate logout capability
6. **Rotate secrets** - Periodically rotate JWT signing keys

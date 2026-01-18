# JWT Authentication

JSON Web Token authentication for APIs.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "JWT": {
        "SECRET_KEY": os.environ.get("JWT_SECRET_KEY", SECRET_KEY),
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_LIFETIME": 3600,  # 1 hour
        "REFRESH_TOKEN_LIFETIME": 604800,  # 7 days
        "ISSUER": "my-app",
        "AUDIENCE": "my-app",
        "LEEWAY": 0,  # Clock skew tolerance in seconds
    },
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

# Verify and get user
user = await verify_access_token(token)
user = await verify_refresh_token(token)

# Decode without verification (for debugging)
payload = decode_token(token, verify=False)
```

### Refreshing Tokens

```python
from django_matt.auth import refresh_tokens

# Get new token pair from refresh token
new_tokens = await refresh_tokens(refresh_token)
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

Add custom claims to tokens:

```python
from django_matt.auth.jwt import JWTConfig

jwt_config.get_user_claims = lambda user: {
    "email": user.email,
    "roles": list(user.groups.values_list("name", flat=True)),
    "org_id": user.organization_id,
}
```

Access claims in views:

```python
@api.get("/me")
@jwt_required
async def get_me(request):
    claims = request.auth  # Decoded JWT payload
    return {
        "user_id": claims["sub"],
        "roles": claims.get("roles", []),
    }
```

## Token Blacklisting

For logout functionality:

```python
from django_matt.auth.jwt import blacklist_token, is_token_blacklisted

@api.post("/auth/logout")
@jwt_required
async def logout(request):
    token = request.auth
    await blacklist_token(token["jti"])
    return {"message": "Logged out"}
```

## Asymmetric Keys (RS256/ES256)

For microservices or when public key verification is needed:

```python
# settings.py
DJANGO_MATT = {
    "JWT": {
        "ALGORITHM": "RS256",
        "PRIVATE_KEY": open("private.pem").read(),
        "PUBLIC_KEY": open("public.pem").read(),
    },
}
```

!!! note
    Asymmetric algorithms require the `cryptography` package:
    ```bash
    pip install django-matt[jwt-asymmetric]
    ```

## Error Handling

JWT errors return appropriate HTTP status codes:

| Error | Status | Code |
|-------|--------|------|
| Missing token | 401 | `MISSING_TOKEN` |
| Invalid token | 401 | `INVALID_TOKEN` |
| Expired token | 401 | `TOKEN_EXPIRED` |
| Invalid signature | 401 | `INVALID_SIGNATURE` |
| Blacklisted token | 401 | `TOKEN_BLACKLISTED` |

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

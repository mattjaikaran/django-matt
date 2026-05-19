# Auth Flows

JWT login, refresh, logout, protected endpoints, magic links, and RBAC.

---

## Setup

Register the built-in `AuthController` to get all auth endpoints at `/auth/*`:

```python
# urls.py or api setup
from django_matt import MattAPI
from django_matt.auth.controllers import AuthController

api = MattAPI()
api.register_controller(AuthController)
```

This mounts:
- `POST /auth/login`
- `POST /auth/login/username`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET  /auth/verify`
- `POST /auth/magic-link/request`
- `POST /auth/magic-link/verify`
- `GET  /auth/magic-link/check`

---

## JWT Login / Refresh / Logout

### Login

```http
POST /auth/login
Content-Type: application/json

{"email": "alice@example.com", "password": "s3cr3t"}
```

Response:

```json
{
  "user": {"id": 1, "email": "alice@example.com", "roles": ["member"]},
  "tokens": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 900,
    "refresh_expires_in": 604800
  }
}
```

### Refresh

```http
POST /auth/refresh
Content-Type: application/json

{"refresh_token": "eyJ..."}
```

Returns a new `TokenPair`. If `ROTATE_REFRESH_TOKENS` is true the old refresh token is blacklisted.

### Logout

```http
POST /auth/logout
Authorization: Bearer eyJ...
```

Blacklists the current access token (and refresh token if included in the body).

---

## Settings

```python
# settings.py
from datetime import timedelta

DJANGO_MATT_JWT = {
    "SECRET_KEY": env("JWT_SECRET_KEY"),   # defaults to Django SECRET_KEY
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # Asymmetric (RS256, ES256):
    # "SIGNING_KEY": env("JWT_PRIVATE_KEY"),
    # "VERIFYING_KEY": env("JWT_PUBLIC_KEY"),
}
```

---

## Protected Endpoints

### `@jwt_required`

Requires a valid `Bearer` token. Sets `request.user` and `request.token_payload`.

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get, post
from django_matt.auth.decorators import jwt_required

class ProfileController(APIController):
    prefix = "/profile"

    @get("/")
    @jwt_required
    async def me(self, request):
        user = request.user
        payload = request.token_payload  # TokenPayload
        return {"id": user.id, "email": user.email, "roles": payload.roles}
```

Returns `401` for missing, expired, or invalid tokens.

### `@jwt_optional`

Proceeds with `request.user = AnonymousUser` when no token is present.

```python
from django_matt.auth.decorators import jwt_optional

@get("/feed")
@jwt_optional
async def feed(self, request):
    if request.user.is_authenticated:
        return await personalized_feed(request.user)
    return await public_feed()
```

---

## Role & Permission Guards

### `@with_roles`

```python
from django_matt.auth.decorators import with_roles

# Any of these roles
@post("/publish")
@with_roles("editor", "admin")
async def publish(self, request):
    ...

# Must have ALL roles
@post("/audit")
@with_roles("auditor", "compliance", require_all=True)
async def audit(self, request):
    ...
```

### `@with_permission`

```python
from django_matt.auth.decorators import with_permission

@delete("/{id}")
@with_permission("delete", resource="posts")
async def delete_post(self, request, id: int):
    ...
```

### Convenience guards

```python
from django_matt.auth.decorators import admin_required, superuser_required

@admin_required    # requires is_staff or is_superuser
@superuser_required  # requires is_superuser
```

### Role configuration

```python
DJANGO_MATT_RBAC = {
    "ROLES": {
        "viewer":  {"permissions": ["read", "list"], "priority": 1},
        "editor":  {"permissions": ["create", "update"], "inherits": ["viewer"], "priority": 2},
        "manager": {"permissions": ["delete", "publish"], "inherits": ["editor"], "priority": 3},
        "admin":   {"permissions": ["manage_users"], "inherits": ["manager"], "priority": 4},
    },
    "DEFAULT_ROLE": "viewer",
    "USE_DJANGO_GROUPS": True,
}
```

### Manual RBAC checks

```python
from django_matt.auth.rbac import user_has_permission, user_has_role, get_user_roles

roles = get_user_roles(user)                              # list[str]
ok = user_has_permission(user, "delete", resource="posts")  # bool
ok = user_has_role(user, "admin")                         # bool
```

---

## Programmatic Token Creation

```python
from django_matt.auth import create_token_pair, acreate_token_pair

# Sync (e.g. management commands, signals)
tokens = create_token_pair(user)

# Async (controllers, async views)
tokens = await acreate_token_pair(user)

print(tokens.access_token)
print(tokens.expires_in)   # seconds
```

### Extra claims (e.g. org context)

```python
tokens = await acreate_token_pair(user, extra_claims={"org_id": "org_abc"})

# Read back
from django_matt.auth import averify_access_token
payload = await averify_access_token(tokens.access_token)
print(payload.org_id)
```

### Verify a token

```python
from django_matt.auth import verify_access_token, InvalidTokenError, ExpiredSignatureError

try:
    payload = verify_access_token(token_string)
    print(payload.sub)    # user ID
    print(payload.roles)
except ExpiredSignatureError:
    ...  # token is expired
except InvalidTokenError:
    ...  # malformed or tampered
```

### Token blacklisting

```python
from django_matt.auth import blacklist_token, ablacklist_token

payload = verify_access_token(token_string)
blacklist_token(payload.jti, payload.exp)   # sync
await ablacklist_token(payload.jti, payload.exp)  # async
```

---

## Magic Links (Passwordless)

### Request a link

```http
POST /auth/magic-link/request
Content-Type: application/json

{"email": "alice@example.com"}
```

Always returns `200` to prevent email enumeration.

### Verify the link

```http
POST /auth/magic-link/verify
Content-Type: application/json

{"token": "<token-from-email>"}
```

Response includes `user`, `tokens`, and `user_created` (when registration is allowed).

### Settings

```python
DJANGO_MATT_MAGIC_LINK = {
    "TOKEN_LIFETIME": timedelta(minutes=15),
    "MAX_USES": 1,
    "BASE_URL": "https://myapp.com",
    "VERIFY_PATH": "/auth/magic-link/verify",
    "CREATE_USER_IF_NOT_EXISTS": False,
    "EMAIL_SUBJECT": "Your login link",
}
```

### Programmatic usage

```python
from django_matt.auth.magic_link import (
    create_magic_link_url,
    verify_magic_link_token,
    averify_magic_link_token,
    send_magic_link_async,
)

# Generate and send
url = create_magic_link_url("alice@example.com")
await send_magic_link_async("alice@example.com", url)

# Verify (e.g. custom endpoint)
result = await averify_magic_link_token(token_string)
if result.valid:
    user = result.user
    was_created = result.user_created
else:
    print(result.error)
```

---

## Schemas Reference

```python
from django_matt.auth.schemas import (
    LoginRequest,          # email, password
    RefreshTokenRequest,   # refresh_token
    RegisterRequest,       # email, password, password_confirm, username?
    TokenPair,             # access_token, refresh_token, token_type, expires_in
    TokenPayload,          # sub, exp, iat, type, roles, permissions, org_id
    UserResponse,          # id, email, roles, permissions, ...
    AuthResponse,          # user + tokens
    MagicLinkRequest,      # email
    MagicLinkVerifyRequest,# token
)
```

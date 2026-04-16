# django-matt-clerk-auth

Clerk authentication integration for django-matt. Verifies Clerk session JWTs,
syncs Clerk users to Django, and handles Clerk webhook events.

## Installation

```bash
uv add django-matt-clerk-auth
```

## Configuration

```python
# settings.py
MATT_CLERK = {
    "PUBLISHABLE_KEY": "pk_...",
    "SECRET_KEY": "sk_...",
    "WEBHOOK_SECRET": "whsec_...",
    "JWKS_URL": "https://{your-domain}.clerk.accounts.dev/.well-known/jwks.json",
    "API_BASE_URL": "https://api.clerk.com/v1",
    "AUTO_CREATE_USER": True,   # create Django user on first JWT verification
    "WEBHOOK_PATH": "/webhooks/clerk",
}
```

## Usage

The plugin automatically:
- Adds `ClerkAuthMiddleware` that verifies Clerk session JWTs on every request
- Sets `request.user` to the synced Django user
- Registers a webhook endpoint for Clerk user events (`user.created`, `user.updated`, `user.deleted`)
- Emits `clerk.*` events on the django-matt event bus

### Protecting views

The middleware runs on all requests. Unauthenticated requests get an
anonymous user (same as Django's default behavior). Use django-matt's
`IsAuthenticated` permission class to protect specific controllers.

```python
from django_matt.permissions import IsAuthenticated

class ProtectedController(Controller):
    permission_classes = [IsAuthenticated]
    ...
```

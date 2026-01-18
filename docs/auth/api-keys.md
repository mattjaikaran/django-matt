# API Keys

API key authentication for server-to-server communication and third-party integrations.

## Overview

Django Matt provides a Stripe-like API key system with:
- Live and test keys (`sk_live_*` and `sk_test_*` prefixes)
- Scoped permissions
- Plan-based rate limiting
- Usage tracking and analytics
- IP allowlisting

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "API_KEYS": {
        "PREFIX_LIVE": "sk_live_",
        "PREFIX_TEST": "sk_test_",
        "KEY_LENGTH": 32,
        "HASH_ALGORITHM": "sha256",
        "RATE_LIMITS": {
            "free": 1000,      # requests per hour
            "starter": 10000,
            "pro": 100000,
            "enterprise": None,  # unlimited
        },
    },
}
```

## Creating API Keys

```python
from django_matt.auth.api_keys import create_api_key, acreate_api_key

# Synchronous
api_key, raw_key = create_api_key(
    user=user,
    name="My Integration",
    scopes=["read:posts", "write:posts"],
    is_live=True,
)

# Async
api_key, raw_key = await acreate_api_key(
    user=user,
    name="Production Key",
    scopes=["*"],  # All permissions
    is_live=True,
    plan="pro",
)

# raw_key is only available once - store it securely!
print(f"API Key: {raw_key}")  # sk_live_abc123...
```

## Decorators

### @api_key_required

```python
from django_matt.auth.api_keys import api_key_required

@api.get("/data")
@api_key_required
async def get_data(request):
    # request.api_key contains the APIKey object
    return {"data": [...]}
```

### @api_key_optional

```python
from django_matt.auth.api_keys import api_key_optional

@api.get("/public-data")
@api_key_optional
async def get_public_data(request):
    if request.api_key:
        # Return more data for authenticated requests
        return {"data": [...], "extra": [...]}
    return {"data": [...]}
```

### @requires_scope

```python
from django_matt.auth.api_keys import requires_scope

@api.post("/posts")
@api_key_required
@requires_scope("write:posts")
async def create_post(request, data: PostCreate):
    # Only API keys with "write:posts" scope can access
    ...
```

### @requires_live_key

```python
from django_matt.auth.api_keys import requires_live_key

@api.post("/payments")
@api_key_required
@requires_live_key
async def create_payment(request, data: PaymentCreate):
    # Only live keys (sk_live_*) can access
    ...
```

### @requires_plan

```python
from django_matt.auth.api_keys import requires_plan

@api.get("/premium-feature")
@api_key_required
@requires_plan("pro", "enterprise")
async def premium_feature(request):
    # Only pro or enterprise plans can access
    ...
```

## Middleware

```python
# settings.py
MIDDLEWARE = [
    # Authentication
    "django_matt.auth.api_keys.APIKeyAuthenticationMiddleware",
    # Rate limiting
    "django_matt.auth.api_keys.APIKeyRateLimitMiddleware",
    # Usage tracking
    "django_matt.auth.api_keys.APIKeyUsageTrackingMiddleware",
]
```

## Key Rotation

```python
from django_matt.auth.api_keys import rotate_api_key, arotate_api_key

# Rotate a key (generates new key, keeps same permissions)
new_api_key, raw_key = await arotate_api_key(api_key)
```

## APIKeyController

Pre-built controller for key management:

```python
from django_matt.auth.api_keys import APIKeyController

api.register_controller(APIKeyController, prefix="/api-keys")

# Provides:
# GET /api-keys/ - List user's API keys
# POST /api-keys/ - Create new API key
# GET /api-keys/{id} - Get API key details
# DELETE /api-keys/{id} - Revoke API key
# POST /api-keys/{id}/rotate - Rotate API key
# GET /api-keys/{id}/usage - Get usage statistics
# GET /api-keys/{id}/export - Export usage data (CSV/JSON)
```

## Usage Tracking

API key usage is tracked hourly:

```python
from django_matt.auth.api_keys import APIKeyUsage

# Get usage for a key
usage = await APIKeyUsage.objects.filter(
    api_key=api_key,
    hour__gte=start_date,
).aaggregate(total=Sum("request_count"))
```

## IP Allowlisting

Restrict API keys to specific IP addresses:

```python
api_key, raw_key = await acreate_api_key(
    user=user,
    name="Restricted Key",
    allowed_ips=["192.168.1.1", "10.0.0.0/8"],
)
```

## Scopes

Common scope patterns:

| Scope | Description |
|-------|-------------|
| `*` | All permissions |
| `read:*` | All read permissions |
| `write:*` | All write permissions |
| `read:posts` | Read posts |
| `write:posts` | Create/update posts |
| `delete:posts` | Delete posts |

```python
from django_matt.auth.api_keys import requires_scope

@api.get("/users")
@requires_scope("read:users")
async def list_users(request):
    ...

@api.delete("/users/{id}")
@requires_scope("delete:users")
async def delete_user(request, id: int):
    ...
```

## Rate Limiting

Rate limits are enforced per API key:

```python
# Default rate limits by plan
PLAN_RATE_LIMITS = {
    "free": 1000,       # 1,000/hour
    "starter": 10000,   # 10,000/hour
    "pro": 100000,      # 100,000/hour
    "enterprise": None,  # Unlimited
}
```

When rate limited, the API returns:

```json
{
    "error": {
        "message": "Rate limit exceeded",
        "code": "RATE_LIMIT_EXCEEDED",
        "details": {
            "retry_after": 3600,
            "limit": 1000,
            "remaining": 0
        }
    }
}
```

## Security Best Practices

1. **Never log raw keys** - Only store hashed keys
2. **Use scopes** - Grant minimum necessary permissions
3. **Use test keys for development** - Keep live keys for production
4. **Rotate keys regularly** - Especially after team changes
5. **Enable IP allowlisting** - For known server IPs
6. **Monitor usage** - Detect anomalies and abuse

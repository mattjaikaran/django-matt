# Throttling

Django-matt provides rate limiting to protect your API from abuse and ensure fair usage.

## Overview

Throttling limits the number of requests a client can make within a time window. When exceeded, requests return `429 Too Many Requests`.

## Quick Start

```python
from django_matt.throttling import throttle, UserRateThrottle

@api.get("/resource")
@throttle(rate="100/hour")
async def limited_endpoint(request):
    return {"message": "Success"}
```

---

## Built-in Throttle Classes

### AnonRateThrottle

Rate limit anonymous (unauthenticated) users by IP address:

```python
from django_matt.throttling import AnonRateThrottle, throttle

@api.get("/public")
@throttle(AnonRateThrottle, rate="100/hour")
async def public_endpoint(request):
    return {"data": "public"}
```

- **Default rate**: 100 requests/hour
- **Scope**: `anon`
- **Key**: Client IP address
- **Authenticated users**: Bypass this throttle

### UserRateThrottle

Rate limit authenticated users by user ID:

```python
from django_matt.throttling import UserRateThrottle, throttle

@api.get("/user")
@throttle(UserRateThrottle, rate="1000/day")
async def user_endpoint(request):
    return {"data": "user"}
```

- **Default rate**: 1000 requests/day
- **Scope**: `user`
- **Key**: User ID (or IP for anonymous)

### ScopedRateThrottle

Different limits for different API sections:

```python
from django_matt.throttling import ScopedRateThrottle, throttle

# Configure rates in settings.py
THROTTLE_RATES = {
    "uploads": "10/hour",
    "search": "30/minute",
    "default": "1000/day",
}

@api.post("/upload")
@throttle(ScopedRateThrottle, scope="uploads")
async def upload_file(request):
    return {"uploaded": True}

@api.get("/search")
@throttle(ScopedRateThrottle, scope="search")
async def search(request):
    return {"results": []}
```

### BurstRateThrottle

Allow short bursts while maintaining overall limits:

```python
from django_matt.throttling import BurstRateThrottle, throttle

@api.get("/api")
@throttle(BurstRateThrottle, burst_rate="10/second", sustained_rate="100/minute")
async def burst_endpoint(request):
    return {"data": "ok"}
```

Checks both limits:
- **Burst**: Short-term limit (e.g., 10 requests/second)
- **Sustained**: Long-term limit (e.g., 100 requests/minute)

---

## Rate Format

Rates are specified as `"number/period"`:

| Format | Duration |
|--------|----------|
| `100/s` or `100/second` | 1 second |
| `100/m` or `100/minute` | 60 seconds |
| `100/h` or `100/hour` | 3600 seconds |
| `100/d` or `100/day` | 86400 seconds |

Examples:
```python
"10/second"      # 10 requests per second
"60/minute"      # 60 requests per minute
"1000/hour"      # 1000 requests per hour
"10000/day"      # 10000 requests per day
```

---

## Using the `@throttle` Decorator

### Basic Usage

```python
from django_matt.throttling import throttle

# Auto-select throttle class based on authentication
@throttle(rate="100/hour")
async def my_endpoint(request):
    pass
```

### With Specific Class

```python
from django_matt.throttling import throttle, UserRateThrottle

@throttle(UserRateThrottle, rate="500/hour")
async def user_endpoint(request):
    pass
```

### Method-Specific Throttling

```python
from django_matt.throttling import throttle

# Only throttle POST requests
@throttle(rate="10/hour", methods=["POST"])
async def create_resource(request):
    pass
```

### Scoped Throttling

```python
from django_matt.throttling import throttle, ScopedRateThrottle

@throttle(ScopedRateThrottle, scope="expensive")
async def expensive_operation(request):
    pass
```

---

## Shortcut Decorators

### `@throttle_anon`

Quick anonymous user throttling:

```python
from django_matt.throttling import throttle_anon

@throttle_anon("50/hour")
async def public_endpoint(request):
    pass
```

### `@throttle_user`

Quick authenticated user throttling:

```python
from django_matt.throttling import throttle_user

@throttle_user("500/hour")
async def user_endpoint(request):
    pass
```

---

## Class-Based Views

### ThrottlesMixin

Add throttling to ViewSets:

```python
from django_matt.throttling import ThrottlesMixin, UserRateThrottle, AnonRateThrottle
from django_matt.views import APIViewSet

class ProductViewSet(ThrottlesMixin, APIViewSet):
    model = Product

    throttle_classes = [UserRateThrottle, AnonRateThrottle]
    throttle_rates = {
        "UserRateThrottle": "1000/day",
        "AnonRateThrottle": "100/hour",
    }

    list_products = ListView()
    create_product = CreateView()
```

---

## Middleware

Apply throttling globally:

```python
# settings.py
MIDDLEWARE = [
    ...
    'django_matt.throttling.ThrottleMiddleware',
]

# Configure default throttles
MATT_THROTTLE_CLASSES = [
    'django_matt.throttling.AnonRateThrottle',
    'django_matt.throttling.UserRateThrottle',
]

THROTTLE_RATES = {
    'anon': '100/hour',
    'user': '1000/day',
}
```

---

## Storage Backends

### InMemoryBackend (Default)

Good for development, single-server deployments:

```python
from django_matt.throttling import InMemoryBackend

# Used by default
```

### RedisBackend

For production, multi-server deployments:

```python
from django_matt.throttling import RedisBackend

# settings.py
MATT_THROTTLE_BACKEND = RedisBackend(
    host='localhost',
    port=6379,
    db=0,
)
```

---

## Custom Throttle Classes

### Basic Custom Throttle

```python
from django_matt.throttling import BaseThrottle

class IPBasedThrottle(BaseThrottle):
    """Custom IP-based throttling."""

    rate = "50/minute"
    scope = "ip"

    def get_cache_key(self, request):
        ip = self.get_ident(request)
        return f"throttle:{self.scope}:{ip}"
```

### Premium User Throttle

```python
class PremiumUserThrottle(BaseThrottle):
    """Higher limits for premium users."""

    scope = "premium"

    def get_cache_key(self, request):
        if not request.user.is_authenticated:
            return None  # Skip for anonymous

        # Different rates based on plan
        if hasattr(request.user, 'subscription'):
            plan = request.user.subscription.plan
            if plan == 'premium':
                self.rate = "10000/day"
            elif plan == 'basic':
                self.rate = "1000/day"
            else:
                self.rate = "100/day"

            self.num_requests, self.duration = self.parse_rate(self.rate)

        return f"throttle:{self.scope}:{request.user.pk}"
```

### Endpoint-Specific Throttle

```python
class EndpointThrottle(BaseThrottle):
    """Different rates per endpoint."""

    def get_cache_key(self, request):
        endpoint = request.path
        user_id = request.user.pk if request.user.is_authenticated else self.get_ident(request)
        return f"throttle:endpoint:{endpoint}:{user_id}"

    def allow_request(self, request):
        # Set rate based on endpoint
        endpoint_rates = {
            '/api/search': '30/minute',
            '/api/upload': '10/hour',
            '/api/export': '5/hour',
        }

        self.rate = endpoint_rates.get(request.path, '1000/day')
        self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request)
```

---

## Response Headers

Rate limit information is included in response headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1706140800
Retry-After: 3600  # (Only when throttled)
```

---

## Error Handling

### ThrottleError

Raised when rate limit is exceeded:

```python
from django_matt.throttling import ThrottleError

try:
    response = await process_request(request)
except ThrottleError as e:
    return JsonResponse({
        "detail": e.message,
        "wait_seconds": e.wait,
    }, status=429, headers=e.headers)
```

### Default Response

When throttled:
```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds.",
  "code": "throttled"
}
```
Status: 429 Too Many Requests

---

## Configuration

### Django Settings

```python
# settings.py

# Default throttle backend
MATT_THROTTLE_BACKEND = 'django_matt.throttling.InMemoryBackend'
# or
MATT_THROTTLE_BACKEND = 'django_matt.throttling.RedisBackend'

# Redis configuration
MATT_THROTTLE_REDIS = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
}

# Scoped rates
THROTTLE_RATES = {
    'anon': '100/hour',
    'user': '1000/day',
    'uploads': '10/hour',
    'search': '30/minute',
    'exports': '5/hour',
}
```

---

## Complete Example

```python
from django_matt.views import APIViewSet, ListView, CreateView
from django_matt.throttling import (
    BaseThrottle,
    UserRateThrottle,
    AnonRateThrottle,
    ScopedRateThrottle,
    throttle,
    ThrottlesMixin,
)


# Custom throttle for API tiers
class TieredThrottle(BaseThrottle):
    """Rate limits based on subscription tier."""

    TIER_RATES = {
        'free': '100/day',
        'basic': '1000/day',
        'pro': '10000/day',
        'enterprise': '100000/day',
    }

    def get_cache_key(self, request):
        if not request.user.is_authenticated:
            return f"throttle:anon:{self.get_ident(request)}"

        tier = getattr(request.user, 'subscription_tier', 'free')
        self.rate = self.TIER_RATES.get(tier, self.TIER_RATES['free'])
        self.num_requests, self.duration = self.parse_rate(self.rate)

        return f"throttle:tiered:{request.user.pk}"


class ProductViewSet(ThrottlesMixin, APIViewSet):
    model = Product
    prefix = "products"

    # Default throttling
    throttle_classes = [TieredThrottle]

    # Standard list (uses default throttle)
    list_products = ListView()

    # Create with additional limit
    @throttle(ScopedRateThrottle, scope="writes")
    create_product = CreateView()

    # Export with strict limit
    @throttle(rate="5/hour")
    async def export_all(self, request):
        products = await self.get_queryset(request).aall()
        return {"products": [p.to_dict() for p in products]}

    # Search with burst protection
    @throttle(AnonRateThrottle, rate="30/minute")
    async def search(self, request):
        query = request.GET.get('q', '')
        results = await self.model.objects.filter(name__icontains=query)[:100]
        return {"results": list(results)}


# settings.py
THROTTLE_RATES = {
    'anon': '100/hour',
    'user': '1000/day',
    'writes': '100/hour',
    'search': '30/minute',
    'exports': '5/hour',
}

MATT_THROTTLE_BACKEND = RedisBackend(
    host='redis',
    port=6379,
)
```

## Best Practices

1. **Start with generous limits**: Tighten as needed based on usage patterns
2. **Use Redis in production**: For consistent limits across servers
3. **Different rates for operations**: Stricter for writes, looser for reads
4. **Include headers**: Help clients understand their limits
5. **Monitor and adjust**: Track 429 responses and adjust rates
6. **Consider user tiers**: Premium users may need higher limits
7. **Protect expensive endpoints**: Stricter limits for resource-intensive operations

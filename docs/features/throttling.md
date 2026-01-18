# Rate Limiting

Protect your API from abuse with rate limiting.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "THROTTLING": {
        "DEFAULT_RATES": {
            "anon": "100/hour",
            "user": "1000/hour",
        },
        "BACKEND": "django_matt.throttling.RedisBackend",
    },
}
```

## Throttle Classes

### Built-in Classes

```python
from django_matt.throttling import (
    AnonRateThrottle,      # Rate limit anonymous users
    UserRateThrottle,      # Rate limit authenticated users
    ScopedRateThrottle,    # Different rates per scope
    BurstRateThrottle,     # Short burst + sustained limit
)
```

### Usage on Controllers

```python
from django_matt.throttling import UserRateThrottle

@api.controller("/api")
class MyController(APIController):
    throttle_classes = [UserRateThrottle]

    @get("/data")
    async def get_data(self, request):
        ...
```

### Per-View Throttling

```python
from django_matt.throttling import throttle

@api.post("/expensive-operation")
@throttle("10/minute")
async def expensive_operation(request):
    ...

@api.post("/login")
@throttle("5/minute", scope="login")
async def login(request, data: LoginRequest):
    ...
```

## Rate Formats

| Format | Meaning |
|--------|---------|
| `100/second` | 100 requests per second |
| `1000/minute` | 1000 requests per minute |
| `10000/hour` | 10000 requests per hour |
| `100000/day` | 100000 requests per day |

## Scoped Throttling

Different rates for different endpoints:

```python
# settings.py
DJANGO_MATT = {
    "THROTTLING": {
        "SCOPED_RATES": {
            "login": "5/minute",
            "signup": "3/minute",
            "api": "1000/hour",
            "upload": "10/hour",
        },
    },
}
```

```python
from django_matt.throttling import ScopedRateThrottle

class AuthController(APIController):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @post("/login")
    async def login(self, request, data: LoginRequest):
        ...
```

## Burst Throttling

Allow short bursts with sustained limits:

```python
from django_matt.throttling import BurstRateThrottle

class ApiBurstThrottle(BurstRateThrottle):
    burst_rate = "100/second"
    sustained_rate = "10000/hour"

@api.controller("/api")
class MyController(APIController):
    throttle_classes = [ApiBurstThrottle]
```

## Middleware

Global throttling via middleware:

```python
# settings.py
MIDDLEWARE = [
    "django_matt.throttling.ThrottleMiddleware",
]

DJANGO_MATT = {
    "THROTTLING": {
        "DEFAULT_RATE": "1000/hour",
    },
}
```

### Path-Specific Throttling

```python
# settings.py
MIDDLEWARE = [
    "django_matt.throttling.PathSpecificThrottleMiddleware",
]

DJANGO_MATT = {
    "THROTTLING": {
        "PATH_RATES": {
            "/api/auth/login": "5/minute",
            "/api/auth/register": "3/minute",
            "/api/upload": "10/hour",
            "/api/*": "1000/hour",
        },
    },
}
```

## Backends

### In-Memory (Development)

```python
DJANGO_MATT = {
    "THROTTLING": {
        "BACKEND": "django_matt.throttling.InMemoryBackend",
    },
}
```

### Redis (Production)

```python
DJANGO_MATT = {
    "THROTTLING": {
        "BACKEND": "django_matt.throttling.RedisBackend",
        "REDIS_URL": "redis://localhost:6379/1",
    },
}
```

### Django Cache

```python
DJANGO_MATT = {
    "THROTTLING": {
        "BACKEND": "django_matt.throttling.CacheBackend",
        "CACHE_ALIAS": "throttling",
    },
}
```

## Custom Throttle Classes

```python
from django_matt.throttling import BaseThrottle

class PremiumUserThrottle(BaseThrottle):
    """Higher limits for premium users."""

    def get_rate(self, request):
        if request.user.is_authenticated:
            if request.user.subscription_tier == "premium":
                return "100000/hour"
            return "10000/hour"
        return "1000/hour"

    def get_cache_key(self, request):
        if request.user.is_authenticated:
            return f"throttle:user:{request.user.id}"
        return f"throttle:anon:{self.get_ident(request)}"
```

## Response Headers

Throttle information is included in response headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1609459200
```

## Handling Throttled Requests

When rate limited, the API returns HTTP 429:

```json
{
    "error": {
        "message": "Request was throttled. Expected available in 3600 seconds.",
        "code": "RATE_LIMIT_EXCEEDED",
        "details": {
            "retry_after": 3600
        }
    }
}
```

With `Retry-After` header.

# Rate Limiting

Per-user, per-IP, per-endpoint, scoped, and burst throttling.

---

## Quick Start

The simplest way is the `@throttle_user` / `@throttle_anon` shortcut decorators:

```python
from django_matt.throttling import throttle_user, throttle_anon
from django_matt.core.controller import APIController
from django_matt.core.router import get, post

class SearchController(APIController):
    prefix = "/search"

    @get("/")
    @throttle_user(rate="100/hour")
    async def search(self, request):
        ...

    @post("/register")
    @throttle_anon(rate="5/hour")
    async def register(self, request):
        ...
```

---

## `@throttle` Decorator

Full control over throttle class and parameters:

```python
from django_matt.throttling import throttle, UserRateThrottle, AnonRateThrottle, ScopedRateThrottle

# Authenticated users by user ID; anonymous by IP
@throttle(UserRateThrottle, rate="1000/day")
async def api_endpoint(request):
    ...

# Anonymous only (by IP)
@throttle(AnonRateThrottle, rate="100/hour")
async def public_endpoint(request):
    ...

# Named scope (rate defined in settings)
@throttle(ScopedRateThrottle, scope="uploads")
async def upload(request):
    ...

# Simple rate string without specifying class
@throttle(rate="50/minute")
async def any_endpoint(request):
    ...

# Restrict to specific HTTP methods
@throttle(rate="10/minute", methods=["POST", "PUT"])
async def write_endpoint(request):
    ...
```

---

## Scoped Rate Limiting

Define rates per scope in settings, then reference them from any endpoint:

```python
# settings.py
THROTTLE_RATES = {
    "uploads": "10/hour",
    "search":  "30/minute",
    "ai":      "5/minute",
    "default": "1000/day",
}
```

```python
from django_matt.throttling import throttle, ScopedRateThrottle

@throttle(ScopedRateThrottle, scope="ai")
async def ai_endpoint(request):
    ...

@throttle(ScopedRateThrottle, scope="uploads")
async def upload(request):
    ...
```

---

## Burst Throttling

Allow short bursts while enforcing a sustained limit:

```python
from django_matt.throttling import throttle, BurstRateThrottle

@throttle(BurstRateThrottle, burst_rate="10/second", sustained_rate="200/minute")
async def hot_endpoint(request):
    ...
```

---

## Token Bucket (Advanced)

For fine-grained control with optional Rust acceleration:

```python
from django_matt.throttling import TokenBucketThrottle

bucket = TokenBucketThrottle(
    capacity=100,           # max tokens
    refill_per_second=10.0, # refill rate
)

allowed, remaining, reset_ms = bucket.check(request)
# or by arbitrary key (e.g. API key header)
allowed, remaining, reset_ms = bucket.check_key(request.headers.get("X-API-Key", ""))

if not allowed:
    return JsonResponse({"detail": "Rate limit exceeded"}, status=429)
```

---

## Class-Based Views (Mixin)

```python
from django_matt.throttling import ThrottlesMixin, UserRateThrottle

class MyController(APIController, ThrottlesMixin):
    throttle_classes = [UserRateThrottle]
    throttle_rates = {"default": "100/hour"}

    @get("/")
    async def list(self, request):
        self.check_throttles(request)  # raises ThrottleError if exceeded
        ...
```

---

## Global Throttling (Middleware)

Apply a baseline throttle to all requests:

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.throttling.ThrottleMiddleware",
]

THROTTLE_DEFAULT_RATE = "10000/day"
THROTTLE_BACKEND = "redis"  # "memory" (default) | "redis" | "django-cache"
```

---

## Storage Backends

### In-memory (development)

```python
from django_matt.throttling.backends import InMemoryBackend

backend = InMemoryBackend()
backend.cleanup_expired()  # prune old entries
```

### Redis (production)

```python
from django_matt.throttling.backends import RedisBackend

# From Django cache config
backend = RedisBackend.from_django_cache(cache_name="default")
```

```python
# settings.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    }
}

THROTTLE_BACKEND = "redis"
```

### Django cache (any backend)

```python
from django_matt.throttling.backends import DjangoCacheBackend

backend = DjangoCacheBackend(cache_name="throttle")
```

---

## Rate Formats

All throttle classes accept these rate string formats:

| String | Meaning |
|--------|---------|
| `"100/s"` | 100 per second |
| `"100/m"` | 100 per minute |
| `"100/h"` / `"100/hour"` | 100 per hour |
| `"100/d"` / `"100/day"` | 100 per day |

---

## Response Headers

When throttling is active, responses include standard rate-limit headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1710003600
Retry-After: 30            ← only on 429 responses
```

---

## Error Handling

```python
from django_matt.throttling import ThrottleError

@get("/")
async def endpoint(self, request):
    try:
        self.check_throttles(request)
    except ThrottleError as exc:
        return JsonResponse(
            {"detail": str(exc), "retry_after": exc.wait},
            status=429,
            headers=exc.headers,
        )
```

---

## Testing

Bypass throttling in tests with the context manager:

```python
from django_matt.throttling import bypass_throttle

def test_bulk_insert(client):
    with bypass_throttle():
        for _ in range(200):
            client.post("/api/items/", data={...})
```

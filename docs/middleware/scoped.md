# Route-Scoped Middleware

Django Matt provides route-scoped middleware that runs around individual handler methods rather than the entire Django request/response cycle. This is lighter than global Django middleware and can be applied per-controller or per-route.

## Overview

```
Global Django Middleware (entire request lifecycle)
  -> Controller dispatch
    -> Route-scoped middleware (per-handler)
      -> Your handler function
    <- process_response (reverse order)
  <- ...
```

Route middleware uses the onion model: `process_request` hooks run top-to-bottom, `process_response` hooks run bottom-to-top.

## RouteMiddleware Base Class

Subclass `RouteMiddleware` and override any of the three hooks:

```python
from django_matt.middleware.scoped import RouteMiddleware
from django.http import HttpRequest, HttpResponse


class TimingMiddleware(RouteMiddleware):
    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        import time
        request._start_time = time.perf_counter()
        return None  # continue to handler

    async def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        import time
        elapsed = time.perf_counter() - request._start_time
        response["X-Response-Time"] = f"{elapsed:.3f}s"
        return response

    async def process_exception(
        self, request: HttpRequest, exc: Exception
    ) -> HttpResponse | None:
        return None  # re-raise the exception
```

### Hook Behavior

| Hook | Return `None` | Return `HttpResponse` |
|------|---------------|----------------------|
| `process_request` | Continue to next middleware / handler | Short-circuit, skip handler |
| `process_response` | N/A (must return response) | Replace the response |
| `process_exception` | Re-raise the exception | Use this response instead |

## Applying Middleware to Controllers

Set `middleware_classes` on your controller to apply middleware to all routes:

```python
@api.controller("/products", tags=["Products"])
class ProductController(APIController):
    middleware_classes = [TimingMiddleware, ScopedRateLimitMiddleware]

    @api.get("/")
    async def list_products(self, request):
        ...

    @api.post("/")
    async def create_product(self, request, data: ProductSchema):
        ...
```

## @use_middleware Decorator

Add middleware to a specific route method:

```python
from django_matt.middleware.scoped import use_middleware


@api.controller("/users", tags=["Users"])
class UserController(APIController):

    @api.get("/")
    async def list_users(self, request):
        ...  # no extra middleware

    @api.post("/import")
    @use_middleware(ScopedRateLimitMiddleware)
    async def import_users(self, request, data: ImportSchema):
        ...  # rate limited
```

Middleware added via `@use_middleware` runs after controller-level middleware.

## @skip_middleware Decorator

Exclude specific middleware from a route that would otherwise inherit it from the controller:

```python
from django_matt.middleware.scoped import skip_middleware


@api.controller("/admin", tags=["Admin"])
class AdminController(APIController):
    middleware_classes = [ScopedAuthMiddleware, ScopedRateLimitMiddleware]

    @api.get("/dashboard")
    async def dashboard(self, request):
        ...  # both middlewares apply

    @api.get("/health")
    @skip_middleware(ScopedAuthMiddleware, ScopedRateLimitMiddleware)
    async def health(self, request):
        ...  # no middleware
```

## Built-in Middleware

### ScopedCorsMiddleware

CORS headers for specific routes. Handles OPTIONS preflight requests.

```python
from django_matt.middleware.builtins import ScopedCorsMiddleware

class MyController(APIController):
    middleware_classes = [
        ScopedCorsMiddleware(
            allowed_origins=["https://myapp.com"],
            allowed_methods=["GET", "POST"],
            allowed_headers=["Content-Type", "Authorization"],
            max_age=86400,
        ),
    ]
```

Defaults: `allowed_origins=["*"]`, all standard methods, `Content-Type` + `Authorization` headers.

### ScopedRateLimitMiddleware

In-memory rate limiting per client IP + path. Returns 429 when the limit is exceeded.

```python
from django_matt.middleware.builtins import ScopedRateLimitMiddleware

class MyController(APIController):
    middleware_classes = [
        ScopedRateLimitMiddleware(max_requests=60, window_seconds=60),
    ]
```

Uses a module-level dict for storage. Suitable for single-process dev servers. For production, back with Redis.

### ScopedCacheMiddleware

Response caching for GET requests. In-memory with TTL.

```python
from django_matt.middleware.builtins import ScopedCacheMiddleware

class MyController(APIController):
    middleware_classes = [
        ScopedCacheMiddleware(ttl_seconds=300),
    ]
```

Cache key is based on the request method and full path (including query string). Only caches 2xx GET responses.

### ScopedAuthMiddleware

Require an authenticated user. Returns 401 if `request.user` is anonymous or missing.

```python
from django_matt.middleware.builtins import ScopedAuthMiddleware

class MyController(APIController):
    middleware_classes = [ScopedAuthMiddleware()]
```

## MiddlewareStack Internals

The `MiddlewareStack` is resolved once at controller init time per method (not per request). The resolution logic:

1. Start with controller-level `middleware_classes`
2. Append classes from `@use_middleware` on the method
3. Remove classes from `@skip_middleware` on the method
4. Instantiate each class once

```python
from django_matt.middleware.scoped import MiddlewareStack

# Typically you don't construct this directly — it's built automatically
stack = MiddlewareStack([TimingMiddleware(), ScopedRateLimitMiddleware()])
response = await stack.execute(request, handler, *args, **kwargs)
```

## Writing Custom Middleware

```python
from django_matt.middleware.scoped import RouteMiddleware
from django.http import HttpRequest, HttpResponse, JsonResponse
import logging

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(RouteMiddleware):
    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        logger.info(f"{request.method} {request.path}")
        return None

    async def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        logger.info(f"{request.method} {request.path} -> {response.status_code}")
        return response


class MaintenanceModeMiddleware(RouteMiddleware):
    def __init__(self, *, enabled: bool = False):
        self.enabled = enabled

    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        if self.enabled:
            return JsonResponse(
                {"detail": "Service under maintenance"},
                status=503,
            )
        return None
```

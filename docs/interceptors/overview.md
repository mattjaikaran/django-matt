# Interceptors

Interceptors are composable, ordered hooks that wrap request handling with `before_request`, `after_response`, and `on_error` lifecycle methods. They sit between middleware and decorators in the execution model: more granular than middleware (per-route or per-controller), more structured than decorators (ordered pipeline with error propagation).

## When to Use Interceptors

| Mechanism | Scope | Use Case |
|-----------|-------|----------|
| **Middleware** | Global, every request | Auth, CORS, security headers |
| **Interceptors** | Per-route or per-controller | Logging, caching, rate limiting, transforms |
| **Decorators** | Single endpoint | Permission checks, input validation |

Use interceptors when you need a reusable pipeline of cross-cutting concerns applied to specific routes or controllers, with guaranteed execution order and error isolation.

## Quick Start

```python
from django_matt.interceptors import (
    Interceptor,
    InterceptorChain,
    LoggingInterceptor,
    TimingInterceptor,
    intercept,
    intercept_controller,
)

# Apply to a single endpoint
@api.get("/items")
@intercept(TimingInterceptor(), LoggingInterceptor())
async def list_items(request):
    return {"items": []}

# Apply to an entire controller
@intercept_controller(TimingInterceptor(), LoggingInterceptor(log_body=True))
@api.controller("/products", tags=["Products"])
class ProductController(APIController):
    @api.get("/")
    async def list_products(self, request):
        ...
```

## Base Interceptor Class

Subclass `Interceptor` to create custom interceptors. All lifecycle methods are async.

```python
from django_matt.interceptors import Interceptor

class AuditInterceptor(Interceptor):
    order: int = 10  # lower runs first in before_request, last in after_response

    def enabled(self, request) -> bool:
        """Return False to skip this interceptor for a request."""
        return request.method != "OPTIONS"

    async def before_request(self, request, **kwargs):
        """Called before the handler. Return HttpResponse to short-circuit."""
        request._audit_start = time.monotonic()
        return None  # continue pipeline

    async def after_response(self, request, response, **kwargs):
        """Called after the handler (reverse order). Must return a response."""
        duration = time.monotonic() - request._audit_start
        await log_audit(request, response, duration)
        return response

    async def on_error(self, request, exc, **kwargs):
        """Called on handler exception (reverse order). Return HttpResponse to handle it."""
        await log_error(request, exc)
        return None  # let exception propagate
```

### Lifecycle

1. **`enabled(request)`** -- sync check; return `False` to skip this interceptor entirely
2. **`before_request(request, **kwargs)`** -- runs in order. Return `None` to continue, or `HttpResponse` to short-circuit (after_response still runs for already-executed interceptors)
3. **Handler executes**
4. **`after_response(request, response, **kwargs)`** -- runs in reverse order. Must return an `HttpResponse`
5. **`on_error(request, exc, **kwargs)`** -- runs in reverse order on exception. Return `HttpResponse` to handle it; return `None` to let the next interceptor (or the framework) handle it

### Ordering

The `order` class attribute controls execution priority. Lower values run first in `before_request`, last in `after_response`/`on_error` (reverse). Built-in order values:

| Interceptor | Order |
|-------------|-------|
| `LoggingInterceptor` | -100 |
| `RateLimitInterceptor` | -95 |
| `TimingInterceptor` | -90 |
| `CachingInterceptor` | -80 |
| `TransformInterceptor` | 0 |
| `RetryInterceptor` | 50 |

## InterceptorChain

`InterceptorChain` manages an ordered pipeline of interceptors and orchestrates execution.

```python
from django_matt.interceptors import InterceptorChain, TimingInterceptor, LoggingInterceptor

chain = InterceptorChain([TimingInterceptor(), LoggingInterceptor()])

# Add more interceptors (auto-sorted by order)
chain.add(CachingInterceptor(ttl=30))

# Execute the chain around a handler
response = await chain.execute(request, handler, *args, **kwargs)

# Merge two chains
combined = chain.merge(other_chain)

# Introspect
print(len(chain))              # number of interceptors
print(chain.interceptors)      # sorted list (copy)
```

### Short-Circuit Behavior

When `before_request` returns an `HttpResponse`, the chain stops calling further interceptors. It then runs `after_response` in reverse for all interceptors that already executed (including the one that short-circuited), ensuring cleanup always runs.

### Error Handling

When the handler raises an exception, `on_error` runs in reverse order. The first interceptor that returns an `HttpResponse` handles the error -- `after_response` then runs for all active interceptors. If no interceptor handles it, the exception re-raises.

## Decorators

### `@intercept(*interceptors)`

Apply interceptors to a single async view or controller method.

```python
from django_matt.interceptors import intercept, CachingInterceptor

@api.get("/cached-data")
@intercept(CachingInterceptor(ttl=120))
async def cached_data(request):
    return await expensive_query()
```

The wrapped function exposes its chain via `fn._interceptors` for introspection.

### `@intercept_controller(*interceptors)`

Class decorator that attaches interceptors to all methods on a controller. Merges with any existing `interceptors` attribute on the class.

```python
from django_matt.interceptors import intercept_controller, LoggingInterceptor, TimingInterceptor

@intercept_controller(LoggingInterceptor(), TimingInterceptor())
@api.controller("/analytics", tags=["Analytics"])
class AnalyticsController(APIController):
    @api.get("/dashboard")
    async def dashboard(self, request):
        ...

    @api.get("/reports")
    async def reports(self, request):
        ...
```

## Built-in Interceptors

### LoggingInterceptor

Structured request/response logging with configurable verbosity.

```python
LoggingInterceptor(
    log_body=False,          # log request body (JSON parsed)
    log_headers=False,       # log request headers
    logger_name=None,        # custom logger name (default: django_matt.interceptors)
)
```

Logs `request_start` on entry with method/path (plus headers/body if enabled), `request_end` on exit with status and duration_ms, and `request_error` with full traceback on exception.

### TimingInterceptor

Adds an `X-Interceptor-Time` response header with handler duration.

```python
TimingInterceptor(
    header_name="X-Interceptor-Time",  # custom header name
)
```

### CachingInterceptor

In-memory response cache keyed by method + full path (including query string). Adds `X-Cache: HIT` or `X-Cache: MISS` headers.

```python
CachingInterceptor(
    ttl=60.0,                # cache TTL in seconds
    methods={"GET"},         # HTTP methods to cache
)
```

Only caches 2xx responses. Cache key is an MD5 hash of `{method}:{full_path}`.

### TransformInterceptor

Apply sync callables to transform request body and/or response content. Works with JSON payloads.

```python
def snake_to_camel(data):
    # transform keys
    return transformed

def add_metadata(data):
    data["_version"] = "v2"
    return data

TransformInterceptor(
    request_transform=snake_to_camel,   # transform inbound JSON
    response_transform=add_metadata,     # transform outbound JSON
)
```

### RetryInterceptor

Tracks retry count on the request. Retry logic is managed by the chain caller.

```python
RetryInterceptor(
    max_retries=3,
    retry_on=(TimeoutError, ConnectionError),
)
```

### RateLimitInterceptor

In-memory sliding window rate limiter, keyed by IP + path.

```python
RateLimitInterceptor(
    max_requests=100,        # requests per window
    window=60.0,             # window in seconds
    key_func=None,           # custom key function(request) -> str
)
```

Returns `429 Rate limit exceeded` when the limit is hit. Default key uses `X-Forwarded-For` or `REMOTE_ADDR`.

## Common Patterns

### Composing Multiple Interceptors

```python
# API-wide defaults
api_interceptors = InterceptorChain([
    RateLimitInterceptor(max_requests=1000, window=60),
    TimingInterceptor(),
    LoggingInterceptor(),
])

# Route-specific additions
cached_chain = api_interceptors.merge(
    InterceptorChain([CachingInterceptor(ttl=300)])
)
```

### Conditional Interceptors

```python
class AdminOnlyLogging(LoggingInterceptor):
    def enabled(self, request) -> bool:
        return getattr(request, "user", None) and request.user.is_staff
```

### Custom Error Handler

```python
class SentryInterceptor(Interceptor):
    order = 100  # run last in on_error

    async def on_error(self, request, exc, **kwargs):
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
        return None  # don't swallow the error
```

## Best Practices

1. **Keep interceptors focused** -- one responsibility per interceptor
2. **Use `order` intentionally** -- rate limiting should run before caching, caching before transforms
3. **Always return the response** from `after_response` -- forgetting causes silent failures
4. **Don't block the event loop** -- interceptors are async; offload CPU-heavy transforms
5. **Use `enabled()` for conditional logic** instead of early returns in `before_request`
6. **Prefer `@intercept_controller`** for cross-cutting concerns that apply to all methods on a controller

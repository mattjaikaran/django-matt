# Interceptor Recipes

Route-scoped middleware for before/after hooks on individual endpoints or controllers.

## Request Logging with Correlation IDs

```python
import uuid
from typing import Any

from django.http import HttpRequest, HttpResponse

from django_matt.interceptors import Interceptor, intercept


class CorrelationIDInterceptor(Interceptor):
    order = -100  # run first

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        correlation_id = request.headers.get(
            "X-Correlation-ID", str(uuid.uuid4())
        )
        request._correlation_id = correlation_id  # type: ignore[attr-defined]
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs: Any
    ) -> HttpResponse:
        cid = getattr(request, "_correlation_id", "")
        response["X-Correlation-ID"] = cid
        return response


@intercept(CorrelationIDInterceptor())
async def my_view(request):
    cid = request._correlation_id
    return JsonResponse({"correlation_id": cid})
```

## Response Caching with TTL

```python
from django_matt.interceptors import CachingInterceptor, intercept

# Cache GET responses for 30 seconds
cache = CachingInterceptor(ttl=30.0, methods={"GET"})


@intercept(cache)
async def product_list(request):
    # First call: X-Cache: MISS
    # Subsequent calls within 30s: X-Cache: HIT
    products = await Product.objects.all().avalues_list("id", "name")
    return JsonResponse({"products": list(products)})
```

## API Rate Limiting per User

```python
from django.http import HttpRequest

from django_matt.interceptors import RateLimitInterceptor, intercept


def user_key(request: HttpRequest) -> str:
    """Rate limit by authenticated user, fall back to IP."""
    if hasattr(request, "user") and request.user.is_authenticated:
        return str(request.user.pk)
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


# 60 requests per minute per user
rate_limit = RateLimitInterceptor(
    max_requests=60,
    window=60.0,
    key_func=user_key,
)


@intercept(rate_limit)
async def create_order(request):
    # Returns 429 {"detail": "Rate limit exceeded"} when over limit
    ...
```

## Request/Response Transformation (camelCase <-> snake_case)

```python
import re

from django_matt.interceptors import TransformInterceptor, intercept


def camel_to_snake(data: dict) -> dict:
    """Convert camelCase keys to snake_case."""
    def convert_key(key: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()

    if isinstance(data, dict):
        return {convert_key(k): camel_to_snake(v) for k, v in data.items()}
    if isinstance(data, list):
        return [camel_to_snake(item) for item in data]
    return data


def snake_to_camel(data: dict) -> dict:
    """Convert snake_case keys to camelCase."""
    def convert_key(key: str) -> str:
        parts = key.split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])

    if isinstance(data, dict):
        return {convert_key(k): snake_to_camel(v) for k, v in data.items()}
    if isinstance(data, list):
        return [snake_to_camel(item) for item in data]
    return data


# Incoming camelCase -> snake_case, outgoing snake_case -> camelCase
transform = TransformInterceptor(
    request_transform=camel_to_snake,
    response_transform=snake_to_camel,
)


@intercept(transform)
async def update_user(request):
    # Client sends {"firstName": "Matt"} -> handler sees {"first_name": "Matt"}
    # Handler returns {"first_name": "Matt"} -> client sees {"firstName": "Matt"}
    ...
```

## Retry with Exponential Backoff

```python
import asyncio
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse

from django_matt.interceptors import Interceptor, intercept


class ExponentialRetryInterceptor(Interceptor):
    order = 50

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.1,
        retry_on: tuple[type[Exception], ...] = (TimeoutError, ConnectionError),
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.retry_on = retry_on

    async def on_error(
        self, request: HttpRequest, exc: Exception, **kwargs: Any
    ) -> HttpResponse | None:
        if not isinstance(exc, self.retry_on):
            return None

        attempt = getattr(request, "_retry_attempt", 0)
        if attempt >= self.max_retries:
            return JsonResponse(
                {"detail": f"Failed after {self.max_retries} retries"},
                status=503,
            )

        delay = self.base_delay * (2 ** attempt)
        await asyncio.sleep(delay)
        request._retry_attempt = attempt + 1  # type: ignore[attr-defined]
        return None  # let the chain re-raise, caller handles retry


@intercept(ExponentialRetryInterceptor(max_retries=3, base_delay=0.2))
async def call_external_api(request):
    ...
```

## Composing Multiple Interceptors

```python
from django_matt.interceptors import (
    CachingInterceptor,
    InterceptorChain,
    LoggingInterceptor,
    RateLimitInterceptor,
    TimingInterceptor,
    intercept,
    intercept_controller,
)

# Option 1: stack decorators (order determined by Interceptor.order)
@intercept(
    LoggingInterceptor(log_body=True),
    TimingInterceptor(),
    RateLimitInterceptor(max_requests=100, window=60.0),
    CachingInterceptor(ttl=15.0),
)
async def dashboard(request):
    ...


# Option 2: build a chain manually and merge
api_chain = InterceptorChain([
    LoggingInterceptor(),
    TimingInterceptor(),
])
cache_chain = InterceptorChain([
    CachingInterceptor(ttl=60.0),
])
combined = api_chain.merge(cache_chain)
# combined has all 3 interceptors, sorted by .order


# Option 3: apply to an entire controller class
@intercept_controller(
    LoggingInterceptor(log_headers=True),
    TimingInterceptor(header_name="X-API-Time"),
)
class ProductController:
    ...
```

## Timing and Metrics Collection

```python
import logging
import time
from typing import Any

from django.http import HttpRequest, HttpResponse

from django_matt.interceptors import Interceptor, intercept

logger = logging.getLogger("api.metrics")


class MetricsInterceptor(Interceptor):
    """Collect per-endpoint timing metrics and log slow requests."""

    order = -90

    def __init__(self, slow_threshold_ms: float = 500.0) -> None:
        self.slow_threshold_ms = slow_threshold_ms
        self.endpoint_times: dict[str, list[float]] = {}

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        request._metrics_start = time.monotonic()  # type: ignore[attr-defined]
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs: Any
    ) -> HttpResponse:
        start = getattr(request, "_metrics_start", None)
        if start is None:
            return response

        duration_ms = (time.monotonic() - start) * 1000
        endpoint = f"{request.method} {request.path}"

        self.endpoint_times.setdefault(endpoint, []).append(duration_ms)
        response["X-Response-Time"] = f"{duration_ms:.1f}ms"

        if duration_ms > self.slow_threshold_ms:
            logger.warning(
                "slow_request",
                extra={
                    "endpoint": endpoint,
                    "duration_ms": f"{duration_ms:.1f}",
                    "status": response.status_code,
                },
            )
        return response

    def get_stats(self, endpoint: str) -> dict[str, float]:
        times = self.endpoint_times.get(endpoint, [])
        if not times:
            return {"count": 0, "avg_ms": 0, "max_ms": 0}
        return {
            "count": len(times),
            "avg_ms": sum(times) / len(times),
            "max_ms": max(times),
        }


metrics = MetricsInterceptor(slow_threshold_ms=200.0)


@intercept(metrics)
async def slow_endpoint(request):
    ...
```

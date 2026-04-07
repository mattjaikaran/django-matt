# Performance Recipes

Auto-instrumentation, custom spans, metrics, slim mode, and query optimization.

## Auto-Instrumentation Setup (Zero-Config)

```python
# In your AppConfig.ready() or startup script
from django_matt.observability import setup_observability

# One call instruments controllers, DB queries, cache, and HTTP clients
instrumentor = setup_observability(auto=True)

# Or configure via settings.py (setup_observability reads these)
# settings.py
DJANGO_MATT_OBSERVABILITY = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "SERVICE_MODULES": ["myapp.services", "myapp.tasks"],
    "EXPORTERS": [
        {"type": "console", "color": True},  # dev
        # {"type": "json"},                   # production
        # {"type": "opentelemetry", "service_name": "myapp"},
    ],
}
```

## Custom Spans for Business Operations

```python
from django_matt.observability import span, aspan, traced


# Sync context manager
def process_payment(order_id: int) -> bool:
    with span("payment.process", tags={"order_id": order_id}) as s:
        result = gateway.charge(order_id)
        s.set_tag("gateway", "stripe")
        s.set_tag("amount", result.amount)
        return result.success


# Async context manager
async def fetch_recommendations(user_id: int) -> list:
    async with aspan("ml.recommendations", tags={"user_id": user_id}) as s:
        recs = await ml_service.get_recommendations(user_id)
        s.set_tag("count", len(recs))
        return recs


# Decorator — auto-names the span from the function
@traced("order.fulfill")
async def fulfill_order(order_id: int):
    ...


# Spans nest automatically via context vars
async def checkout(request):
    async with aspan("checkout.flow") as parent:
        async with aspan("checkout.validate"):
            await validate_cart(request)
        async with aspan("checkout.charge"):
            await process_payment(request)
        async with aspan("checkout.confirm"):
            await send_confirmation(request)
        # parent.children contains all 3 child spans
```

## Span Listeners for Export

```python
from django_matt.observability import Span, add_span_listener, remove_span_listener


def export_to_datadog(span: Span):
    """Called when a root span finishes."""
    data = span.to_dict()
    # data includes: name, duration_ms, status, tags, children, error
    datadog_client.send_trace(data)


add_span_listener(export_to_datadog)

# Remove when done
remove_span_listener(export_to_datadog)
```

## Metrics Collection and Export

```python
from django_matt.observability import (
    MetricsManager,
    metrics_manager,
    record_request,
    timed,
    counted,
)

# Use built-in convenience functions
record_request(method="GET", endpoint="/api/users", status=200, duration=0.045)

# Create custom metrics
order_counter = metrics_manager.counter(
    "orders_total",
    "Total orders placed",
    labelnames=["payment_method", "status"],
)
order_counter.labels(payment_method="stripe", status="success").inc()

latency = metrics_manager.histogram(
    "external_api_duration_seconds",
    "External API call latency",
    labelnames=["service"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)
latency.labels(service="stripe").observe(0.234)

active_users = metrics_manager.gauge(
    "active_users",
    "Currently active users",
)
active_users.inc()


# Decorator shortcuts
@timed(name="email_send_duration_seconds", labels={"provider": "sendgrid"})
async def send_email(to: str, subject: str):
    ...


@counted(name="webhook_received_total", labels={"source": "stripe"})
async def handle_webhook(request):
    ...


# Expose via endpoint (auto-included with observability_urlpatterns)
# GET /_matt/metrics -> Prometheus text format
```

## Slim Mode for Faster Startup

```python
# settings.py — control which modules load at startup
DJANGO_MATT = {
    "SLIM_MODE": {
        "mode": "slim",           # full | slim | minimal | auto
        "enabled_modules": [      # only load these (slim mode)
            "auth",
            "views",
            "observability",
        ],
        "disabled_modules": [],   # explicit blocklist (any mode)
        "lazy_imports": True,     # defer heavy module imports
    },
}

# Modes:
# "full"    — everything loaded (default, backwards-compatible)
# "slim"    — only explicitly enabled modules load
# "minimal" — only core + auth + error handling
# "auto"    — detect from settings which modules are configured
```

## Lazy Module Loading

```python
from django_matt.loader import DeferredLoader, LazyModuleProxy

# Heavy modules are loaded on first access, not at import time
# These are defined in django_matt.loader.HEAVY_MODULES:
#   billing, ai, ml, graphql, websockets, analytics,
#   experiments, notifications, email, messaging, files, tasks

# Check if a module is enabled before importing
from django_matt.slim import is_module_enabled

if is_module_enabled("billing"):
    from django_matt.billing import BillingController

# The ModuleRegistry tracks active modules
from django_matt.slim import ModuleRegistry

registry = ModuleRegistry(mode="auto")
registry.activate("billing", "analytics")
print(registry.active_modules)      # frozenset({'core', 'auth', 'billing', ...})
print(registry.get_active_middleware())  # only middleware for active modules
```

## Query Optimization with select_related/prefetch_related

```python
# django_matt views auto-detect FK/M2M from your schema and optimize queries.
# For manual optimization in controllers:

from django.db.models import Prefetch


async def list_orders(request):
    # BAD: N+1 queries — each order.customer triggers a DB hit
    orders = [o async for o in Order.objects.all().aiterator()]

    # GOOD: select_related for FK/OneToOne (JOIN)
    orders = Order.objects.select_related("customer", "shipping_address")

    # GOOD: prefetch_related for M2M/reverse FK (separate query)
    orders = Order.objects.prefetch_related(
        "items",
        "items__product",
        Prefetch(
            "items__product__categories",
            queryset=Category.objects.only("id", "name"),
        ),
    )

    # Combine both
    qs = (
        Order.objects
        .select_related("customer")
        .prefetch_related("items", "items__product")
        .only("id", "total", "status", "customer__name", "customer__email")
        .order_by("-created_at")[:50]
    )

    data = [
        {
            "id": o.id,
            "total": str(o.total),
            "customer": o.customer.name,
            "items": [{"sku": i.product.sku} for i in o.items.all()],
        }
        async for o in qs.aiterator()
    ]
    return JsonResponse(data, safe=False)
```

## Response Caching Strategies

```python
from django.core.cache import cache
from django.http import JsonResponse

import orjson


# Pattern 1: Cache-aside with TTL
async def get_dashboard_stats(request):
    cache_key = f"dashboard:{request.user.pk}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(orjson.loads(cached))

    stats = await compute_stats(request.user)
    cache.set(cache_key, orjson.dumps(stats), timeout=300)
    return JsonResponse(stats)


# Pattern 2: Interceptor-based caching (per-route)
from django_matt.interceptors import CachingInterceptor, intercept

@intercept(CachingInterceptor(ttl=60.0))
async def product_catalog(request):
    ...


# Pattern 3: CQRS query caching (per-query-type)
from django_matt.cqrs import CachingMiddleware, get_query_bus

query_bus = get_query_bus()
query_bus.use(CachingMiddleware(ttl=120))


# Pattern 4: HTTP cache headers
async def static_content(request):
    data = await get_content()
    response = JsonResponse(data)
    response["Cache-Control"] = "public, max-age=3600"
    response["ETag"] = hashlib.md5(response.content).hexdigest()
    return response
```

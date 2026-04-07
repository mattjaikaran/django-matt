# Async Patterns

django-matt is async-first. All controllers, views, and hooks are `async def` by default. This guide covers the patterns, escape hatches, and pitfalls you need to know.

## Why Async-First

1. **I/O concurrency** — async handlers can serve other requests while waiting on database queries, HTTP calls, or file I/O
2. **WebSocket support** — ASGI is required for WebSocket consumers
3. **Streaming** — SSE and NDJSON streaming require async responses
4. **Performance** — under concurrent load, async handlers significantly outperform sync handlers for I/O-bound work

django-matt targets ASGI deployment:

```bash
gunicorn config.asgi:application --worker-class uvicorn.workers.UvicornWorker
```

## Async Controllers and Views

All handler methods should be `async def`:

```python
@api.controller("/users", tags=["Users"])
class UserController(APIController):
    @api.get("/")
    async def list_users(self, request):
        users = [u async for u in User.objects.all()]
        return {"items": users}

    @api.post("/")
    async def create_user(self, request, data: UserCreateSchema) -> UserSchema:
        user = await User.objects.acreate(**data.model_dump())
        return user
```

ViewSet handlers are always async:

```python
class ProductViewSet(APIViewSet):
    api = api
    model = Product
    list = ListView()      # internally calls async handle()
    create = CreateView()  # internally calls async handle()
```

## Django ORM Async Methods

Django 4.1+ provides async ORM methods. Use these instead of their sync counterparts:

| Sync (blocks event loop) | Async (safe) |
|--------------------------|--------------|
| `Model.objects.get()` | `Model.objects.aget()` |
| `Model.objects.create()` | `Model.objects.acreate()` |
| `Model.objects.filter().count()` | `await qs.acount()` |
| `Model.objects.filter().exists()` | `await qs.aexists()` |
| `Model.objects.filter().first()` | `await qs.afirst()` |
| `Model.objects.filter().update()` | `await qs.aupdate()` |
| `Model.objects.filter().delete()` | `await qs.adelete()` |
| `instance.save()` | `await instance.asave()` |
| `instance.delete()` | `await instance.adelete()` |
| `list(queryset)` | `[obj async for obj in queryset]` |

```python
# Correct async usage
user = await User.objects.aget(pk=user_id)
user.name = "New Name"
await user.asave()

# Async iteration over querysets
active_users = [u async for u in User.objects.filter(is_active=True)]
```

## sync_to_async for ORM Fallbacks

Some Django ORM operations do not have async equivalents yet. Wrap them with `sync_to_async`:

```python
from asgiref.sync import sync_to_async

# Aggregation
total = await sync_to_async(
    lambda: Order.objects.filter(user=user).aggregate(Sum("amount"))["amount__sum"]
)()

# Complex queries without async support
@sync_to_async
def get_complex_report(org_id):
    return list(
        Order.objects
        .filter(organization_id=org_id)
        .values("status")
        .annotate(count=Count("id"), total=Sum("amount"))
    )

report = await get_complex_report(org.id)
```

### Model full_clean()

The `validate_model` option on ViewSets wraps `full_clean()` in `sync_to_async`:

```python
class StrictProductViewSet(APIViewSet):
    validate_model = True  # auto-calls full_clean() via sync_to_async before save
```

Internally:

```python
async def _validate_model_instance(self, instance):
    if self._should_validate_model():
        await sync_to_async(instance.full_clean)()
```

## Concurrent Operations with asyncio.gather

When you need multiple independent I/O operations, run them concurrently:

```python
import asyncio

async def get_dashboard(self, request):
    user = request.user

    # Run three independent queries concurrently
    orders, notifications, stats = await asyncio.gather(
        Order.objects.filter(user=user).acount(),
        Notification.objects.filter(user=user, read=False).acount(),
        sync_to_async(get_user_stats)(user.id),
    )

    return {
        "order_count": orders,
        "unread_notifications": notifications,
        "stats": stats,
    }
```

### Parallel External API Calls

```python
import httpx

async def enrich_user(self, request, user_id: int):
    async with httpx.AsyncClient() as client:
        github_task = client.get(f"https://api.github.com/users/{username}")
        twitter_task = client.get(f"https://api.twitter.com/users/{username}")

        github_resp, twitter_resp = await asyncio.gather(
            github_task, twitter_task, return_exceptions=True
        )

    return {
        "github": github_resp.json() if not isinstance(github_resp, Exception) else None,
        "twitter": twitter_resp.json() if not isinstance(twitter_resp, Exception) else None,
    }
```

## Lifecycle Hooks are Async

All ViewSet lifecycle hooks must be async:

```python
class OrderViewSet(APIViewSet):
    async def before_create(self, request, data):
        # Validate stock availability
        product = await Product.objects.aget(pk=data["product_id"])
        if product.stock < data["quantity"]:
            raise ValueError("Insufficient stock")
        return data

    async def after_create(self, request, instance):
        # Send notification asynchronously
        await send_order_notification(instance)
        return instance
```

Decorator-based hooks:

```python
from django_matt.views.hooks import before_create

@before_create(OrderViewSet)
async def validate_order(context, data):
    ...
    return data
```

## Interceptors are Async

```python
from django_matt.interceptors import Interceptor

class TimingInterceptor(Interceptor):
    async def before_request(self, request, **kwargs):
        request._start_time = time.monotonic()
        return None

    async def after_response(self, request, response, **kwargs):
        duration = time.monotonic() - request._start_time
        response["Server-Timing"] = f"total;dur={duration * 1000:.1f}"
        return response
```

## Common Pitfalls

### 1. Calling Sync ORM in Async Context

This blocks the event loop and degrades performance for all concurrent requests:

```python
# BAD — blocks the event loop
async def list_users(self, request):
    users = list(User.objects.all())  # sync iteration!

# GOOD
async def list_users(self, request):
    users = [u async for u in User.objects.all()]
```

### 2. Forgetting await

```python
# BAD — returns a coroutine object, not the user
async def get_user(self, request, id: int):
    return User.objects.aget(pk=id)  # missing await!

# GOOD
async def get_user(self, request, id: int):
    return await User.objects.aget(pk=id)
```

### 3. Using sync_to_async Unnecessarily

If Django provides an async method, use it directly:

```python
# UNNECESSARY — Django has aget()
user = await sync_to_async(User.objects.get)(pk=id)

# BETTER
user = await User.objects.aget(pk=id)
```

### 4. Shared Mutable State

Async handlers can run concurrently. Do not modify shared mutable state without protection:

```python
# BAD — race condition
_cache = {}

async def get_or_create(self, request, key: str):
    if key not in _cache:
        _cache[key] = await expensive_computation(key)  # two requests can race here
    return _cache[key]

# GOOD — use asyncio.Lock or Django's cache framework
_lock = asyncio.Lock()

async def get_or_create(self, request, key: str):
    async with _lock:
        if key not in _cache:
            _cache[key] = await expensive_computation(key)
    return _cache[key]
```

### 5. Blocking in sync_to_async(thread_sensitive=True)

By default, `sync_to_async` uses `thread_sensitive=True`, which runs the function in the main thread. For CPU-bound work, use `thread_sensitive=False` to run in a thread pool:

```python
# CPU-bound work — use thread pool
@sync_to_async(thread_sensitive=False)
def compute_report(data):
    # heavy computation
    return result
```

## Testing Async Code

Use `pytest-asyncio` for async tests:

```python
import pytest

@pytest.mark.asyncio
async def test_create_user(async_client):
    response = await async_client.post("/api/users/", json={
        "username": "testuser",
        "email": "test@example.com",
    })
    assert response.status_code == 201
```

django-matt's `AsyncAPITestClient` handles authentication and request scoping automatically.

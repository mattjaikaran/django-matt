# Async Views and Handlers

Django Matt is designed with async-first principles. This guide covers how to leverage async views for better performance and concurrency.

## Why Async?

Async views provide significant benefits:

- **Higher Concurrency**: Handle more simultaneous requests
- **Better I/O Utilization**: Don't block on database/network calls
- **Lower Memory**: Share event loop instead of thread-per-request
- **Natural for Modern APIs**: WebSockets, streaming, real-time

## Basic Async Views

### Defining Async Views

```python
from django_matt import MattAPI

api = MattAPI()

@api.get("/users")
async def list_users(request):
    users = [u async for u in User.objects.all()]
    return users

@api.post("/users")
async def create_user(request, data: UserCreate):
    user = await User.objects.create(**data.model_dump())
    return user
```

### Async vs Sync Performance

| Scenario | Sync | Async | Improvement |
|----------|------|-------|-------------|
| 100 concurrent requests | 100 threads | 1 event loop | 10-50x memory |
| I/O-bound operations | Blocked | Non-blocking | 2-5x throughput |
| Database queries | Sequential | Concurrent | 2-10x speed |

## Async Database Operations

### Using Django ORM Async

Django 4.1+ supports async ORM operations:

```python
# Async queries
users = await User.objects.filter(active=True).all()
user = await User.objects.aget(id=1)
count = await User.objects.acount()

# Async create/update/delete
user = await User.objects.acreate(name="John")
await User.objects.filter(id=1).aupdate(active=False)
await User.objects.filter(id=1).adelete()

# Async aggregations
from django.db.models import Count, Sum
stats = await Order.objects.aaggregate(total=Sum('amount'))
```

### Async Iteration

```python
# Async iteration over queryset
async for user in User.objects.filter(active=True):
    await process_user(user)
```

### Using sync_to_async

For sync database operations:

```python
from asgiref.sync import sync_to_async

@api.get("/users/{user_id}")
async def get_user(request, user_id: int):
    # Wrap sync ORM call
    user = await sync_to_async(User.objects.get)(id=user_id)
    return user

# Or use a wrapper function
@sync_to_async
def get_user_sync(user_id):
    return User.objects.select_related('profile').get(id=user_id)

@api.get("/users/{user_id}")
async def get_user(request, user_id: int):
    user = await get_user_sync(user_id)
    return user
```

## Concurrent Operations

### Using asyncio.gather

Run multiple operations concurrently:

```python
import asyncio

@api.get("/dashboard")
async def get_dashboard(request):
    # Sequential: ~600ms (200+200+200)
    # users = await get_user_count()
    # orders = await get_order_count()
    # revenue = await get_revenue()

    # Concurrent: ~200ms (max of all)
    users, orders, revenue = await asyncio.gather(
        get_user_count(),
        get_order_count(),
        get_revenue(),
    )

    return {
        "users": users,
        "orders": orders,
        "revenue": revenue,
    }
```

### Using asyncio.create_task

For fire-and-forget operations:

```python
@api.post("/orders")
async def create_order(request, data: OrderCreate):
    order = await Order.objects.acreate(**data.model_dump())

    # Start background tasks (don't wait)
    asyncio.create_task(send_confirmation_email(order))
    asyncio.create_task(update_inventory(order))

    return order
```

### Using asyncio.wait_for (Timeouts)

```python
import asyncio

@api.get("/external-data")
async def get_external_data(request):
    try:
        # Timeout after 5 seconds
        data = await asyncio.wait_for(
            fetch_from_external_api(),
            timeout=5.0
        )
        return data
    except asyncio.TimeoutError:
        return {"error": "External API timeout"}, 504
```

## Async HTTP Clients

### Using aiohttp

```python
import aiohttp

@api.get("/proxy")
async def proxy_request(request, url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data
```

### Using httpx

```python
import httpx

@api.get("/external")
async def fetch_external(request):
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()
```

### Parallel External Calls

```python
import asyncio
import httpx

@api.get("/aggregate")
async def aggregate_data(request):
    async with httpx.AsyncClient() as client:
        responses = await asyncio.gather(
            client.get("https://api1.example.com/data"),
            client.get("https://api2.example.com/data"),
            client.get("https://api3.example.com/data"),
        )

    return {
        "api1": responses[0].json(),
        "api2": responses[1].json(),
        "api3": responses[2].json(),
    }
```

## Async Caching

### Using Async Cache Operations

```python
from django_matt.utils.performance import distributed_cache

@api.get("/data")
async def get_data(request):
    # Async get_or_set
    data = await distributed_cache.aget_or_set(
        "expensive_data",
        compute_data,  # Can be async function
        timeout=300,
    )
    return data
```

### Async Cache Decorator

```python
from django_matt.utils.performance import cache_manager

@api.get("/products")
@cache_manager.cache_response(timeout=300)
async def list_products(request):
    # Response is cached
    return [p async for p in Product.objects.all()]
```

## Async File Operations

### Using aiofiles

```python
import aiofiles

@api.post("/upload")
async def upload_file(request, file: UploadFile):
    async with aiofiles.open(f"uploads/{file.filename}", "wb") as f:
        content = await file.read()
        await f.write(content)

    return {"filename": file.filename}

@api.get("/download/{filename}")
async def download_file(request, filename: str):
    async with aiofiles.open(f"uploads/{filename}", "rb") as f:
        content = await f.read()

    return Response(content, media_type="application/octet-stream")
```

## Async Streaming

### Streaming Responses

```python
from django.http import StreamingHttpResponse

async def generate_data():
    for i in range(1000):
        yield f"data: {i}\n"
        await asyncio.sleep(0.01)

@api.get("/stream")
async def stream_data(request):
    return StreamingHttpResponse(
        generate_data(),
        content_type="text/event-stream"
    )
```

### Server-Sent Events (SSE)

```python
async def event_stream(user_id: int):
    yield "event: connected\ndata: {}\n\n"

    async for event in get_user_events(user_id):
        yield f"event: {event.type}\ndata: {event.data}\n\n"

@api.get("/events")
async def subscribe_events(request):
    return StreamingHttpResponse(
        event_stream(request.user.id),
        content_type="text/event-stream"
    )
```

## Best Practices

### 1. Use Async Throughout

```python
# Bad: Mixing sync calls in async view
@api.get("/users")
async def list_users(request):
    users = User.objects.all()  # Sync! Blocks event loop
    return users

# Good: Fully async
@api.get("/users")
async def list_users(request):
    users = [u async for u in User.objects.all()]  # Async
    return users
```

### 2. Don't Block the Event Loop

```python
# Bad: CPU-bound work blocks event loop
@api.get("/compute")
async def compute(request):
    result = heavy_computation()  # Blocks!
    return result

# Good: Run in thread pool
from asgiref.sync import sync_to_async

@api.get("/compute")
async def compute(request):
    result = await sync_to_async(heavy_computation)()
    return result

# Or use ProcessPoolExecutor for CPU-bound
import asyncio
from concurrent.futures import ProcessPoolExecutor

executor = ProcessPoolExecutor(max_workers=4)

@api.get("/compute")
async def compute(request):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, heavy_computation)
    return result
```

### 3. Handle Errors Properly

```python
@api.get("/data")
async def get_data(request):
    try:
        result = await asyncio.gather(
            fetch_users(),
            fetch_orders(),
            return_exceptions=True  # Don't fail all on one error
        )

        users = result[0] if not isinstance(result[0], Exception) else []
        orders = result[1] if not isinstance(result[1], Exception) else []

        return {"users": users, "orders": orders}
    except Exception as e:
        return {"error": str(e)}, 500
```

### 4. Use Semaphores for Rate Limiting

```python
import asyncio

# Limit concurrent external calls
semaphore = asyncio.Semaphore(10)

async def fetch_with_limit(url):
    async with semaphore:
        return await fetch_url(url)

@api.get("/batch")
async def batch_fetch(request, urls: list[str]):
    results = await asyncio.gather(*[
        fetch_with_limit(url) for url in urls
    ])
    return results
```

### 5. Set Appropriate Timeouts

```python
import asyncio

@api.get("/external")
async def fetch_external(request):
    try:
        async with asyncio.timeout(10):  # Python 3.11+
            return await external_api_call()
    except asyncio.TimeoutError:
        return {"error": "Timeout"}, 504

# For Python < 3.11
@api.get("/external")
async def fetch_external(request):
    try:
        return await asyncio.wait_for(external_api_call(), timeout=10)
    except asyncio.TimeoutError:
        return {"error": "Timeout"}, 504
```

## Performance Monitoring

### Measure Async Operations

```python
from django_matt.utils.performance import benchmark

@api.get("/data")
@benchmark.measure("data_endpoint")
async def get_data(request):
    async with benchmark.measure("database"):
        data = await fetch_from_database()

    async with benchmark.measure("processing"):
        result = await process_data(data)

    return result
```

### Async Timing Context Manager

```python
import time

class async_timer:
    def __init__(self, name):
        self.name = name

    async def __aenter__(self):
        self.start = time.perf_counter()
        return self

    async def __aexit__(self, *args):
        elapsed = time.perf_counter() - self.start
        print(f"{self.name}: {elapsed*1000:.2f}ms")

@api.get("/data")
async def get_data(request):
    async with async_timer("database"):
        data = await fetch_data()
    return data
```

## Deployment Considerations

### ASGI Server Configuration

```python
# Using uvicorn
# uvicorn myproject.asgi:application --workers 4

# Using hypercorn
# hypercorn myproject.asgi:application --workers 4

# Using gunicorn with uvicorn workers
# gunicorn myproject.asgi:application -k uvicorn.workers.UvicornWorker --workers 4
```

### Connection Pool Settings

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
        'CONN_MAX_AGE': 60,  # Keep connections alive
        'CONN_HEALTH_CHECKS': True,  # Django 4.1+
    }
}
```

### Event Loop Policy (uvloop)

```python
# For better performance, use uvloop
# uv add uvloop

# In your ASGI application
import uvloop
uvloop.install()
```

## Troubleshooting

### "Synchronous requests not allowed"

```python
# Error: SynchronousOnlyOperation
# Fix: Use async ORM or sync_to_async

from asgiref.sync import sync_to_async

# Option 1: Use async ORM methods
user = await User.objects.aget(id=1)

# Option 2: Wrap sync code
user = await sync_to_async(User.objects.get)(id=1)
```

### Event Loop Already Running

```python
# Error: This event loop is already running
# Fix: Don't use asyncio.run() inside async context

# Bad
async def view(request):
    result = asyncio.run(some_async_func())  # Error!

# Good
async def view(request):
    result = await some_async_func()
```

### Debugging Async Code

```python
import asyncio

# Enable debug mode
asyncio.get_event_loop().set_debug(True)

# Or via environment variable
# PYTHONASYNCIODEBUG=1 python manage.py runserver
```

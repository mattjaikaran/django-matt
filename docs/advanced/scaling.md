# Scaling Guide

How to scale django-matt applications from a single process to a distributed fleet.

---

## Horizontal Scaling with ASGI

django-matt is async-first. Every view, controller method, and middleware hook is an `async def`. This means a single worker can handle many concurrent requests while waiting on I/O.

### Basic ASGI Setup

```bash
# Development
uvicorn config.asgi:application --reload --host 0.0.0.0 --port 8000

# Production: gunicorn manages multiple uvicorn workers
gunicorn config.asgi:application \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000
```

### Worker Count

Rule of thumb: `2 * num_cpus + 1` for CPU-bound workloads, but django-matt apps are typically I/O-bound. Start with `num_cpus` workers and scale based on observed CPU usage.

```bash
# 4-core machine, I/O-bound app
gunicorn config.asgi:application \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4

# CPU-heavy (ML inference, image processing)
gunicorn config.asgi:application \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 9  # 2 * 4 + 1
```

### Load Balancing

Put a reverse proxy (nginx, Caddy, or cloud LB) in front of multiple app instances. All django-matt endpoints are stateless by default -- JWT auth has no server-side session state.

```nginx
upstream app {
    server app-1:8000;
    server app-2:8000;
    server app-3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://app;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-ID $request_id;
    }
}
```

---

## Database Connection Pooling

django-matt auto-configures connection pooling for PostgreSQL via psycopg3.

### Configuration

```python
from django_matt.config import configure

configure(
    database="postgresql",  # enables pooling with defaults
)

# Or fine-tune via settings:
DJANGO_MATT = {
    "CONNECTION_POOL": {
        "ENABLED": True,
        "MIN_SIZE": 5,     # keep 5 connections warm
        "MAX_SIZE": 20,    # allow up to 20 concurrent connections
    },
}
```

### Sizing the Pool

Each worker process gets its own pool. Total connections = `pool_max_size * num_workers`.

```
4 workers * 20 max_size = 80 connections
PostgreSQL default max_connections = 100
```

Leave headroom for migrations, admin sessions, and monitoring. For larger deployments, use PgBouncer:

```
[pgbouncer]
pool_mode = transaction
max_client_conn = 400
default_pool_size = 25
```

### Async ORM Usage

All ORM calls in async handlers must use the async variants:

```python
# Correct
user = await User.objects.aget(id=user_id)
users = [u async for u in User.objects.filter(is_active=True)]
await user.asave()

# Wrong -- blocks the event loop
user = User.objects.get(id=user_id)  # raises SynchronousOnlyOperation
```

---

## Caching Strategies

### Layer 1: View-Level Caching with Interceptors

Use the built-in `CachingInterceptor` for route-level response caching:

```python
from django_matt.interceptors.builtins import CachingInterceptor
from django_matt.interceptors.decorators import intercept

@api.get("/products")
@intercept(CachingInterceptor(ttl=60.0, methods={"GET"}))
async def list_products(request):
    products = [p async for p in Product.objects.all()]
    return {"products": products}
```

Responses are cached in-memory with an `X-Cache: HIT/MISS` header.

### Layer 2: Application-Level Caching

Use `CacheManager` for fine-grained control:

```python
from django_matt.utils.performance import CacheManager

cache = CacheManager()  # uses Django's default cache backend

async def get_user_profile(user_id: int) -> dict:
    key = f"user_profile:{user_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    user = await User.objects.aget(id=user_id)
    profile = UserSchema.from_orm_fast(user).model_dump()
    cache.set(key, profile, timeout=300)  # 5 minutes
    return profile
```

### Layer 3: Django Cache Framework

Configure Redis as the cache backend:

```python
configure(cache="redis")

# This sets:
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.redis.RedisCache",
#         "LOCATION": "redis://localhost:6379/0",
#     }
# }
```

### Cache Invalidation

Invalidate on write operations using view hooks or interceptors:

```python
class ProductViewSet(APIViewSet):
    api = api
    model = Product

    list = ListView()
    create = CreateView()
    update = UpdateView()

    async def after_create(self, request, instance):
        cache.delete("products:list")

    async def after_update(self, request, instance):
        cache.delete(f"product:{instance.id}")
        cache.delete("products:list")
```

---

## Background Task Offloading

Move slow operations out of the request-response cycle.

### Celery Integration

```python
# tasks.py
from django_matt.tasks import task

@task
async def send_welcome_email(user_id: int):
    user = await User.objects.aget(id=user_id)
    await send_email(user.email, template="welcome")

# In your controller
@api.post("/users")
async def create_user(request, data: UserCreateSchema):
    user = await User.objects.acreate(**data.model_dump())
    send_welcome_email.delay(user.id)  # runs in background
    return UserSchema.from_orm_fast(user)
```

### Task Patterns

- **Fire-and-forget**: `task.delay(args)` -- email, notifications, analytics
- **Chained**: `chain(task1.s(arg), task2.s())` -- multi-step workflows
- **Scheduled**: `task.apply_async(eta=datetime)` -- delayed execution

### When to Offload

| Operation | In-Request | Background |
|---|---|---|
| DB read/write | Yes | |
| Email sending | | Yes |
| File processing | | Yes |
| Webhook delivery | | Yes |
| Analytics tracking | | Yes |
| PDF generation | | Yes |
| External API calls (slow) | | Yes |
| Cache warming | | Yes |

---

## WebSocket Scaling

WebSocket connections are stateful and long-lived. A single server can handle thousands, but horizontal scaling requires a pub/sub backend.

### Single-Server Setup

```python
# routing.py
from django_matt.websockets import WebSocketRouter

ws_router = WebSocketRouter()

@ws_router.route("/ws/chat/{room_id}")
class ChatConsumer:
    async def on_connect(self, ws):
        await ws.accept()

    async def on_message(self, ws, data):
        await ws.send_json({"echo": data})
```

### Multi-Server with Redis Pub/Sub

Use Django Channels with a Redis channel layer:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("redis", 6379)],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}
```

### Centrifugo for Large Scale

For thousands of concurrent WebSocket connections, offload to Centrifugo:

```python
# django-matt handles HTTP API, Centrifugo handles WebSocket transport
DJANGO_MATT = {
    "WEBSOCKETS": {
        "BACKEND": "centrifugo",
        "API_URL": "http://centrifugo:8000/api",
        "API_KEY": "your-api-key",
    },
}
```

---

## Slim Mode

Reduce memory footprint and startup time by loading only the modules you need.

### Modes

| Mode | Behavior |
|---|---|
| `full` | Load everything (default, backwards-compatible) |
| `slim` | Only core + explicitly enabled modules |
| `minimal` | Only core + auth + error handling |
| `auto` | Detect from settings which modules are configured |

### Configuration

```python
DJANGO_MATT = {
    "SLIM_MODE": {
        "mode": "slim",
        "enabled_modules": ["auth", "cors", "observability", "throttling"],
        "disabled_modules": [],
        "lazy_imports": True,
    },
}
```

### Auto Mode

Auto mode scans your `DJANGO_MATT` settings and only loads modules that have corresponding configuration:

```python
DJANGO_MATT = {
    "SLIM_MODE": {"mode": "auto"},
    "JWT_AUTH": {...},          # -> loads auth module
    "CORS": {...},              # -> loads cors module
    "OBSERVABILITY": {...},     # -> loads observability module
    # billing, analytics, etc. are NOT loaded
}
```

### Impact

Slim mode controls:
- **Middleware**: only middleware for active modules is injected
- **URL patterns**: only active module URLs are registered
- **Imports**: heavy modules are deferred until first use when `lazy_imports: True`

On a typical app using 5-6 modules out of 30+, slim mode reduces import time and memory usage significantly.

### Module Registry

Programmatic control over which modules are active:

```python
from django_matt.slim import ModuleRegistry

registry = ModuleRegistry(mode="slim")
registry.activate("auth", "cors", "observability")

# Check if a module is active
if registry.is_active("billing"):
    ...

# Get middleware for active modules only
middleware = registry.get_active_middleware()
```

---

## Scaling Checklist

1. **Profile first** -- use `AutoInstrumentor` and `DatabaseQueryMiddleware` to find actual bottlenecks
2. **Cache aggressively** -- most read-heavy APIs benefit enormously from a 60-second cache
3. **Pool connections** -- a misconfigured pool is the #1 cause of "too many connections" errors
4. **Offload slow work** -- anything over 500ms belongs in a background task
5. **Scale horizontally** -- add more ASGI workers before optimizing individual request speed
6. **Use slim mode** -- if you only use 5 modules, do not load 30

# Building Custom Extensions

django-matt is designed to be extended. This guide covers creating custom modules, interceptors, exception filters, auth backends, and serialization backends.

---

## Creating a MattModule

A `MattModule` is the primary extension point. It has lifecycle hooks, dependency resolution, config validation, and can contribute URLs and middleware.

### Basic Module

```python
# myapp/matt_module.py
from django_matt.modules.base import MattModule

class AnalyticsModule(MattModule):
    name = "analytics"
    version = "1.0.0"
    dependencies = ["auth"]  # loaded after auth module

    async def on_ready(self) -> None:
        """Called when the module is loaded (after dependencies)."""
        # Initialize analytics client, warm caches, etc.
        self.client = AnalyticsClient()

    async def on_shutdown(self) -> None:
        """Called when the module is unloaded (reverse order)."""
        await self.client.flush()

    def get_urls(self) -> list:
        """Return URL patterns contributed by this module."""
        from django.urls import path
        from .views import track_event
        return [path("analytics/track/", track_event)]

    def get_middleware(self) -> list[str]:
        """Return middleware class dotted paths."""
        return ["myapp.middleware.AnalyticsMiddleware"]

    def get_checks(self) -> list:
        """Return Django system checks."""
        return [check_analytics_config]
```

### Module with Config Validation

Use a Pydantic schema to validate module configuration at load time:

```python
from pydantic import BaseModel

class AnalyticsConfig(BaseModel):
    api_key: str
    endpoint: str = "https://analytics.example.com"
    batch_size: int = 100
    flush_interval: float = 30.0

class AnalyticsModule(MattModule):
    name = "analytics"
    version = "1.0.0"
    config_namespace = "ANALYTICS"
    config_schema = AnalyticsConfig
```

Set config via the registry:

```python
from django_matt.modules.registry import get_registry

registry = get_registry()
registry.set_config("ANALYTICS", {
    "api_key": "ak_live_...",
    "batch_size": 200,
})
```

Or via Django settings:

```python
DJANGO_MATT = {
    "MODULES": ["myapp.matt_module"],
    "ANALYTICS": {
        "api_key": "ak_live_...",
    },
}
```

### Registering Modules

Modules are discovered in three ways:

1. **Entry points** (for published packages):

```toml
# pyproject.toml
[project.entry-points."django_matt.modules"]
my_analytics = "myapp.matt_module:AnalyticsModule"
```

2. **Settings list** (explicit):

```python
DJANGO_MATT = {
    "MODULES": ["myapp.matt_module"],
}
```

3. **Convention** (automatic): place a `matt_module.py` in any installed Django app. The registry scans all installed apps for this file.

### Module Lifecycle Hooks

React to other modules being loaded:

```python
from django_matt.modules.hooks import on_module_loaded, on_all_loaded, before_module_load

@on_module_loaded("auth")
async def setup_auth_integration(auth_module):
    """Called when the auth module finishes loading."""
    auth_module.register_provider(MyCustomProvider())

@before_module_load("billing")
async def inject_billing_config(billing_module):
    """Called just before the billing module loads."""
    billing_module.default_currency = "EUR"

@on_all_loaded
async def finalize():
    """Called after all modules have loaded."""
    print("All modules ready")
```

### Module Registry API

```python
from django_matt.modules.registry import get_registry, discover_modules

registry = get_registry()

# Register a module class or instance
registry.register(AnalyticsModule)

# Resolve dependency order (topological sort)
order = registry.resolve_dependencies()

# Load all modules in order
await registry.load_all()

# Check module state
registry.is_registered("analytics")  # True
registry.is_loaded("analytics")      # True after load_all()

# Get a loaded module
mod = registry.get("analytics")

# List all loaded modules
for mod in registry.list_loaded():
    print(f"{mod.name} v{mod.version}")

# Unload all (reverse order, calls on_shutdown)
await registry.unload_all()
```

---

## Custom Interceptors

Interceptors are route-scoped middleware. They run before/after individual view handlers, not globally.

### Creating an Interceptor

```python
from django.http import HttpRequest, HttpResponse
from django_matt.interceptors.base import Interceptor

class AuditInterceptor(Interceptor):
    """Log who accessed what."""
    order = 10  # lower order runs first

    def enabled(self, request: HttpRequest) -> bool:
        """Return False to skip this interceptor for a request."""
        return request.user.is_authenticated

    async def before_request(
        self, request: HttpRequest, **kwargs
    ) -> HttpRequest | HttpResponse | None:
        """
        Called before the view handler.

        Return None to continue, HttpResponse to short-circuit.
        """
        request._audit_start = time.monotonic()
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs
    ) -> HttpResponse:
        """Called after the view handler returns a response."""
        duration = time.monotonic() - request._audit_start
        await AuditLog.objects.acreate(
            user=request.user,
            path=request.path,
            method=request.method,
            status=response.status_code,
            duration_ms=duration * 1000,
        )
        return response

    async def on_error(
        self, request: HttpRequest, exc: Exception, **kwargs
    ) -> HttpResponse | None:
        """Called if the view handler raises an exception."""
        logger.error(f"Audit: {request.path} raised {exc}")
        return None  # let the exception propagate
```

### Applying Interceptors

Per-view with the `@intercept` decorator:

```python
from django_matt.interceptors.decorators import intercept

@api.get("/admin/users")
@intercept(AuditInterceptor(), RateLimitInterceptor(max_requests=10, window=60))
async def admin_list_users(request):
    ...
```

Per-controller with the class decorator:

```python
from django_matt.interceptors.decorators import intercept_controller

@intercept_controller(AuditInterceptor())
@api.controller("/admin")
class AdminController:
    ...
```

### Built-in Interceptors

| Interceptor | Purpose |
|---|---|
| `LoggingInterceptor` | Structured request/response logging with optional body/header capture |
| `TimingInterceptor` | Adds `X-Interceptor-Time` header with handler duration |
| `CachingInterceptor` | In-memory response cache keyed by method+path+query |
| `TransformInterceptor` | Apply transforms to request body and/or response content |
| `RetryInterceptor` | Retry handler on specified exception types |
| `RateLimitInterceptor` | Per-route in-memory rate limiter |

---

## Custom Exception Filters

Exception filters catch specific exception types and convert them to HTTP responses.

### Class-Based Filter

```python
from django.http import HttpRequest, HttpResponse, JsonResponse
from django_matt.exceptions.filters import ExceptionFilter

class StripeErrorFilter(ExceptionFilter):
    exception_types = (stripe.error.StripeError,)
    order = 10

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        if isinstance(exc, stripe.error.CardError):
            return JsonResponse(
                {"error": "card_declined", "detail": str(exc)},
                status=402,
            )
        return JsonResponse(
            {"error": "payment_error", "detail": "Payment processing failed"},
            status=500,
        )
```

### Function-Based Filter

Use the `@catch` decorator for inline exception handling:

```python
from django_matt.exceptions.decorators import catch

async def handle_validation(exc, request):
    return JsonResponse({"errors": exc.errors()}, status=422)

@api.post("/users")
@catch(ValidationError, handler=handle_validation)
async def create_user(request, data: UserCreateSchema):
    ...
```

### Global Registration

Register a filter globally so it applies to all routes:

```python
from django_matt.exceptions.decorators import register_global_filter

register_global_filter(StripeErrorFilter())
```

### Exception Filter Chain

Filters are tried in `order` (lowest first). The first filter that `can_handle(exc)` returns True wins. If a filter itself raises, the chain logs the error and tries the next filter.

```python
from django_matt.exceptions.filters import ExceptionFilterChain

chain = ExceptionFilterChain([
    NotFoundFilter(),       # order=0
    ValidationFilter(),     # order=5
    StripeErrorFilter(),    # order=10
    CatchAllFilter(),       # order=100
])

response = await chain.handle(exc, request)
```

---

## Custom Auth Backends

### SecretsBackend Protocol

Implement the `SecretsBackend` protocol to integrate with any secrets provider:

```python
from django_matt.secrets.backends import SecretsBackend

class OnePasswordBackend:
    """1Password secrets backend."""

    def __init__(self, vault: str, token: str) -> None:
        self._vault = vault
        self._token = token

    async def get(self, key: str) -> str | None:
        # Call 1Password Connect API
        ...

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        return {k: await self.get(k) for k in keys}

    async def set(self, key: str, value: str) -> None:
        ...

    async def delete(self, key: str) -> None:
        ...

    async def list_keys(self) -> list[str]:
        ...
```

### Built-in Backends

| Backend | Use Case |
|---|---|
| `EnvBackend` | Environment variables (dev/CI) |
| `DotenvBackend` | `.env` files (local dev) |
| `EncryptedFileBackend` | Fernet-encrypted JSON file |
| `AWSSecretsManagerBackend` | AWS Secrets Manager |
| `VaultBackend` | HashiCorp Vault KV v2 |
| `GCPSecretManagerBackend` | Google Cloud Secret Manager |

---

## Custom Serialization Backends

### FastJSONRenderer

Extend the renderer for custom serialization logic:

```python
from django_matt.utils.performance import FastJSONRenderer

class CustomRenderer(FastJSONRenderer):
    @staticmethod
    def dumps(obj, **kwargs):
        # Add custom preprocessing
        if hasattr(obj, "to_api_dict"):
            obj = obj.to_api_dict()
        return FastJSONRenderer.dumps(obj, **kwargs)
```

### Response Classes

Use the built-in response classes for optimal serialization:

```python
from django_matt.utils.performance import FastJsonResponse, MessagePackResponse

# JSON response using orjson (fast)
return FastJsonResponse({"users": user_list})

# MessagePack response (compact binary)
return MessagePackResponse({"users": user_list})
```

---

## Publishing as a Package

### Package Structure

```
my-matt-extension/
    pyproject.toml
    my_extension/
        __init__.py
        matt_module.py
        interceptors.py
        filters.py
```

### pyproject.toml

```toml
[project]
name = "my-matt-extension"
version = "0.1.0"
dependencies = ["django-matt>=1.0"]

[project.entry-points."django_matt.modules"]
my_extension = "my_extension.matt_module:MyExtensionModule"
```

The entry point ensures the module is auto-discovered by `discover_modules()` without requiring the user to add anything to their `DJANGO_MATT["MODULES"]` list.

### Testing Your Extension

```python
import pytest
from django_matt.modules.registry import ModuleRegistry

@pytest.fixture
def registry():
    r = ModuleRegistry()
    yield r
    r.reset()

@pytest.mark.asyncio
async def test_module_loads(registry):
    from my_extension.matt_module import MyExtensionModule

    registry.register(MyExtensionModule)
    await registry.load_all()
    assert registry.is_loaded("my_extension")
```

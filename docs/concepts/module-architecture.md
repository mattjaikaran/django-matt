# Module Architecture

django-matt is organized as a collection of loosely coupled modules. Each module encapsulates a feature domain (auth, billing, analytics, etc.) and can be loaded eagerly, lazily, or not at all depending on your application's needs.

## Module Boundaries

Every top-level directory under `django_matt/` is a module. Modules follow these rules:

1. **Self-contained** — a module's core logic lives within its own directory
2. **Explicit dependencies** — cross-module imports go through public APIs (`__init__.py` exports)
3. **Optional by default** — most modules can be disabled without breaking the core framework

Core modules that are always loaded: `core`, `router`, `controller`, `schema`, `errors`, `openapi`, `docs`, `redoc`.

## Slim Mode

Slim mode controls which modules load at startup. Configure it in Django settings:

```python
# settings.py
DJANGO_MATT = {
    "SLIM_MODE": {
        "mode": "slim",                    # "full", "slim", "minimal", "auto"
        "enabled_modules": ["auth", "di"], # only load these (slim mode)
        "disabled_modules": ["graphql"],   # never load these
        "lazy_imports": True,              # defer heavy module imports
    }
}
```

### Modes

| Mode | Behavior |
|------|----------|
| `full` | Everything loads. Default, backwards-compatible. |
| `slim` | Only core + explicitly enabled modules load. |
| `minimal` | Only core + auth + error handling. Smallest footprint. |
| `auto` | Detects which modules are configured in `DJANGO_MATT` settings and loads only those. |

### Checking Module Status

```python
from django_matt.slim import is_module_enabled

if is_module_enabled("billing"):
    from django_matt.billing import create_subscription
```

### Module Registry (Slim)

The `ModuleRegistry` tracks which modules are active and provides their middleware:

```python
from django_matt.slim import ModuleRegistry

registry = ModuleRegistry(mode="auto")
registry.activate("billing", "analytics")
registry.deactivate("graphql")

# Get middleware for active modules only
active_middleware = registry.get_active_middleware()
# ["django_matt.auth.middleware.JWTAuthenticationMiddleware", ...]
```

Core modules cannot be deactivated. Calling `registry.deactivate("core")` raises `ValueError`.

### Auto-Detection

In `auto` mode, the registry scans `DJANGO_MATT` settings keys to determine which modules are in use:

| Setting Key | Module Activated |
|-------------|-----------------|
| `JWT_AUTH` | auth |
| `CORS` | cors |
| `FEATURE_FLAGS` | flags |
| `EXPERIMENTS` | experiments |
| `DI_AUTO_WIRE` | di |
| `BILLING` | billing |
| `MULTITENANCY` | multitenancy |
| `OBSERVABILITY` | observability |
| `ANALYTICS` | analytics |
| `WEBSOCKETS` | websockets |
| `GRAPHQL` | graphql |

The `MIDDLEWARE_STACK` setting activates bundles:
- `"production"` -> security, request_id, cors, logging, timing
- `"development"` -> request_id, cors, logging, timing

## Lazy Loading

Heavy modules (billing, AI, ML, GraphQL, analytics, etc.) benefit from deferred loading. The `DeferredLoader` uses `LazyModuleProxy` to defer `import` until first attribute access.

### LazyModuleProxy

A transparent proxy that imports the module on first access:

```python
from django_matt.loader import lazy_import

billing = lazy_import("django_matt.billing")

# Module is NOT imported yet
print(repr(billing))
# <LazyModuleProxy 'django_matt.billing' (deferred)>

# First attribute access triggers the import
billing.create_subscription(...)
# <LazyModuleProxy 'django_matt.billing' (loaded)>
```

### DeferredLoader

Manages lazy loading for all django-matt modules:

```python
from django_matt.loader import DeferredLoader

loader = DeferredLoader()

# Light modules are loaded eagerly
core = loader.get("core")       # imported immediately

# Heavy modules are deferred
billing = loader.get("billing") # LazyModuleProxy, not imported yet

# Force immediate loading
loader.preload("billing", "analytics")

# Check status
loader.is_loaded("billing")      # True after preload
loader.deferred_modules           # list of not-yet-loaded module names
```

**Light modules** (always eager): core, auth, views, config, permissions, openapi, pagination, filtering.

**Heavy modules** (deferred by default): billing, ai, ml, graphql, websockets, analytics, experiments, notifications, email, messaging, files, tasks.

## Plugin System (MattModule)

For third-party or application-level extensions, django-matt provides a plugin system based on `MattModule`.

### Defining a Module

```python
from django_matt.modules import MattModule
from pydantic import BaseModel

class StripeConfig(BaseModel):
    api_key: str
    webhook_secret: str

class StripeModule(MattModule):
    name = "stripe"
    version = "1.0.0"
    dependencies = ["auth", "billing"]
    config_namespace = "STRIPE"
    config_schema = StripeConfig

    async def on_ready(self):
        """Called when the module is loaded (after dependencies)."""
        import stripe
        config = self.validate_config(get_stripe_config())
        stripe.api_key = config.api_key

    async def on_shutdown(self):
        """Called when the application shuts down."""
        pass

    def get_urls(self):
        """Return URL patterns this module provides."""
        return [
            path("webhooks/stripe/", stripe_webhook_view),
        ]

    def get_middleware(self):
        """Return middleware class paths this module requires."""
        return ["myapp.stripe.StripeSignatureMiddleware"]

    def get_checks(self):
        """Return Django system checks."""
        return [check_stripe_configuration]
```

### Module Registry

Register and load modules with dependency resolution:

```python
from django_matt.modules import get_registry

registry = get_registry()
registry.register(StripeModule)
registry.register(BillingModule)

# Resolve load order (topological sort of dependencies)
order = registry.resolve_dependencies()
# ["billing", "stripe"] — billing loads before stripe

# Load all modules in order
await registry.load_all()

# Access a loaded module
stripe = registry.get("stripe")
```

### Discovery

Modules are discovered from three sources (in order):

1. **Entry points** — `pyproject.toml` entry points under `django_matt.modules`
2. **Settings** — `DJANGO_MATT["MODULES"]` list of dotted paths
3. **Convention** — `matt_module.py` in any installed Django app

```toml
# pyproject.toml (for third-party packages)
[project.entry-points."django_matt.modules"]
stripe = "mypackage.stripe_module:StripeModule"
```

```python
# settings.py
DJANGO_MATT = {
    "MODULES": [
        "myapp.modules.analytics",
        "myapp.modules.notifications",
    ]
}
```

```python
# myapp/matt_module.py (convention-based discovery)
from django_matt.modules import MattModule

class MyAppModule(MattModule):
    name = "myapp"
    ...
```

### Lifecycle Hooks

Hook into the module loading lifecycle:

```python
registry = get_registry()

# Run after a specific module loads
@registry.add_on_loaded_hook("auth")
async def on_auth_loaded(auth_module):
    print(f"Auth module loaded: {auth_module}")

# Run before a specific module loads
@registry.add_before_load_hook("billing")
async def before_billing(billing_module):
    # Pre-configure something
    ...

# Run after ALL modules are loaded
@registry.add_all_loaded_hook
async def on_all_loaded():
    print("All modules ready")
```

### Configuration

Pass configuration to modules via the registry:

```python
registry.set_config("STRIPE", {
    "api_key": "sk_test_...",
    "webhook_secret": "whsec_...",
})

# The module's on_ready() receives validated config via validate_config()
```

If a module defines `config_schema`, the configuration is validated against the Pydantic model during loading.

## Import Patterns

### Internal Imports

Within django-matt, modules import from each other through public APIs:

```python
# Good — import from public API
from django_matt.core.errors import APIError
from django_matt.auth.jwt import decode_token

# Bad — import internal implementation details
from django_matt.core.errors import _make_error_envelope  # private
```

### Conditional Imports

For optional dependencies, use `try/except` or check module availability:

```python
from django_matt.slim import is_module_enabled

if is_module_enabled("billing"):
    from django_matt.billing import BillingService
```

Or use `importlib`:

```python
import importlib

try:
    billing = importlib.import_module("django_matt.billing")
except ImportError:
    billing = None
```

## Creating Extensions

To create a reusable django-matt extension:

1. **Subclass `MattModule`** with your module's configuration
2. **Declare dependencies** on other modules your extension needs
3. **Register via entry points** for automatic discovery
4. **Provide a `config_schema`** for validated configuration
5. **Use lifecycle hooks** (`on_ready`, `on_shutdown`) for setup and teardown

```python
# myextension/matt_module.py
from django_matt.modules import MattModule

class MyExtensionModule(MattModule):
    name = "myextension"
    version = "0.1.0"
    dependencies = ["auth"]

    async def on_ready(self):
        # Initialize your extension
        ...
```

```toml
# pyproject.toml
[project.entry-points."django_matt.modules"]
myextension = "myextension.matt_module:MyExtensionModule"
```

Users install your package, and django-matt discovers and loads it automatically.

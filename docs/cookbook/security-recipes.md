# Security Recipes

Secrets management, exception handling, and role-based access patterns.

## Rotating API Keys

```python
from django_matt.secrets import (
    RotationPolicy,
    SecretsManager,
    get_secrets_manager,
    on_rotation,
)


# Register a rotation callback via decorator
@on_rotation("API_KEY")
async def handle_api_key_rotation(key: str):
    """Called when the API_KEY secret is rotated."""
    new_key = await get_secrets_manager().get("API_KEY")
    await external_client.update_auth(new_key)


# Or register programmatically on the manager
manager = get_secrets_manager()
manager.on_rotation("DATABASE_PASSWORD", reconnect_database)


# Set up a rotation policy — check every 60s, rotate every 24h
from django_matt.secrets.rotation import RotationChecker, RotationPolicy

checker = RotationChecker(check_interval=60.0)
checker.add_policy(RotationPolicy(
    key="API_KEY",
    ttl_seconds=86400,  # 24 hours
    callback=lambda key: print(f"Rotating {key}"),
))
checker.start()  # runs as an asyncio background task
```

## Environment-Based Secret Resolution

```python
from django_matt.secrets import (
    EnvBackend,
    SecretReference,
    SecretsManager,
)

# Resolve secrets from environment variables
manager = SecretsManager(backend=EnvBackend(prefix="MYAPP_"))

# Fetch secrets — looks up MYAPP_DATABASE_URL in os.environ
db_url = await manager.get("DATABASE_URL")
api_key = await manager.get("STRIPE_KEY", default="sk_test_xxx")

# Batch fetch
secrets = await manager.get_many(["DATABASE_URL", "REDIS_URL", "SECRET_KEY"])

# Use SecretReference URIs for explicit backend routing
ref = SecretReference("env://DATABASE_URL")
value = await manager.resolve_ref(ref)

# In settings.py — use the lazy secret() helper (no await needed)
from django_matt.secrets import secret

DATABASE_PASSWORD = secret("DB_PASSWORD", default="devpass")
STRIPE_API_KEY = secret("STRIPE_KEY")
```

## Encrypted Secrets File for Staging

```python
from django_matt.secrets import EncryptedFileBackend, SecretsManager

# Generate an encryption key (store this securely, e.g. in env var)
key = EncryptedFileBackend.generate_key()
# => "gAAAAABm..." (Fernet key)

# Create the encrypted backend
backend = EncryptedFileBackend(
    path="secrets/staging.enc",
    key=key,  # or os.environ["SECRETS_KEY"]
)

manager = SecretsManager(backend=backend)

# Store secrets — written to encrypted JSON file
await manager.set("DATABASE_URL", "postgres://staging:pass@db:5432/app")
await manager.set("REDIS_URL", "redis://staging-redis:6379/0")

# Read secrets — decrypted on the fly
db_url = await manager.get("DATABASE_URL")

# List all stored keys
keys = await manager.list_keys()
# => ["DATABASE_URL", "REDIS_URL"]
```

## Multi-Backend Secret Resolution

```python
from django_matt.secrets import (
    AWSSecretsManagerBackend,
    EnvBackend,
    SecretsManager,
    VaultBackend,
)

# Register multiple backends by scheme
manager = SecretsManager(
    backend=EnvBackend(),  # default fallback
    backends={
        "vault": VaultBackend(
            url="https://vault.internal:8200",
            token="hvs.xxx",
            mount_point="secret",
        ),
        "aws": AWSSecretsManagerBackend(
            region_name="us-east-1",
            prefix="myapp/",
        ),
    },
)

# Resolve by URI scheme
from django_matt.secrets import SecretReference

db_pass = await manager.resolve_ref(SecretReference("vault://database/password"))
api_key = await manager.resolve_ref(SecretReference("aws://stripe-key"))
local = await manager.resolve_ref(SecretReference("env://DEBUG"))
```

## Exception Filters for Clean Error Responses

```python
from django.http import HttpRequest, HttpResponse

from django_matt.exceptions import (
    ExceptionFilter,
    ExceptionFilterChain,
    ValidationExceptionFilter,
    NotFoundExceptionFilter,
    PermissionExceptionFilter,
    DatabaseExceptionFilter,
    register_global_filter,
    catch,
    exception_filter,
)

# Register built-in filters globally
register_global_filter(ValidationExceptionFilter())   # Pydantic -> 422
register_global_filter(NotFoundExceptionFilter())      # DoesNotExist -> 404
register_global_filter(PermissionExceptionFilter())    # PermissionDenied -> 403
register_global_filter(DatabaseExceptionFilter())      # IntegrityError -> 409


# Create a custom exception filter
@exception_filter(ValueError, TypeError, order=5)
class BadInputFilter(ExceptionFilter):
    exception_types = (ValueError, TypeError)

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        import orjson
        body = orjson.dumps({"status": 400, "detail": str(exc)})
        return HttpResponse(body, content_type="application/json", status=400)

register_global_filter(BadInputFilter())


# Use @catch on individual views
@catch(ValueError, handler=lambda exc, req: JsonResponse(
    {"error": str(exc)}, status=400
))
async def strict_endpoint(request):
    ...
```

## Role-Based Serialization (Admin Sees All, User Sees Subset)

```python
from pydantic import BaseModel

from django_matt.permissions import IsAdmin, IsAuthenticated


class UserPublicSchema(BaseModel):
    id: int
    name: str
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class UserAdminSchema(UserPublicSchema):
    email: str
    role: str
    is_active: bool
    created_at: str
    last_login: str | None = None


async def get_user(request, user_id: int):
    user = await User.objects.aget(pk=user_id)

    # Admin sees full details, regular users see public subset
    if request.user.is_staff:
        schema = UserAdminSchema.model_validate(user)
    else:
        schema = UserPublicSchema.model_validate(user)

    return JsonResponse(schema.model_dump())


async def list_users(request):
    users = User.objects.all()

    if request.user.is_staff:
        data = [
            UserAdminSchema.model_validate(u)
            async for u in users.aiterator()
        ]
    else:
        data = [
            UserPublicSchema.model_validate(u)
            async for u in users.only("id", "name", "avatar_url").aiterator()
        ]

    return JsonResponse([d.model_dump() for d in data], safe=False)
```

## Health Check Endpoints for Monitoring

```python
from django_matt.observability import (
    ReadinessChecker,
    health_view,
    ready_view,
    readiness_checker,
    observability_urlpatterns,
)

# Register custom readiness checks
def check_redis():
    try:
        from django.core.cache import cache
        cache.set("_probe", "1", 5)
        return (True, "Redis connected")
    except Exception as e:
        return (False, f"Redis error: {e}")


def check_external_api():
    import httpx
    try:
        resp = httpx.get("https://api.stripe.com/v1/", timeout=3)
        return (True, f"Stripe reachable ({resp.status_code})")
    except Exception as e:
        return (False, f"Stripe unreachable: {e}")


readiness_checker.register("redis", check_redis)
readiness_checker.register("stripe", check_external_api)


# URLs — include the built-in patterns
# GET /health  -> {"status": "healthy", "timestamp": ...}
# GET /ready   -> {"ready": true, "checks": {"database": ..., "redis": ...}}
from django.urls import include, path

urlpatterns = [
    path("", include(observability_urlpatterns)),
    # Also available: /_matt/metrics, /_matt/info, /_matt/debug
]
```

## Scoped Exception Handling (Controller and Route Level)

```python
from django_matt.exceptions import (
    ExceptionFilterRegistry,
    FunctionExceptionFilter,
    default_registry,
)


# Route-level filter — only applies to a specific endpoint
stripe_filter = FunctionExceptionFilter(
    exception_types=(StripeError,),
    handler=lambda exc, req: JsonResponse(
        {"detail": "Payment error", "code": exc.code}, status=402
    ),
    order=0,
)
default_registry.register_route_filter("POST:/api/payments/charge", stripe_filter)


# Controller-level filter — applies to all methods on a controller
class PaymentController:
    ...

default_registry.register_controller_filter(PaymentController, stripe_filter)


# Resolution order: route -> controller -> global
# First match wins
response = await default_registry.handle(
    exc,
    request,
    route_key="POST:/api/payments/charge",
    controller_cls=PaymentController,
)
```

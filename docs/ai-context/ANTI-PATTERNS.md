# Django Matt — Anti-Patterns (What NOT to Do)

> AI models: Read this BEFORE generating django-matt code. These are the most common mistakes.

## 1. register_controller() Does NOT Take a Prefix

```python
# WRONG — prefix is NOT an argument
api.register_controller(UserController, prefix="/users")
api.register_controller(UserController, prefix="users")

# CORRECT — prefix comes from @api.controller() decorator
@api.controller("/users")
class UserController(APIController): ...

api.register_controller(UserController)  # One arg only
```

## 2. QuerySets Are NOT Awaitable

```python
# WRONG — cannot await a queryset
users = await User.objects.all()
users = await User.objects.filter(is_active=True)

# CORRECT — use async iteration
users = [u async for u in User.objects.all()]
users = [u async for u in User.objects.filter(is_active=True)]
```

## 3. Use Async ORM Methods

```python
# WRONG — sync ORM in async context blocks the event loop
user = User.objects.get(id=1)
user.save()
user.delete()
User.objects.create(email="x@x.com")
User.objects.filter(id=1).exists()

# CORRECT — async equivalents
user = await User.objects.aget(id=1)
await user.asave()
await user.adelete()
await User.objects.acreate(email="x@x.com")
await User.objects.filter(id=1).aexists()
```

## 4. Don't Use pip — Use uv

```python
# WRONG
pip install django-matt
pip install django-matt[auth]

# CORRECT
uv add django-matt
uv add "django-matt[auth]"
```

## 5. Don't Import orjson Conditionally

```python
# WRONG — orjson is a base dependency, always available
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    import json
    HAS_ORJSON = False

# CORRECT — just import it
import orjson
```

## 6. Don't Use PyJWT

```python
# WRONG — django-matt has its own JWT implementation
import jwt
token = jwt.encode(payload, secret, algorithm="HS256")

# CORRECT — use the built-in
from django_matt.auth.jwt_builtin import encode_jwt, decode_jwt
token = encode_jwt(payload, secret, algorithm="HS256")
```

## 7. The Method is retrieve(), Not read()

```python
# WRONG — CRUDController method
async def read(self, request, id: int): ...

# CORRECT
async def retrieve(self, request, id: int): ...

# But ViewSet uses ReadView (the class name)
class MyViewSet(APIViewSet):
    read = ReadView()  # This is correct — ReadView is the class
```

## 8. Use force_authenticate, Not authenticate

```python
# WRONG — in tests
client.authenticate(user)

# CORRECT
client.force_login(user)
# Or for the Matt test client:
client.force_authenticate(user)
```

## 9. Don't Block the Event Loop with requests

```python
# WRONG — blocking HTTP in async context
import requests
response = requests.post(url, json=data)

# CORRECT — use httpx or wrap with sync_to_async
import httpx
async with httpx.AsyncClient() as client:
    response = await client.post(url, json=data)

# Or if you must use requests:
from asgiref.sync import sync_to_async
response = await sync_to_async(requests.post)(url, json=data)
```

## 10. Don't Use json.loads — Use orjson.loads

```python
# WRONG — slower
import json
data = json.loads(request.body)

# CORRECT — 3-10x faster, always available
import orjson
data = orjson.loads(request.body)
```

## 11. Don't Cache Type Hints Per-Request

```python
# WRONG — introspection on every request
async def handle(self, request):
    hints = get_type_hints(self.endpoint)  # Expensive!

# CORRECT — cache at init/registration time
def __init__(self):
    self._hints = get_type_hints(self.endpoint)  # Once
```

## 12. Watch for Loop Closure Capture

```python
# WRONG — all wrapped methods share the same `method` variable
for method_name in methods:
    method = getattr(self, method_name)

    @wraps(method)
    async def wrapper(request):
        return await method(request)  # BUG: captures last method only!

# CORRECT — bind via default argument
for method_name in methods:
    method = getattr(self, method_name)

    @wraps(method)
    async def wrapper(request, _method=method):  # Bound at creation
        return await _method(request)
```

## 13. Don't Use DRF Serializers

```python
# WRONG — django-matt uses Pydantic, not DRF
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User

# CORRECT — use ModelSchema
from django_matt import ModelSchema

class UserSchema(ModelSchema):
    class Config:
        model = User
        include = ["id", "email", "username"]
```

## 14. Membership Model is "Membership", Not "OrganizationMembership"

```python
# WRONG
from django_matt.multitenancy.models import OrganizationMembership

# CORRECT
from django_matt.multitenancy.models import Membership
```

## 15. Don't Add External Auth Dependencies

Django Matt has built-in implementations for:
- JWT (HS256/HS384/HS512 built-in, RS256/ES256 with cryptography)
- Password hashing (uses Django's built-in hashers)
- Magic links
- RBAC
- API keys

Only add external deps when needed:
- `cryptography` — for RSA/EC JWT algorithms
- `authlib` — for OAuth provider flows
- `webauthn` — for passkey support
- `python3-saml` — for SAML SSO

## 16. Don't Use Global Middleware When Interceptors Suffice

```python
# WRONG — adding logging middleware that runs on EVERY request
MIDDLEWARE = [
    ...
    "myapp.middleware.AuditLogMiddleware",  # runs for health checks, static files, everything
]

# CORRECT — use interceptors for route-scoped concerns
from django_matt.interceptors import intercept, LoggingInterceptor

@get("/sensitive")
@intercept(LoggingInterceptor())
async def sensitive_endpoint(self, request):
    ...

# Or apply to an entire controller
@intercept_controller(LoggingInterceptor())
@api.controller("/admin", tags=["Admin"])
class AdminController(APIController):
    ...
```

## 17. Don't Put Business Logic in Interceptors

```python
# WRONG — interceptor doing domain work
class OrderValidationInterceptor(Interceptor):
    async def before_request(self, request, **kwargs):
        # Business logic doesn't belong here!
        order = await Order.objects.aget(id=request.data["order_id"])
        if order.total > 10000:
            await notify_compliance_team(order)
        return None

# CORRECT — interceptors handle cross-cutting concerns only
class TimingInterceptor(Interceptor):
    async def before_request(self, request, **kwargs):
        request._start_time = time.monotonic()
        return None

    async def after_response(self, request, response, **kwargs):
        elapsed = time.monotonic() - request._start_time
        response["X-Response-Time"] = f"{elapsed:.3f}s"
        return response

# Business logic goes in the controller or a service
```

## 18. Don't Use the Event Bus for Synchronous Workflows

```python
# WRONG — using events when you need the result immediately
bus = get_event_bus()
await bus.emit(ValidatePayment(order_id=order.id))
# Can't get the validation result back! Events are fire-and-forget.

# CORRECT — use CQRS commands for request/response workflows
from django_matt.cqrs import Command, get_command_bus

class ValidatePayment(Command):
    order_id: int

bus = get_command_bus()
result = await bus.dispatch(ValidatePayment(order_id=order.id))
# result is returned from the command handler
```

## 19. Don't Catch Exceptions in Controllers When Exception Filters Handle It

```python
# WRONG — redundant try/except that exception filters already cover
@post("/charge")
async def charge(self, request, body: ChargeSchema):
    try:
        result = await stripe.charge(body.amount)
        return {"ok": True}
    except stripe.CardError as e:
        return JsonResponse({"error": str(e)}, status=402)
    except stripe.RateLimitError as e:
        return JsonResponse({"error": "rate limited"}, status=429)

# CORRECT — register exception filters, keep controller clean
from django_matt.exceptions import register_global_filter

register_global_filter(StripeExceptionFilter())

@post("/charge")
async def charge(self, request, body: ChargeSchema):
    result = await stripe.charge(body.amount)
    return {"ok": True}
    # StripeExceptionFilter handles CardError, RateLimitError, etc.
```

## 20. Don't Mix CQRS Commands and Queries

```python
# WRONG — command that reads data
class GetAndUpdateUser(Command):
    user_id: int

# CORRECT — separate read and write
class GetUser(Query):        # read path
    user_id: int

class UpdateUser(Command):   # write path
    user_id: int
    name: str
```

## 21. Don't Use Celery When tasks_native Suffices

```python
# WRONG — adding Celery for simple background tasks
from celery import shared_task

@shared_task
def send_welcome_email(user_id):
    ...

# CORRECT — use the native task engine (no broker required for DB backend)
from django_matt.tasks_native import task, retry
from pydantic import BaseModel

class EmailPayload(BaseModel):
    user_id: int

@task(retry=retry.exponential(max_retries=3))
async def send_welcome_email(payload: EmailPayload):
    ...

# Enqueue
await send_welcome_email.delay(EmailPayload(user_id=1))
```

## 22. Don't Pass Unvalidated Dicts to Tasks

```python
# WRONG — untyped dict payload, validation fails silently
@task
async def process_order(data: dict):
    order_id = data["order_id"]  # KeyError at execution time

# CORRECT — Pydantic model validates at enqueue time (not at execution)
from pydantic import BaseModel

class OrderPayload(BaseModel):
    order_id: int
    user_id: int

@task
async def process_order(payload: OrderPayload):
    # payload is guaranteed valid — validated when .delay() was called
    ...
```

## 24. Don't Import Heavy Modules Eagerly in Slim Mode

```python
# WRONG — importing billing at module level when using slim mode
from django_matt.billing import StripeProvider  # loads entire billing module

# CORRECT — use lazy_import or check if module is enabled
from django_matt.loader import lazy_import
billing = lazy_import("django_matt.billing")

# Or check first
from django_matt.slim import is_module_enabled
if is_module_enabled("billing"):
    from django_matt.billing import StripeProvider
```

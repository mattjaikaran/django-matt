# Request Lifecycle

This guide traces the full journey of an HTTP request through a django-matt application, from the ASGI server to the JSON response returned to the client.

## Overview

```
Client Request
    |
    v
[1] ASGI Server (uvicorn / gunicorn+uvicorn)
    |
    v
[2] Django Middleware Stack
    |  - SecurityHeadersMiddleware
    |  - RequestIDMiddleware
    |  - CORSMiddleware
    |  - RequestLoggingMiddleware
    |  - TimingMiddleware
    |  - ErrorMiddleware
    |  - JWTAuthenticationMiddleware
    |  - DependencyInjectionMiddleware
    |  - EventBusMiddleware (attaches event context to request)
    |
    v
[3] DjangoMattAPI Router — URL resolution
    |
    v
[4] Route-Scoped Interceptors (before_request)
    |
    v
[5] Exception Filters — scoped error handling active from here
    |
    v
[6] Permission Check
    |
    v
[7] Dependency Injection — resolve Depends() parameters
    |
    v
[8] Request Validation — Pydantic schema (request body)
    |
    v
[9] Controller Method / ViewSet Handler
    |  (CQRS: Commands/Queries dispatched to their buses here)
    |  (Event Bus: domain events published after writes)
    |
    v
[10] Response Serialization — ModelSchema.from_orm_fast()
    |
    v
[11] Route-Scoped Interceptors (after_response)
    |
    v
[12] Django Middleware (response phase, reverse order)
    |
    v
Client Response
```

If an exception occurs at any stage, the error handling layers activate:

```
Exception raised at step [8-10]
    |
    v
[E1] ViewSet Hook: on_error
    |
    v
[E2] Route-scoped Exception Filters (@catch)
    |
    v
[E3] Controller-scoped Exception Filters
    |
    v
[E4] Global Exception Filter Registry
    |
    v
[E5] ErrorMiddleware — last resort, returns JSON error envelope
```

## Step-by-Step

### 1. ASGI Server

django-matt is async-first. Production deployments use:

```bash
gunicorn config.asgi:application --worker-class uvicorn.workers.UvicornWorker
```

The ASGI server receives the raw HTTP connection and passes it to Django's ASGI handler.

### 2. Django Middleware Stack

Middleware runs in order on the request, and in reverse order on the response. django-matt provides middleware that can be enabled via slim mode or explicit configuration:

| Middleware | Module | Purpose |
|-----------|--------|---------|
| `SecurityHeadersMiddleware` | security | HSTS, X-Content-Type-Options, etc. |
| `RequestIDMiddleware` | request_id | Adds X-Request-ID header |
| `CORSMiddleware` | cors | Cross-origin resource sharing |
| `RequestLoggingMiddleware` | logging | Structured request logging |
| `TimingMiddleware` | timing | Server-Timing header |
| `ErrorMiddleware` | core.errors | Catches unhandled exceptions, returns JSON |
| `JWTAuthenticationMiddleware` | auth | Decodes JWT, sets request.user |
| `DependencyInjectionMiddleware` | di | Creates per-request DI scope |

The `ErrorMiddleware` catches any exception that escapes all other layers. For API paths (`/api/...`), it returns a JSON error response. For non-API paths, it re-raises.

### 3. URL Resolution

`DjangoMattAPI` extends Django's URL resolver. When you register controllers or viewsets, their routes are compiled into Django URL patterns:

```python
api = DjangoMattAPI(prefix="/api")

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    ...

# Or with ViewSets
class ProductViewSet(APIViewSet):
    api = api
    model = Product
    ...
```

The router matches the incoming URL and dispatches to the appropriate handler.

### 4. Interceptors (Before)

Interceptors are route-scoped middleware. They run before and after the handler, scoped to specific controllers or routes rather than the entire application. The event bus context is available to interceptors via the request.

```python
from django_matt.interceptors import Interceptor, intercept

class AuditInterceptor(Interceptor):
    async def before_request(self, request, **kwargs):
        request._audit_start = time.monotonic()
        return None  # continue to handler

    async def after_response(self, request, response, **kwargs):
        duration = time.monotonic() - request._audit_start
        await log_audit(request, response, duration)
        return response

@intercept(AuditInterceptor)
class OrderController(APIController):
    ...
```

The `InterceptorChain` runs interceptors in `order` priority. If `before_request` returns an `HttpResponse`, the chain short-circuits and that response is returned immediately.

### 5. Permission Check

Permissions are checked before the handler executes. They are defined on the controller or viewset class, and can be overridden per-operation:

```python
class UserController(APIController):
    permission_classes = [IsAuthenticated]

class ProductViewSet(APIViewSet):
    permission_classes = [IsAuthenticated]
    _permission_overrides = {
        "list": [AllowAny],  # public listing
        "create": [IsAdmin],  # only admins can create
    }
```

Each permission class has a `has_permission(request, view)` method. If any returns `False`, a 403 (or custom status) response is returned.

### 6. Dependency Injection

Parameters with `Depends()` default values are resolved from the DI container:

```python
@api.get("/orders")
async def list_orders(
    self,
    request,
    order_service: OrderService = Depends(),
    user: User = CurrentUser(),
):
    ...
```

The `DependencyInjectionMiddleware` creates a scoped container per request. Scoped dependencies are created once per request and shared across all injections within that request.

### 7. Request Validation

For endpoints with a typed `data` parameter, the request body is parsed with orjson and validated against the Pydantic schema:

```python
@api.post("/")
async def create_user(self, request, data: UserCreateSchema) -> UserSchema:
    # data is already validated — a UserCreateSchema instance
    ...
```

If validation fails, a 422 response with field-level errors is returned before the handler runs.

### 9. Handler Execution

The controller method or view handler runs. For ViewSets, this is the `handle()` method on the view class (e.g., `ListView.handle()`, `CreateView.handle()`).

ViewSet handlers support lifecycle hooks:

```
before_list -> queryset retrieval -> after_list
before_create -> model creation -> after_create
before_update -> model update -> after_update
before_delete -> model deletion -> after_delete
```

Hooks can modify data in-flight. `StopHookChain` can short-circuit execution.

#### CQRS Bus Dispatch

When using the CQRS pattern, controllers dispatch commands and queries through their respective buses rather than calling services directly:

```python
from django_matt.cqrs import CommandBus, QueryBus

class OrderController(APIController):
    @api.post("/")
    async def create_order(self, request, data: OrderCreateSchema):
        command = CreateOrderCommand(**data.model_dump(), user_id=request.user.id)
        order = await CommandBus.dispatch(command)
        return order

    @api.get("/")
    async def list_orders(self, request):
        query = ListOrdersQuery(user_id=request.user.id)
        return await QueryBus.dispatch(query)
```

#### Event Bus Publishing

After write operations, domain events are published to the event bus. Subscribers handle side effects (notifications, analytics, webhooks) without coupling them to the handler:

```python
from django_matt.events import EventBus

async def after_create(self, request, instance):
    await EventBus.publish("order.created", {"order_id": instance.id})
    return instance
```

### 10. Response Serialization

Model instances are serialized using `ModelSchema`:

- **Single objects** (create, read, update): `serialize_single()` uses `from_orm_fast()` (no re-validation)
- **Lists**: `serialize_list()` uses `from_orm_fast()` per item
- **Rust fast path**: When Rust extensions are available and camelCase is enabled, list serialization uses the Rust JSON serializer for a single-pass rename + serialize

The response is wrapped in a `JsonResponse` (or raw `HttpResponse` for the Rust path).

### 11. Interceptors (After)

The `after_response` method of each interceptor runs in reverse order, receiving the response. Interceptors can modify or replace the response.

### 12. Response Middleware

Django middleware processes the response in reverse order (timing headers, CORS headers, logging, etc.), and the response is sent to the client.

## Error Flow

When an exception occurs during handler execution:

1. **ViewSet error hooks** (`on_error`) run first, for logging or cleanup
2. **The BoundView** catches specific exception types and maps them to HTTP responses:
   - `ValidationError` (Pydantic) -> 422
   - `DjangoValidationError` -> 422
   - `NotFoundAPIError` -> 404
   - `APIError` -> status from exception
   - `ValueError` -> 400
   - Anything else -> 500
3. **Exception Filters** (if attached via `@catch`) handle scoped errors
4. **ErrorMiddleware** is the final safety net for any exception that escapes everything else

The standard error envelope is:

```json
{
    "status": 400,
    "detail": "Human-readable message",
    "extra": null
}
```

For validation errors, `extra` contains field-level details:

```json
{
    "status": 422,
    "detail": "Validation error",
    "extra": [
        {"message": "field required", "key": "email", "source": "body"}
    ]
}
```

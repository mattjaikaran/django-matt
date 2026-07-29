# Best Practices

High-level patterns for building maintainable, performant django-matt applications.

---

## Project Structure

### One Model Per File

Keep models focused. One model per file makes it easy to find definitions and reduces merge conflicts.

```
myapp/
    models/
        __init__.py          # re-exports all models
        user.py              # User model
        organization.py      # Organization model
        membership.py        # Membership model
    controllers/
        __init__.py
        user_controller.py
        org_controller.py
    schemas/
        __init__.py
        user_schemas.py
        org_schemas.py
    services/
        __init__.py
        user_service.py
        org_service.py
```

### One Controller Per File

Each controller handles one resource. This keeps files under 200 lines and responsibilities clear.

```python
# controllers/user_controller.py
from django_matt.core import APIController
from django_matt.permissions import IsAuthenticated

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list_users(self, request):
        ...

    @api.get("/{user_id}")
    async def get_user(self, request, user_id: UUID):
        ...

    @api.post("/")
    async def create_user(self, request, data: UserCreateSchema):
        ...
```

### Separate Schemas from Models

Schemas define the API contract. Models define the database schema. Keep them in separate files even when they look similar -- they evolve independently.

```python
# schemas/user_schemas.py
from django_matt.core.schema import MattSchema

class UserSchema(MattSchema):
    id: UUID
    email: str
    name: str
    created_at: datetime

class UserCreateSchema(MattSchema):
    email: str
    name: str
    password: str

class UserUpdateSchema(MattSchema):
    name: str | None = None
    email: str | None = None
```

---

## Async-First Development

### Default to Async

Every handler, service method, and ORM call should be async. This is not optional -- it is the foundation of django-matt's concurrency model.

```python
# Correct
@api.get("/users")
async def list_users(request):
    users = [u async for u in User.objects.filter(is_active=True)]
    return {"users": [UserSchema.from_orm_fast(u).model_dump() for u in users]}

# Wrong: blocks the event loop
@api.get("/users")
def list_users(request):
    users = list(User.objects.filter(is_active=True))  # synchronous query
    return {"users": users}
```

### ORM Async Methods

| Sync (do not use in async handlers) | Async (use these) |
|---|---|
| `.get()` | `.aget()` |
| `.create()` | `.acreate()` |
| `.save()` | `.asave()` |
| `.delete()` | `.adelete()` |
| `.update()` | `.aupdate()` |
| `.count()` | `.acount()` |
| `.exists()` | `.aexists()` |
| `.aggregate()` | `.aaggregate()` |
| `list(qs)` | `[x async for x in qs]` |

### When You Must Call Sync Code

Use `sync_to_async` for third-party libraries that do not support async:

```python
from asgiref.sync import sync_to_async

@sync_to_async
def call_legacy_api(data):
    return legacy_client.send(data)  # blocking I/O

@api.post("/legacy")
async def handle(request, data: DataSchema):
    result = await call_legacy_api(data.model_dump())
    return {"result": result}
```

---

## Service Layer Patterns

### Extract Business Logic from Controllers

Controllers handle HTTP concerns (request parsing, response formatting). Services handle business logic and data access.

```python
# services/user_service.py
from django.contrib.auth import get_user_model

User = get_user_model()

class UserService:
    async def create_user(self, email: str, name: str, password: str) -> User:
        user = await User.objects.acreate(
            email=email,
            name=name,
        )
        await sync_to_async(user.set_password)(password)
        await user.asave()
        return user

    async def get_by_id(self, user_id: UUID) -> User:
        return await User.objects.aget(id=user_id)

    async def update_user(self, user_id: UUID, **kwargs) -> User:
        user = await User.objects.aget(id=user_id)
        for key, value in kwargs.items():
            if value is not None:
                setattr(user, key, value)
        await user.asave()
        return user
```

```python
# controllers/user_controller.py
@api.controller("/users", tags=["Users"])
class UserController(APIController):
    def __init__(self):
        self.service = UserService()

    @api.post("/")
    async def create_user(self, request, data: UserCreateSchema) -> UserSchema:
        user = await self.service.create_user(**data.model_dump())
        return UserSchema.from_orm_fast(user)
```

### Service Layer Benefits

- **Testable**: services can be tested without HTTP infrastructure
- **Reusable**: the same service works in controllers, management commands, background tasks, and WebSocket consumers
- **Single responsibility**: controllers handle HTTP, services handle logic

---

## Error Handling Patterns

### Use APIError for Expected Errors

```python
from django_matt.core.errors import APIError, NotFoundAPIError

class InsufficientFundsError(APIError):
    status_code = 402
    default_detail = "Insufficient funds"
    default_code = "insufficient_funds"

# In a service
async def process_payment(amount: Decimal, user_id: UUID):
    balance = await get_balance(user_id)
    if balance < amount:
        raise InsufficientFundsError(detail=f"Need {amount}, have {balance}")
```

### Exception Filters for Cross-Cutting Concerns

Register global filters for exception types that occur across many endpoints:

```python
from django_matt.exceptions.filters import ExceptionFilter
from django_matt.exceptions.decorators import register_global_filter

class DatabaseErrorFilter(ExceptionFilter):
    exception_types = (DatabaseError,)

    async def catch(self, exc, request):
        logger.error(f"Database error on {request.path}: {exc}")
        return JsonResponse(
            {"error": "database_error", "detail": "Service temporarily unavailable"},
            status=503,
        )

register_global_filter(DatabaseErrorFilter())
```

### Never Swallow Exceptions

```python
# Wrong: silently hides errors
try:
    await process_order(order_id)
except Exception:
    pass

# Correct: log and re-raise or return error response
try:
    await process_order(order_id)
except OrderError as e:
    logger.error(f"Order processing failed: {e}")
    raise APIError(detail=str(e), status_code=422)
```

### Structured Error Responses

Always return a consistent error shape:

```python
{
    "error": "validation_error",
    "detail": "Invalid input",
    "errors": [
        {"field": "email", "message": "Not a valid email address"}
    ]
}
```

---

## Testing Strategies

### Test Behavior, Not Implementation

```python
# Good: tests the API contract
@pytest.mark.asyncio
async def test_create_user(client):
    response = await client.post("/api/users/", json={
        "email": "test@example.com",
        "name": "Test User",
        "password": "securepass123",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data  # password not exposed

# Bad: tests implementation details
async def test_create_user(mocker):
    mock_save = mocker.patch("myapp.models.User.save")
    # ... tests that save was called with specific args
```

### Integration Tests Hit the Real DB

```python
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_user_workflow(async_client):
    # Create
    resp = await async_client.post("/api/users/", json=user_data)
    user_id = resp.json()["id"]

    # Read
    resp = await async_client.get(f"/api/users/{user_id}/")
    assert resp.status_code == 200

    # Update
    resp = await async_client.patch(f"/api/users/{user_id}/", json={"name": "Updated"})
    assert resp.json()["name"] == "Updated"

    # Delete
    resp = await async_client.delete(f"/api/users/{user_id}/")
    assert resp.status_code == 204
```

### Every Bug Fix Gets a Regression Test

Before fixing a bug, write a test that reproduces it. Then fix the bug and verify the test passes.

```python
@pytest.mark.asyncio
async def test_duplicate_email_returns_409(client):
    """Regression: creating user with duplicate email returned 500 instead of 409."""
    await client.post("/api/users/", json={"email": "dup@test.com", "name": "A", "password": "x"})
    resp = await client.post("/api/users/", json={"email": "dup@test.com", "name": "B", "password": "y"})
    assert resp.status_code == 409
```

### Use Factories for Test Data

```python
import factory
from myapp.models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.com")
    name = factory.Faker("name")
    is_active = True

# In tests
user = await sync_to_async(UserFactory.create)(is_active=False)
```

---

## Configuration Management

### Use the configure() Shorthand

```python
from django_matt.config import configure

configure(
    environment="production",
    auth="jwt",
    database="postgresql",
    cache="redis",
    middleware="production",
    throttle="100/hour",
    cors=["https://app.example.com"],
)
```

### Environment-Specific Settings

```python
# settings/base.py
from django_matt.config import configure

configure(
    auth="jwt",
    database="postgresql",
)

# settings/development.py
from settings.base import *

configure(
    environment="development",
    middleware="development",
    cors=True,
)

# settings/production.py
from settings.base import *

configure(
    environment="production",
    middleware="production",
    cache="redis",
    throttle="100/hour",
    cors=["https://app.example.com"],
)
```

### Slim Mode for Production

Only load what you use:

```python
DJANGO_MATT = {
    "SLIM_MODE": {
        "mode": "auto",
        "lazy_imports": True,
    },
}
```


## Project Structure Anti-Patterns

These are the most common mistakes that create unmaintainable Django Matt projects. Refer to the [Architecture guide](architecture.md) for the recommended modular structure.

### Monolithic Files

**WRONG** — a single `models.py` with 15 models:
```python
# blog/models.py — 3,000 lines, impossible to review
class Post(models.Model): ...
class Comment(models.Model): ...
class Tag(models.Model): ...
class Category(models.Model): ...
# ... 11 more models
```

**CORRECT** — one model per file in a `models/` package:
```
blog/models/
├── __init__.py      # re-exports all models
├── post.py          # ~40 lines
├── comment.py       # ~35 lines
├── tag.py           # ~25 lines
└── category.py      # ~30 lines
```

### Business Logic in Controllers

**WRONG** — controller doing domain validation, ORM, and side effects:
```python
@api.controller("/orders", tags=["Orders"])
class OrderController(APIController):
    @api.post("/")
    async def create_order(self, request, data: CreateOrderSchema):
        # Validation in controller — belongs in service
        pending = await Order.objects.filter(
            user=request.user, status="pending"
        ).acount()
        if pending >= 5:
            raise ValidationAPIError("Too many pending orders")

        # ORM + side effects in controller — belongs in service
        order = await Order.objects.acreate(user=request.user, **data.model_dump())
        for item in data.items:
            product = await Product.objects.aget(id=item.product_id)
            if product.stock < item.quantity:
                await order.adelete()
                raise ValidationAPIError(f"{product.name} out of stock")
            product.stock -= item.quantity
            await product.asave()

        await send_confirmation.delay(str(order.id))
        return order
```

**CORRECT** — thin controller delegates everything:
```python
@api.controller("/orders", tags=["Orders"])
class OrderController(APIController):
    def __init__(self):
        self.service = OrderService()

    @api.post("/")
    async def create_order(self, request, data: CreateOrderSchema):
        return await self.service.create_order(request.user, data)
```

### Not Scoping Queries to User

**WRONG** — returns everyone's data:
```python
@api.get("/")
async def list_items(self, request):
    return await Item.objects.all()  # INSECURE: returns all users' items
```

**CORRECT** — always filter by authenticated user:
```python
@api.get("/")
async def list_items(self, request):
    items = [i async for i in Item.objects.filter(created_by=request.user)]
    return items
```

### Missing __init__.py Exports

**WRONG** — empty `__init__.py` files:
```python
# blog/models/__init__.py is empty
# Results in: from blog.models import Post  →  ImportError
```

**CORRECT** — always export in `__init__.py`:
```python
# blog/models/__init__.py
from .post import Post
from .comment import Comment

__all__ = ["Post", "Comment"]
```

### Flat App Structure

**WRONG** — Django's default flat files don't scale:
```
myapp/
├── models.py      # 2,000 lines
├── views.py       # 1,500 lines
├── admin.py       # 600 lines
└── tests.py       # 3,000 lines
```

**CORRECT** — modular package structure scales indefinitely:
```
myapp/
├── models/
│   ├── __init__.py
│   └── post.py         # ~40 lines
├── controllers/
│   ├── __init__.py
│   └── post_controller.py
├── schemas/
│   ├── __init__.py
│   └── post_schema.py
├── services/
│   ├── __init__.py
│   └── post_service.py
└── tests/
    ├── test_post.py
    └── factories/
        └── post_factory.py
```

### Redeclaring Base Model Fields

**WRONG** — redeclaring fields the base model already provides:
```python
class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4)   # use AbstractBaseModel
    created_at = models.DateTimeField(auto_now_add=True)       # use AbstractBaseModel
    updated_at = models.DateTimeField(auto_now=True)           # use AbstractBaseModel
    title = models.CharField(max_length=200)
```

**CORRECT** — only declare your own fields:
```python
from django_matt.db import AbstractBaseModel

class Post(AbstractBaseModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
    # id, created_at, updated_at, is_active provided by AbstractBaseModel
```

---

## Code Organization Rules


1. **Controllers** are thin -- they parse requests, call services, format responses
2. **Services** contain business logic -- they are reusable across controllers, tasks, and commands
3. **Schemas** define the API contract -- separate from models, versioned independently
4. **Models** define database schema -- one per file, no business logic
5. **Interceptors** handle cross-cutting concerns per-route -- logging, caching, rate limiting
6. **Exception filters** handle error-to-response mapping globally
7. **Modules** package features for reuse -- config, lifecycle hooks, URLs, middleware

### Import Order

Follow ruff's import sorting (enforced by lint):

```python
# stdlib
from datetime import datetime
from uuid import UUID

# third-party
from django.db import models
from pydantic import BaseModel

# local
from django_matt.core import APIController
from myapp.services import UserService
```

### File Size Limits

- Controllers: under 200 lines
- Services: under 300 lines
- Schemas: under 150 lines
- Models: under 100 lines per model

If a file exceeds these limits, split it. Large files are a sign of mixed responsibilities.

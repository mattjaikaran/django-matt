# Controllers

This document provides a quick overview of controllers in django-matt. For detailed documentation, see [Core Controllers](./core/controllers.md).

## Quick Reference

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get, post, put, delete
from django_matt import DjangoMattAPI

api = DjangoMattAPI()

class UserController(APIController):
    """User management controller."""

    prefix = "/users"
    tags = ["Users"]

    @get("/")
    async def list(self, request):
        return [u async for u in User.objects.all()]

    @get("/<int:id>")
    async def get(self, request, id: int):
        return await User.objects.aget(id=id)

    @post("/")
    async def create(self, request, data: UserCreate):
        return await User.objects.acreate(**data.model_dump())

    @put("/<int:id>")
    async def update(self, request, id: int, data: UserUpdate):
        user = await User.objects.aget(id=id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(user, key, value)
        await user.asave()
        return user

    @delete("/<int:id>")
    async def delete(self, request, id: int):
        await User.objects.filter(id=id).adelete()
        return {"deleted": True}


api.register_controller(UserController)
```

## Service Layer Integration

Controllers should handle HTTP concerns only: parsing the request, checking permissions, calling services, and returning the response. Business logic — ORM queries, audit fields, validation rules, cross-model operations — belongs in a service class.

### Before: logic in the controller

```python
from django_matt.core.controller import APIController
from django_matt.core.router import post
from django_matt.core.errors import ValidationAPIError

class UserController(APIController):
    prefix = "/users"
    tags = ["Users"]

    @post("/")
    async def create(self, request, data: UserCreate):
        # ORM, audit, and business logic mixed into the endpoint
        if await User.objects.filter(email=data.email).aexists():
            raise ValidationAPIError("Email already in use", status_code=409)
        user = await User.objects.acreate(
            **data.model_dump(),
            created_by=request.user,
        )
        return user
```

### After: thin controller + service

```python
# users/services.py
from django_matt.services import CRUDService, ConflictError
from .models import User

class UserService(CRUDService["User"]):
    model = User

    async def create(self, data: dict, user=None) -> User:
        if await self.exists(email=data["email"]):
            raise ConflictError("Email already in use")
        return await super().create(data, user=user)


# users/controllers.py
from django_matt.core.controller import APIController
from django_matt.core.router import get, post, put, delete
from django_matt.core.errors import APIError
from django_matt.services import ConflictError
from .services import UserService

class UserController(APIController):
    prefix = "/users"
    tags = ["Users"]

    def __init__(self):
        self.service = UserService()
        super().__init__()   # super().__init__() must come last

    @get("/")
    async def list(self, request):
        items, total = await self.service.list()
        return {"items": items, "total": total}

    @post("/")
    async def create(self, request, data: UserCreate):
        try:
            return await self.service.create(data.model_dump(), user=request.user)
        except ConflictError as exc:
            raise APIError(exc.message, status_code=409, code="conflict")

    @get("/<int:id>")
    async def get(self, request, id: int):
        return await self.service.get(id)

    @put("/<int:id>")
    async def update(self, request, id: int, data: UserUpdate):
        return await self.service.update(id, data.model_dump(), user=request.user)

    @delete("/<int:id>")
    async def delete(self, request, id: int):
        await self.service.delete(id)
        return {"deleted": True}
```

### Service injection via `__init__`

Always construct the service in `__init__`, not inside the view method. The instance is created once per controller class registration and reused across requests.

```python
def __init__(self):
    self.service = ProductService()
    super().__init__()   # super().__init__() must come last
```

For tenant-scoped services that need a per-request value, construct them inside the view method:

```python
from django_matt.core.router import get

class ProductController(APIController):
    prefix = "/products"

    @get("/")
    async def list_products(self, request):
        service = ProductService(organization=request.auth.organization)
        items, total = await service.list()
        return {"items": items, "total": total}
```

### Full service layer reference

- [Service Layer Overview](./services/index.md) — why services, patterns, quick start
- [CRUDService API](./services/crud-service.md) — all method signatures and examples
- [BaseThirdPartyService](./services/third-party.md) — external API clients
- [Service Patterns](./services/patterns.md) — naming, structure, testing, anti-patterns

## Related Documentation

- [Core Controllers](./core/controllers.md) - Full controller documentation
- [Routing](./core/routing.md) - Route decorators and URL patterns
- [Schemas](./core/schemas.md) - Request/response schemas
- [Dependency Injection](./di/overview.md) - Injecting services into controllers
- [Permissions](./api/permissions.md) - Controller-level permissions

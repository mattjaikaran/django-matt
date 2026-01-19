# Controllers

This document provides a quick overview of controllers in django-matt. For detailed documentation, see [Core Controllers](./core/controllers.md).

## Quick Reference

```python
from django_matt.core import APIController
from django_matt import MattAPI

api = MattAPI()

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    """User management controller."""

    @api.get("/")
    async def list(self, request):
        return User.objects.all()

    @api.get("/{id}")
    async def get(self, request, id: int):
        return User.objects.get(id=id)

    @api.post("/")
    async def create(self, request, data: UserCreate):
        return User.objects.create(**data.dict())

    @api.put("/{id}")
    async def update(self, request, id: int, data: UserUpdate):
        user = User.objects.get(id=id)
        for key, value in data.dict(exclude_unset=True).items():
            setattr(user, key, value)
        user.save()
        return user

    @api.delete("/{id}")
    async def delete(self, request, id: int):
        User.objects.filter(id=id).delete()
        return {"deleted": True}
```

## Related Documentation

- [Core Controllers](./core/controllers.md) - Full controller documentation
- [Routing](./core/routing.md) - Route decorators and URL patterns
- [Schemas](./core/schemas.md) - Request/response schemas
- [Dependency Injection](./di/overview.md) - Injecting services into controllers
- [Permissions](./api/permissions.md) - Controller-level permissions

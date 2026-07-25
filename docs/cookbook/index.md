# Cookbook

The cookbook contains practical recipes and patterns for common tasks in django-matt.

## Recipes

<div class="grid cards" markdown>

-   :material-code-braces: **Common Patterns**

    ---

    Project structure, service layer, caching, error handling, and more.

    [:octicons-arrow-right-24: Common Patterns](common-patterns.md)

-   :material-shield-account: **Authentication**

    ---

    MFA, OAuth flows, rate limiting, token refresh, and API keys.

    [:octicons-arrow-right-24: Authentication Recipes](authentication.md)

-   :material-database: **Database**

    ---

    Query optimization, transactions, soft deletes, and audit logging.

    [:octicons-arrow-right-24: Database Recipes](database.md)

-   :material-test-tube: **Testing**

    ---

    API testing, mocking, fixtures, and performance testing.

    [:octicons-arrow-right-24: Testing Recipes](testing.md)

</div>

## Quick Reference

### Common Imports

```python
# Core
from django_matt import DjangoMattAPI, APIController, ModelSchema, Schema

# Authentication
from django_matt.auth import jwt_required, jwt_optional, create_token_pair

# Permissions
from django_matt import IsAuthenticated, IsAdmin, IsOwner, HasRole

# Views
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

# Errors
from django_matt.core.errors import NotFoundError, ValidationError, UnauthorizedError, ForbiddenError

# Performance
from django_matt.utils.performance import cache_response, optimize_queryset

# Testing
from django_matt.testing import APITestClient, UserFactory
```

### Common Patterns Cheat Sheet

```python
# Protected endpoint
@api.get("/me")
@jwt_required
async def get_me(request):
    return {"user": request.user.email}

# CRUD ViewSet
class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema
    list = ListView()
    create = CreateView(permission_classes=[IsAuthenticated])
    read = ReadView()
    update = UpdateView(permission_classes=[IsOwner])
    delete = DeleteView(permission_classes=[IsOwner])

# Error handling
try:
    product = await Product.objects.aget(id=product_id)
except Product.DoesNotExist:
    raise NotFoundError(f"Product {product_id} not found")

# Response caching
@api.get("/categories")
@cache_response(timeout=3600)
async def list_categories(request):
    return [c async for c in Category.objects.all()]

# Custom permission
class IsOwnerOrAdmin(BasePermission):
    async def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.owner_id == request.user.id
```

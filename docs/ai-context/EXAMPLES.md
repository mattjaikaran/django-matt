# Django Matt — Full Examples

> Complete, copy-paste-ready examples for common project patterns.

## Example 1: SaaS API with Auth

### Project Structure
```
myproject/
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── api.py
├── users/
│   ├── models.py
│   ├── schemas.py
│   └── controllers.py
├── products/
│   ├── models.py
│   ├── schemas.py
│   └── controllers.py
└── manage.py
```

### config/api.py
```python
from django_matt import MattAPI

api = MattAPI(
    title="My SaaS API",
    version="1.0.0",
    description="A SaaS application built with Django Matt",
)
```

### config/urls.py
```python
from django.contrib import admin
from django.urls import path
from config.api import api

# Import controllers so @api.controller() decorators execute
import users.controllers  # noqa: F401
import products.controllers  # noqa: F401

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
```

### config/settings.py (relevant parts)
```python
from datetime import timedelta

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users",
    "products",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_matt.auth.middleware.JWTAuthenticationMiddleware",
    "django_matt.core.errors.ErrorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

DJANGO_MATT_JWT = {
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
}
```

### users/models.py
```python
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    bio = models.TextField(blank=True, default="")
    avatar_url = models.URLField(blank=True, default="")
```

### users/schemas.py
```python
from django_matt import ModelSchema, Schema

class UserSchema(ModelSchema):
    class Config:
        model = "users.User"  # String ref avoids circular imports
        include = ["id", "email", "username", "bio", "avatar_url", "date_joined"]

class UserCreateSchema(Schema):
    email: str
    username: str
    password: str

class UserUpdateSchema(Schema):
    bio: str | None = None
    avatar_url: str | None = None

class LoginRequest(Schema):
    email: str
    password: str

class TokenResponse(Schema):
    access: str
    refresh: str
    user: UserSchema
```

### users/controllers.py
```python
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password

from django_matt import APIController, get, post, put
from django_matt.auth import jwt_required, create_token_pair
from django_matt.core.errors import APIError, NotFoundAPIError

from config.api import api
from users.schemas import LoginRequest, TokenResponse, UserCreateSchema, UserSchema, UserUpdateSchema

User = get_user_model()


@api.controller("/auth", tags=["Auth"])
class AuthController(APIController):

    @post("/register")
    async def register(self, request, body: UserCreateSchema):
        if await User.objects.filter(email=body.email).aexists():
            raise APIError("Email already registered", status_code=400)

        user = await User.objects.acreate(
            email=body.email,
            username=body.username,
            password=make_password(body.password),
        )
        tokens = create_token_pair(user)
        return TokenResponse(
            access=tokens.access,
            refresh=tokens.refresh,
            user=UserSchema.from_orm(user),
        )

    @post("/login")
    async def login(self, request, body: LoginRequest):
        try:
            user = await User.objects.aget(email=body.email)
        except User.DoesNotExist:
            raise APIError("Invalid credentials", status_code=401)

        if not check_password(body.password, user.password):
            raise APIError("Invalid credentials", status_code=401)

        tokens = create_token_pair(user)
        return TokenResponse(
            access=tokens.access,
            refresh=tokens.refresh,
            user=UserSchema.from_orm(user),
        )


@api.controller("/users", tags=["Users"])
class UserController(APIController):

    @get("/me")
    @jwt_required
    async def me(self, request):
        return UserSchema.from_orm(request.user)

    @put("/me")
    @jwt_required
    async def update_me(self, request, body: UserUpdateSchema):
        user = request.user
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await user.asave()
        return UserSchema.from_orm(user)

    @get("/{id}")
    async def get_user(self, request, id: int):
        try:
            user = await User.objects.aget(id=id)
        except User.DoesNotExist:
            raise NotFoundAPIError(message="User not found")
        return UserSchema.from_orm(user)
```

### products/models.py
```python
from django.conf import settings
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
```

### products/schemas.py
```python
from decimal import Decimal
from django_matt import ModelSchema, Schema

class ProductSchema(ModelSchema):
    class Config:
        model = "products.Product"
        include = ["id", "name", "description", "price", "is_active", "created_by_id", "created_at"]

class ProductCreateSchema(Schema):
    name: str
    description: str = ""
    price: Decimal
```

### products/controllers.py
```python
from django_matt import APIController, get, post, put, delete
from django_matt.auth import jwt_required
from django_matt.core.errors import NotFoundAPIError

from config.api import api
from products.models import Product
from products.schemas import ProductCreateSchema, ProductSchema


@api.controller("/products", tags=["Products"])
class ProductController(APIController):

    @get("/")
    async def list_products(self, request):
        products = [p async for p in Product.objects.filter(is_active=True)]
        return [ProductSchema.from_orm(p) for p in products]

    @get("/{id}")
    async def get_product(self, request, id: int):
        try:
            product = await Product.objects.aget(id=id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundAPIError(message="Product not found")
        return ProductSchema.from_orm(product)

    @post("/")
    @jwt_required
    async def create_product(self, request, body: ProductCreateSchema):
        product = await Product.objects.acreate(
            **body.model_dump(),
            created_by=request.user,
        )
        return ProductSchema.from_orm(product)

    @put("/{id}")
    @jwt_required
    async def update_product(self, request, id: int, body: ProductCreateSchema):
        try:
            product = await Product.objects.aget(id=id, created_by=request.user)
        except Product.DoesNotExist:
            raise NotFoundAPIError(message="Product not found")

        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(product, k, v)
        await product.asave()
        return ProductSchema.from_orm(product)

    @delete("/{id}")
    @jwt_required
    async def delete_product(self, request, id: int):
        try:
            product = await Product.objects.aget(id=id, created_by=request.user)
        except Product.DoesNotExist:
            raise NotFoundAPIError(message="Product not found")
        await product.adelete()
        return {"deleted": True}
```

---

## Example 2: ViewSet-Based CRUD (Minimal Code)

```python
from django_matt import MattAPI
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

api = MattAPI(title="Blog API")

class PostViewSet(APIViewSet):
    api = api
    model = Post
    default_response_schema = PostSchema
    default_request_schema = PostCreateSchema
    prefix = "posts"

    list = ListView()
    create = CreateView()
    read = ReadView()
    update = UpdateView()
    delete = DeleteView()

    async def before_create(self, request, data):
        data["author_id"] = request.user.id
        return data

    async def before_list(self, request, queryset):
        # Only show published posts to non-staff
        if not request.user.is_staff:
            return queryset.filter(is_published=True)
        return queryset
```

---

## Example 3: Multi-Tenant B2B

```python
from django_matt import APIController, get, post
from django_matt.auth import jwt_required
from django_matt.multitenancy.models import Organization, Membership

@api.controller("/orgs", tags=["Organizations"])
class OrgController(APIController):

    @get("/")
    @jwt_required
    async def list_orgs(self, request):
        memberships = [
            m async for m in
            Membership.objects.filter(user=request.user).select_related("organization")
        ]
        return [{"id": m.organization.id, "name": m.organization.name} for m in memberships]

    @post("/")
    @jwt_required
    async def create_org(self, request, body: OrgCreateSchema):
        org = await Organization.objects.acreate(
            name=body.name,
            slug=body.slug,
        )
        await Membership.objects.acreate(
            user=request.user,
            organization=org,
            role="owner",
        )
        return OrgSchema.from_orm(org)
```

---

## Example 4: Testing

```python
import pytest
from django.test import AsyncClient

import orjson


@pytest.mark.django_db
class TestProductAPI:

    async def test_list_products(self):
        client = AsyncClient()
        response = await client.get("/api/products/")
        assert response.status_code == 200
        data = orjson.loads(response.content)
        assert isinstance(data, list)

    async def test_create_product_requires_auth(self):
        client = AsyncClient()
        response = await client.post(
            "/api/products/",
            data=orjson.dumps({"name": "Test", "price": "9.99"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    async def test_create_product_authenticated(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = await User.objects.acreate(username="testuser", email="test@test.com")
        client = AsyncClient()
        client.force_login(user)

        response = await client.post(
            "/api/products/",
            data=orjson.dumps({"name": "Widget", "price": "19.99"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = orjson.loads(response.content)
        assert data["name"] == "Widget"
```

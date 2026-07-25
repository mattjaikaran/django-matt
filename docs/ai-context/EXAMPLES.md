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
from django_matt import DjangoMattAPI

api = DjangoMattAPI(
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
from django_matt import DjangoMattAPI
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

api = DjangoMattAPI(title="Blog API")

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

## Example 4: SSE Streaming with Interceptors

```python
from django_matt import APIController, post
from django_matt.auth import jwt_required
from django_matt.interceptors import intercept, TimingInterceptor, LoggingInterceptor
from django_matt.streaming import sse_response, SSEEvent
from django_matt.ai import get_provider, Message
from config.api import api


@api.controller("/ai", tags=["AI"])
class AIStreamController(APIController):

    @post("/chat")
    @jwt_required
    @intercept(TimingInterceptor(), LoggingInterceptor())
    async def stream_chat(self, request, body: dict):
        llm = get_provider("openai")

        async def generate():
            async for chunk in llm.stream([Message.user(body.get("message", ""))]):
                yield SSEEvent(data={"token": chunk.content}, event="token")
            yield SSEEvent(data={"done": True}, event="done")

        return sse_response(generate())
```

---

## Example 5: Event-Driven Order Processing

```python
# orders/events.py
from django_matt.events import Event, on, get_event_bus

class OrderPlaced(Event):
    order_id: int
    user_id: int
    total: float

class OrderShipped(Event):
    order_id: int
    tracking_number: str

@on("OrderPlaced")
async def send_order_confirmation(event: OrderPlaced):
    from django_matt.email import send_template_email
    await send_template_email(
        user_id=event.user_id,
        template="order_confirmation",
        context={"order_id": event.order_id, "total": event.total},
    )

@on("OrderPlaced")
async def reserve_inventory(event: OrderPlaced):
    from orders.services import reserve_stock
    await reserve_stock(order_id=event.order_id)


# orders/controllers.py
from django_matt import APIController, post
from django_matt.auth import jwt_required
from django_matt.events import get_event_bus
from config.api import api
from orders.events import OrderPlaced

@api.controller("/orders", tags=["Orders"])
class OrderController(APIController):

    @post("/")
    @jwt_required
    async def create_order(self, request, body: OrderCreateSchema):
        order = await Order.objects.acreate(
            user=request.user, **body.model_dump()
        )
        bus = get_event_bus()
        await bus.emit(OrderPlaced(
            order_id=order.id,
            user_id=request.user.id,
            total=float(order.total),
        ))
        return OrderSchema.from_orm(order)
```

---

## Example 6: CQRS with Command/Query Buses

```python
# products/commands.py
from django_matt.cqrs import Command, command_handler

class CreateProduct(Command):
    name: str
    price: float
    category_id: int

@command_handler(CreateProduct)
class CreateProductHandler:
    async def execute(self, command: CreateProduct) -> int:
        from products.models import Product
        product = await Product.objects.acreate(
            name=command.name,
            price=command.price,
            category_id=command.category_id,
        )
        return product.id


# products/queries.py
from django_matt.cqrs import Query, query_handler

class ListProducts(Query):
    category_id: int | None = None
    is_active: bool = True

@query_handler(ListProducts)
class ListProductsHandler:
    async def execute(self, query: ListProducts) -> list:
        from products.models import Product
        qs = Product.objects.filter(is_active=query.is_active)
        if query.category_id:
            qs = qs.filter(category_id=query.category_id)
        return [p async for p in qs]


# products/controllers.py
from django_matt import APIController, get, post
from django_matt.auth import jwt_required
from django_matt.cqrs import get_command_bus, get_query_bus
from config.api import api
from products.commands import CreateProduct
from products.queries import ListProducts

@api.controller("/products", tags=["Products"])
class ProductController(APIController):

    @post("/")
    @jwt_required
    async def create_product(self, request, body: ProductCreateSchema):
        bus = get_command_bus()
        product_id = await bus.dispatch(CreateProduct(**body.model_dump()))
        return {"id": product_id}

    @get("/")
    async def list_products(self, request, category_id: int | None = None):
        bus = get_query_bus()
        products = await bus.dispatch(ListProducts(category_id=category_id))
        return [ProductSchema.from_orm(p) for p in products]
```

---

## Example 7: Serialization Groups for Role-Based APIs

```python
from django_matt import Schema
from django_matt.serialization import Grouped, Secret, serialize_for

class UserDetailSchema(Schema):
    id: int
    username: str                              # always visible
    email: str = Grouped("admin", "self")      # visible to admin or self
    phone: str = Grouped("admin", "self")
    ssn: str = Secret()                        # only admin + internal
    role: str = Grouped("admin")
    created_at: str

# Admin sees all fields
@get("/admin/users")
@jwt_required
@with_roles("admin")
@serialize_for(groups=["admin"])
async def admin_list_users(self, request):
    users = [u async for u in User.objects.all()]
    return [UserDetailSchema.from_orm(u) for u in users]

# Public sees only ungrouped fields (id, username, created_at)
@get("/users")
@serialize_for(groups=["public"])
async def public_list_users(self, request):
    users = [u async for u in User.objects.all()]
    return [UserDetailSchema.from_orm(u) for u in users]
```

---

## Example 8: Exception Filters

```python
from django_matt.exceptions import ExceptionFilter, register_global_filter
from django.http import JsonResponse
import orjson

class PaymentExceptionFilter(ExceptionFilter):
    exception_types = (StripeError, PayPalError)
    order = 10

    async def catch(self, exc, request):
        if isinstance(exc, CardDeclinedError):
            return JsonResponse(
                {"error": "card_declined", "message": str(exc)},
                status=402,
            )
        return JsonResponse(
            {"error": "payment_error", "message": "Payment processing failed"},
            status=500,
        )

# Register once at app startup (e.g., in AppConfig.ready())
register_global_filter(PaymentExceptionFilter())

# Controller stays clean — no try/except needed
@api.controller("/billing", tags=["Billing"])
class BillingController(APIController):

    @post("/charge")
    @jwt_required
    async def charge(self, request, body: ChargeSchema):
        result = await stripe.charges.acreate(
            amount=body.amount,
            currency="usd",
            source=body.token,
        )
        return {"charge_id": result.id}
```

---

## Example 9: Native Background Tasks (Stage 17A)

```python
# tasks.py
from django_matt.tasks_native import task, periodic_task, retry
from django_matt.tasks_native.scheduling import crontab, every
from pydantic import BaseModel

# Typed payload — validated at enqueue time
class WelcomeEmailPayload(BaseModel):
    user_id: int
    email: str

class ReportPayload(BaseModel):
    org_id: int
    format: str = "pdf"

# One-off task with exponential backoff
@task(
    queue="email",
    retry=retry.exponential(max_retries=3, base_delay=2.0, max_delay=60.0),
    timeout=30,
)
async def send_welcome_email(payload: WelcomeEmailPayload) -> bool:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = await User.objects.aget(id=payload.user_id)
    return await deliver_email(user, template="welcome")

# Periodic task — daily at 8 AM UTC
@periodic_task(schedule=crontab(hour=8, minute=0))
async def send_daily_digest():
    active_users = [u async for u in User.objects.filter(is_active=True)]
    for user in active_users:
        await send_digest_email.delay(WelcomeEmailPayload(user_id=user.id, email=user.email))

# Interval task — every 15 minutes
@periodic_task(schedule=every(minutes=15))
async def refresh_analytics_cache():
    from django.core.cache import cache
    stats = await compute_aggregate_stats()
    cache.set("global_stats", stats, timeout=1800)


# controllers.py — enqueue from a controller
from django_matt import APIController, post
from django_matt.auth import jwt_required
from config.api import api
from .tasks import send_welcome_email, WelcomeEmailPayload

@api.controller("/users", tags=["Users"])
class UserController(APIController):

    @post("/register")
    async def register(self, request, body: RegisterSchema):
        user = await User.objects.acreate(**body.model_dump())
        # Payload validated here — invalid data raises ValidationError immediately
        await send_welcome_email.delay(
            WelcomeEmailPayload(user_id=user.id, email=user.email)
        )
        return UserSchema.from_orm(user)
```

---

## Example 10: Testing

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

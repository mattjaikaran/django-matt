# Common Patterns & Recipes

This cookbook contains common patterns, recipes, and best practices for building APIs with django-matt.

## Project Structure

### Recommended Structure for Medium-Large Projects

```
myproject/
    manage.py
    myproject/
        __init__.py
        settings.py
        urls.py
        asgi.py
        wsgi.py
    api/
        __init__.py
        main.py              # Main API instance
        dependencies.py      # Shared dependencies
        middleware.py        # Custom middleware
    apps/
        users/
            __init__.py
            models.py
            schemas.py
            controllers.py
            services.py
            tests/
                __init__.py
                test_controllers.py
                test_services.py
        products/
            ...
        orders/
            ...
    core/
        __init__.py
        exceptions.py        # Custom exceptions
        permissions.py       # Shared permissions
        pagination.py        # Custom pagination
```

### API Module Example

```python
# api/main.py
from django_matt import MattAPI

from apps.users.controllers import UserController
from apps.products.controllers import ProductController
from apps.orders.controllers import OrderController

api = MattAPI(
    title="My E-Commerce API",
    version="1.0.0",
    description="E-commerce platform API",
)

# Register all controllers
api.register_controllers(
    UserController,
    ProductController,
    OrderController,
)
```

## Authentication Patterns

### Multi-Auth Support

Support both JWT and API keys for different use cases:

```python
from django_matt import MattAPI
from django_matt.auth import jwt_required
from django_matt.auth.api_keys import api_key_required, api_key_or_jwt

api = MattAPI()

# JWT only (for user-facing endpoints)
@api.get("/me")
@jwt_required
async def get_current_user(request):
    return {"user": request.user.email}

# API key only (for service-to-service)
@api.get("/internal/stats")
@api_key_required
async def get_stats(request):
    return {"stats": "..."}

# Either JWT or API key
@api.get("/data")
@api_key_or_jwt
async def get_data(request):
    return {"data": "..."}
```

### Role-Based Access

```python
from django_matt import APIController, IsAuthenticated
from django_matt.auth import jwt_required
from django_matt.auth.rbac import HasRole, requires_role

@api.controller("/admin", tags=["Admin"])
class AdminController(APIController):
    permission_classes = [IsAuthenticated, HasRole("admin")]

    @api.get("/users")
    async def list_all_users(self):
        return [u async for u in User.objects.all()]

    @api.delete("/users/{user_id}")
    @requires_role("superadmin")
    async def delete_user(self, user_id: int):
        await User.objects.filter(id=user_id).adelete()
        return {"deleted": True}
```

### Custom Permission

```python
from django_matt.permissions import BasePermission

class IsOwnerOrAdmin(BasePermission):
    """Allow access if user owns the resource or is admin."""

    async def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return obj.owner_id == request.user.id


@api.put("/posts/{post_id}")
@jwt_required
async def update_post(request, post_id: int, data: PostUpdateSchema):
    post = await Post.objects.aget(id=post_id)

    # Check permission
    permission = IsOwnerOrAdmin()
    if not await permission.has_object_permission(request, None, post):
        raise ForbiddenError("You can only edit your own posts")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    await post.asave()

    return PostSchema.from_orm(post)
```

## Service Layer Pattern

Separate business logic from controllers:

```python
# apps/orders/services.py
from typing import List
from django.db import transaction
from .models import Order, OrderItem
from .schemas import OrderCreateSchema, OrderSchema

class OrderService:
    async def create_order(
        self,
        user_id: int,
        items: List[dict],
    ) -> Order:
        """Create an order with items."""
        async with transaction.atomic():
            order = await Order.objects.acreate(
                user_id=user_id,
                status="pending",
            )

            for item in items:
                await OrderItem.objects.acreate(
                    order=order,
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    price=item["price"],
                )

            # Calculate total
            order.total = sum(i["price"] * i["quantity"] for i in items)
            await order.asave()

        return order

    async def cancel_order(self, order_id: int, user_id: int) -> Order:
        """Cancel an order."""
        order = await Order.objects.aget(id=order_id, user_id=user_id)

        if order.status != "pending":
            raise ValueError("Only pending orders can be cancelled")

        order.status = "cancelled"
        await order.asave()

        return order
```

```python
# apps/orders/controllers.py
from django_matt import APIController, Depends
from .services import OrderService
from .schemas import OrderCreateSchema, OrderSchema

@api.controller("/orders", tags=["Orders"])
class OrderController(APIController):
    def __init__(self):
        self.service = OrderService()

    @api.post("/", response=OrderSchema)
    @jwt_required
    async def create_order(self, request, data: OrderCreateSchema):
        order = await self.service.create_order(
            user_id=request.user.id,
            items=data.items,
        )
        return OrderSchema.from_orm(order)

    @api.post("/{order_id}/cancel", response=OrderSchema)
    @jwt_required
    async def cancel_order(self, request, order_id: int):
        order = await self.service.cancel_order(
            order_id=order_id,
            user_id=request.user.id,
        )
        return OrderSchema.from_orm(order)
```

## Schema Patterns

### Separate Input/Output Schemas

```python
from django_matt import ModelSchema, Schema
from pydantic import EmailStr, field_validator

# Input schema - what the client sends
class UserCreateSchema(Schema):
    email: EmailStr
    username: str
    password: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        return v.lower()

# Output schema - what we return
class UserSchema(ModelSchema):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'created_at']

# Partial update schema
class UserUpdateSchema(Schema):
    email: EmailStr | None = None
    username: str | None = None
```

### Nested Schemas

```python
class AddressSchema(Schema):
    street: str
    city: str
    country: str
    postal_code: str

class UserWithAddressSchema(UserSchema):
    addresses: list[AddressSchema]

    @classmethod
    def from_orm(cls, user):
        addresses = [
            AddressSchema(
                street=a.street,
                city=a.city,
                country=a.country,
                postal_code=a.postal_code,
            )
            for a in user.addresses.all()
        ]
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            created_at=user.created_at,
            addresses=addresses,
        )
```

### Schema with Computed Fields

```python
from pydantic import computed_field

class ProductSchema(ModelSchema):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'discount_percent']

    @computed_field
    @property
    def discounted_price(self) -> float:
        return self.price * (1 - self.discount_percent / 100)

    @computed_field
    @property
    def display_price(self) -> str:
        return f"${self.discounted_price:.2f}"
```

## Pagination Patterns

### Custom Pagination

```python
from django_matt.pagination import BasePagination
from typing import Generic, TypeVar, List
from pydantic import BaseModel

T = TypeVar('T')

class CursorPaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: str | None
    prev_cursor: str | None
    has_more: bool

class CursorPagination(BasePagination):
    cursor_param = 'cursor'
    page_size = 20

    async def paginate(self, queryset, request):
        cursor = request.GET.get(self.cursor_param)

        if cursor:
            queryset = queryset.filter(id__lt=cursor)

        items = await queryset[:self.page_size + 1].alist()
        has_more = len(items) > self.page_size
        items = items[:self.page_size]

        return CursorPaginatedResponse(
            items=items,
            next_cursor=str(items[-1].id) if items and has_more else None,
            prev_cursor=cursor,
            has_more=has_more,
        )
```

### Infinite Scroll Pagination

```python
@api.get("/feed")
@jwt_required
async def get_feed(
    request,
    cursor: str | None = None,
    limit: int = 20,
):
    """Get paginated feed for infinite scroll."""
    queryset = Post.objects.filter(
        author__in=request.user.following.all()
    ).select_related('author').order_by('-created_at')

    if cursor:
        queryset = queryset.filter(created_at__lt=cursor)

    posts = await queryset[:limit + 1].alist()
    has_more = len(posts) > limit
    posts = posts[:limit]

    return {
        "posts": [PostSchema.from_orm(p) for p in posts],
        "next_cursor": posts[-1].created_at.isoformat() if posts and has_more else None,
        "has_more": has_more,
    }
```

## Filtering Patterns

### Complex Filtering

```python
from django_matt.filtering import FilterSet, CharFilter, NumberFilter, DateFilter

class ProductFilterSet(FilterSet):
    name = CharFilter(lookup='icontains')
    min_price = NumberFilter(field_name='price', lookup='gte')
    max_price = NumberFilter(field_name='price', lookup='lte')
    category = CharFilter(field_name='category__slug')
    created_after = DateFilter(field_name='created_at', lookup='gte')
    in_stock = NumberFilter(field_name='stock', lookup='gt', value=0)

    class Meta:
        model = Product


@api.get("/products")
async def list_products(request, filters: ProductFilterSet = Depends()):
    queryset = Product.objects.all()
    queryset = filters.apply(queryset)
    return [ProductSchema.from_orm(p) async for p in queryset]
```

### Search with Postgres Full-Text

```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

@api.get("/search")
async def search_products(request, q: str):
    """Full-text search with ranking."""
    search_vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
    search_query = SearchQuery(q)

    products = await Product.objects.annotate(
        search=search_vector,
        rank=SearchRank(search_vector, search_query),
    ).filter(
        search=search_query
    ).order_by('-rank')[:20].alist()

    return [ProductSchema.from_orm(p) for p in products]
```

## Caching Patterns

### Response Caching

```python
from django_matt.utils.performance import cache_response

@api.get("/categories")
@cache_response(timeout=3600)  # Cache for 1 hour
async def list_categories(request):
    """Categories rarely change, so we cache them."""
    categories = [c async for c in Category.objects.all()].alist()
    return [CategorySchema.from_orm(c) for c in categories]
```

### Query Caching with Cache Keys

```python
from django.core.cache import cache

@api.get("/products/{product_id}")
async def get_product(request, product_id: int):
    cache_key = f"product:{product_id}"

    # Try cache first
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Query database
    product = await Product.objects.select_related('category').aget(id=product_id)
    response = ProductDetailSchema.from_orm(product)

    # Cache for 5 minutes
    cache.set(cache_key, response, timeout=300)

    return response

@api.put("/products/{product_id}")
@jwt_required
async def update_product(request, product_id: int, data: ProductUpdateSchema):
    product = await Product.objects.aget(id=product_id)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await product.asave()

    # Invalidate cache
    cache.delete(f"product:{product_id}")

    return ProductDetailSchema.from_orm(product)
```

## Error Handling Patterns

### Custom Exception Handler

```python
from django_matt.core.errors import APIError

class InsufficientFundsError(APIError):
    status_code = 402
    default_message = "Insufficient funds"

class RateLimitExceededError(APIError):
    status_code = 429
    default_message = "Rate limit exceeded"

# Register handler
@api.exception_handler(InsufficientFundsError)
def handle_insufficient_funds(request, exc):
    return JsonResponse({
        "error": "insufficient_funds",
        "message": str(exc),
        "required_amount": exc.required_amount,
        "current_balance": exc.current_balance,
    }, status=402)
```

### Validation Error with Field Details

```python
from django_matt.core.errors import ValidationError

@api.post("/users")
async def create_user(request, data: UserCreateSchema):
    errors = []

    if await User.objects.filter(email=data.email).aexists():
        errors.append({"field": "email", "message": "Email already exists"})

    if await User.objects.filter(username=data.username).aexists():
        errors.append({"field": "username", "message": "Username already taken"})

    if errors:
        raise ValidationError("Validation failed", errors=errors)

    user = await User.objects.acreate_user(**data.model_dump())
    return UserSchema.from_orm(user)
```

## WebSocket Patterns

### Real-time Notifications

```python
from django_matt.websockets import JsonConsumer, broadcast

class NotificationConsumer(JsonConsumer):
    async def connect(self):
        await self.accept()
        # Join user's notification channel
        user_id = self.scope['user'].id
        await self.channel_layer.group_add(
            f"notifications_{user_id}",
            self.channel_name,
        )

    async def disconnect(self, close_code):
        user_id = self.scope['user'].id
        await self.channel_layer.group_discard(
            f"notifications_{user_id}",
            self.channel_name,
        )

    async def notification_message(self, event):
        await self.send_json(event['data'])


# Send notification from anywhere
async def send_notification(user_id: int, notification: dict):
    await broadcast(
        f"notifications_{user_id}",
        {
            "type": "notification_message",
            "data": notification,
        },
    )
```

### Chat Room Pattern

```python
from django_matt.websockets import RoomConsumer

class ChatConsumer(RoomConsumer):
    async def get_room_name(self) -> str:
        return f"chat_{self.scope['url_route']['kwargs']['room_id']}"

    async def receive_json(self, content):
        message = content.get('message')
        if message:
            await self.send_to_room({
                "type": "chat_message",
                "user": self.scope['user'].username,
                "message": message,
            })

    async def chat_message(self, event):
        await self.send_json({
            "user": event['user'],
            "message": event['message'],
        })
```

## Background Tasks Pattern

```python
from django_matt.tasks import task, schedule

@task
async def send_welcome_email(user_id: int):
    """Send welcome email to new user."""
    user = await User.objects.aget(id=user_id)
    # Send email...

@task
async def process_payment(order_id: int):
    """Process payment for order."""
    order = await Order.objects.aget(id=order_id)
    # Process payment...

# In controller
@api.post("/users", response=UserSchema)
async def create_user(request, data: UserCreateSchema):
    user = await User.objects.acreate_user(**data.model_dump())

    # Queue welcome email (non-blocking)
    await send_welcome_email.delay(user.id)

    return UserSchema.from_orm(user)
```

## Multi-Tenancy Pattern

```python
from django_matt.multitenancy import get_current_tenant, tenant_context

@api.get("/projects")
@jwt_required
async def list_projects(request):
    """List projects for current tenant."""
    tenant = get_current_tenant(request)
    projects = await Project.objects.filter(organization=tenant).alist()
    return [ProjectSchema.from_orm(p) for p in projects]

# Use context manager for explicit tenant
async def copy_template_to_tenant(template_id: int, target_org_id: int):
    async with tenant_context(target_org_id):
        template = await Template.objects.aget(id=template_id)
        await Project.objects.acreate(
            name=template.name,
            # ... organization is set automatically
        )
```

## Testing Patterns

### Controller Tests

```python
import pytest
from django_matt.testing import APITestClient
from django_matt.testing.factories import UserFactory

@pytest.fixture
def client():
    return APITestClient(api)

@pytest.fixture
def user():
    return UserFactory()

@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user)
    return client

class TestUserController:
    async def test_get_current_user(self, auth_client, user):
        response = await auth_client.get("/me")
        assert response.status_code == 200
        assert response.json()["email"] == user.email

    async def test_get_current_user_unauthenticated(self, client):
        response = await client.get("/me")
        assert response.status_code == 401

    async def test_update_user(self, auth_client, user):
        response = await auth_client.patch("/me", json={
            "username": "newusername"
        })
        assert response.status_code == 200
        assert response.json()["username"] == "newusername"
```

### Service Tests

```python
import pytest
from apps.orders.services import OrderService

@pytest.fixture
def order_service():
    return OrderService()

class TestOrderService:
    async def test_create_order(self, order_service, user, products):
        items = [
            {"product_id": products[0].id, "quantity": 2, "price": 10.00},
            {"product_id": products[1].id, "quantity": 1, "price": 25.00},
        ]

        order = await order_service.create_order(user.id, items)

        assert order.user_id == user.id
        assert order.status == "pending"
        assert order.total == 45.00

    async def test_cancel_pending_order(self, order_service, order):
        cancelled = await order_service.cancel_order(order.id, order.user_id)
        assert cancelled.status == "cancelled"

    async def test_cannot_cancel_shipped_order(self, order_service, shipped_order):
        with pytest.raises(ValueError, match="Only pending orders"):
            await order_service.cancel_order(
                shipped_order.id,
                shipped_order.user_id,
            )
```

## Next Steps

- [Authentication](../auth/overview.md) - Deep dive into auth patterns
- [Testing](../testing/client.md) - Testing best practices
- [Performance](../performance/optimization.md) - Optimization techniques

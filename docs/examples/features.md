# Feature Examples

## File Uploads

### Image Upload with Validation

```python
# file_upload.py
from django_matt import MattAPI
from django_matt.auth import jwt_required
from django_matt.core import Schema
from django_matt.core.errors import ValidationAPIError

from django.core.files.storage import default_storage
from PIL import Image
import uuid

api = MattAPI()

ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"]
MAX_SIZE = 5 * 1024 * 1024  # 5MB

@api.post("/upload/image", tags=["Uploads"])
@jwt_required
async def upload_image(request):
    """Upload an image file."""
    file = request.FILES.get("file")

    if not file:
        raise ValidationAPIError("No file provided")

    # Validate type
    if file.content_type not in ALLOWED_TYPES:
        raise ValidationAPIError(
            f"Invalid file type. Allowed: {', '.join(ALLOWED_TYPES)}"
        )

    # Validate size
    if file.size > MAX_SIZE:
        raise ValidationAPIError(f"File too large. Max size: {MAX_SIZE // 1024 // 1024}MB")

    # Generate unique filename
    ext = file.name.split(".")[-1]
    filename = f"uploads/{request.user.id}/{uuid.uuid4()}.{ext}"

    # Save file
    path = default_storage.save(filename, file)
    url = default_storage.url(path)

    # Get dimensions
    img = Image.open(file)
    width, height = img.size

    return {
        "url": url,
        "filename": filename,
        "size": file.size,
        "width": width,
        "height": height,
    }

@api.post("/upload/avatar", tags=["Uploads"])
@jwt_required
async def upload_avatar(request):
    """Upload and resize user avatar."""
    file = request.FILES.get("file")

    if not file:
        raise ValidationAPIError("No file provided")

    # Open and resize
    img = Image.open(file)
    img.thumbnail((200, 200))

    # Save
    filename = f"avatars/{request.user.id}.webp"
    path = default_storage.save(filename, img)

    # Update user
    request.user.avatar = path
    await request.user.asave()

    return {"url": default_storage.url(path)}
```

---

## Background Tasks

### Using Celery

```python
# tasks.py
from celery import shared_task
from django.core.mail import send_mail

@shared_task
def send_welcome_email(user_id: int):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user = User.objects.get(id=user_id)
    send_mail(
        subject="Welcome!",
        message=f"Hello {user.name}, welcome to our platform!",
        from_email="noreply@example.com",
        recipient_list=[user.email],
    )

@shared_task
def process_image(image_id: int):
    from .models import Image
    from PIL import Image as PILImage

    image = Image.objects.get(id=image_id)

    # Generate thumbnails
    img = PILImage.open(image.file.path)
    img.thumbnail((300, 300))
    # Save thumbnail...

    image.processed = True
    image.save()
```

```python
# api.py
from django_matt import MattAPI
from django_matt.auth import jwt_required
from .tasks import send_welcome_email, process_image

api = MattAPI()

@api.post("/users", tags=["Users"])
async def create_user(request, data: UserCreate):
    user = await User.objects.acreate(**data.dict())

    # Queue background task
    send_welcome_email.delay(user.id)

    return UserSchema.from_orm(user)

@api.post("/images", tags=["Images"])
@jwt_required
async def upload_image(request):
    file = request.FILES["file"]
    image = await Image.objects.acreate(
        user=request.user,
        file=file,
    )

    # Process in background
    process_image.delay(image.id)

    return {"id": image.id, "status": "processing"}
```

---

## Real-time WebSockets

### Chat Application

```python
# consumers.py
from django_matt.websockets import JsonConsumer, AuthenticatedConsumer
from django_matt.websockets.groups import broadcast, send_to_user

class ChatConsumer(AuthenticatedConsumer):
    """WebSocket consumer for chat rooms."""

    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group = f"chat_{self.room_id}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group,
            self.channel_name
        )
        await self.accept()

        # Notify others
        await broadcast(self.room_group, {
            "type": "user_joined",
            "user": self.scope["user"].email,
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group,
            self.channel_name
        )

    async def receive_json(self, content):
        message_type = content.get("type")

        if message_type == "chat_message":
            # Save message to database
            message = await Message.objects.acreate(
                room_id=self.room_id,
                user=self.scope["user"],
                content=content["message"],
            )

            # Broadcast to room
            await broadcast(self.room_group, {
                "type": "chat_message",
                "id": message.id,
                "user": self.scope["user"].email,
                "message": content["message"],
                "timestamp": message.created_at.isoformat(),
            })

    async def chat_message(self, event):
        """Handle chat_message events from group."""
        await self.send_json(event)

    async def user_joined(self, event):
        await self.send_json(event)
```

```python
# routing.py
from django.urls import path
from django_matt.websockets import WebSocketRouter
from .consumers import ChatConsumer

websocket_urlpatterns = [
    path("ws/chat/<int:room_id>/", ChatConsumer.as_asgi()),
]
```

```python
# asgi.py
from django_matt.websockets import create_asgi_application

application = create_asgi_application(
    django_application=get_asgi_application(),
    websocket_urlpatterns=websocket_urlpatterns,
)
```

---

## Multi-tenancy

### B2B SaaS with Organizations

```python
# api.py
from django_matt import MattAPI
from django_matt.multitenancy import (
    OrganizationController,
    TeamController,
    MembershipController,
    InvitationController,
)
from django_matt.multitenancy.middleware import TenantMiddleware

api = MattAPI()

# Register multi-tenancy controllers
api.register_controller(OrganizationController)
api.register_controller(TeamController)
api.register_controller(MembershipController)
api.register_controller(InvitationController)

# Add middleware in settings.py
MIDDLEWARE = [
    # ...
    "django_matt.multitenancy.middleware.TenantMiddleware",
]
```

```python
# Custom organization-scoped endpoints
from django_matt.multitenancy.permissions import IsOrganizationMember, IsOrganizationAdmin

@api.controller("/organizations/{org_id}/projects", tags=["Projects"])
class ProjectController(APIController):
    permission_classes = [IsOrganizationMember]

    @api.get("/")
    async def list(self, request, org_id: int):
        # request.organization is set by middleware
        projects = await Project.objects.filter(
            organization_id=org_id
        ).all()
        return {"projects": projects}

    @api.post("/")
    @IsOrganizationAdmin
    async def create(self, request, org_id: int, data: ProjectCreate):
        project = await Project.objects.acreate(
            organization_id=org_id,
            **data.dict()
        )
        return ProjectSchema.from_orm(project)
```

---

## Billing Integration

### Stripe Subscriptions

```python
# billing_api.py
from django_matt import MattAPI
from django_matt.billing import (
    BillingController,
    WebhookController,
    get_provider,
)
from django_matt.auth import jwt_required

api = MattAPI()

# Register billing controllers
api.register_controller(BillingController)
api.register_controller(WebhookController)

# Custom billing endpoints
@api.post("/billing/checkout", tags=["Billing"])
@jwt_required
async def create_checkout(request, price_id: str):
    """Create a Stripe checkout session."""
    provider = get_provider("stripe")

    session = await provider.create_checkout_session(
        price_id=price_id,
        customer_email=request.user.email,
        success_url="https://example.com/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://example.com/cancel",
        metadata={"user_id": str(request.user.id)},
    )

    return {"checkout_url": session.url}

@api.get("/billing/subscription", tags=["Billing"])
@jwt_required
async def get_subscription(request):
    """Get current user's subscription."""
    from django_matt.billing.models import Subscription

    subscription = await Subscription.objects.filter(
        customer__user=request.user,
        status__in=["active", "trialing"],
    ).select_related("price__product").afirst()

    if not subscription:
        return {"subscription": None}

    return {
        "subscription": {
            "id": subscription.id,
            "status": subscription.status,
            "plan": subscription.price.product.name,
            "current_period_end": subscription.current_period_end.isoformat(),
        }
    }

@api.post("/billing/portal", tags=["Billing"])
@jwt_required
async def create_portal(request):
    """Create Stripe billing portal session."""
    from django_matt.billing.models import BillingCustomer

    customer = await BillingCustomer.objects.filter(
        user=request.user
    ).afirst()

    if not customer:
        raise NotFoundAPIError("No billing account found")

    provider = get_provider("stripe")
    portal = await provider.create_billing_portal_session(
        customer_id=customer.provider_id,
        return_url="https://example.com/account",
    )

    return {"portal_url": portal.url}
```

```python
# settings.py
MATT_BILLING = {
    "default_provider": "stripe",
    "providers": {
        "stripe": {
            "api_key": os.environ["STRIPE_SECRET_KEY"],
            "webhook_secret": os.environ["STRIPE_WEBHOOK_SECRET"],
            "public_key": os.environ["STRIPE_PUBLIC_KEY"],
        },
    },
}
```

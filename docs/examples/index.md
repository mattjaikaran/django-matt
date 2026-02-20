# Code Examples

Practical examples for common use cases with django-matt.

## Quick Links

| Example | Description |
|---------|-------------|
| [Basic CRUD API](#basic-crud-api) | Simple REST API with CRUD operations |
| [Authentication](#authentication-examples) | JWT, OAuth, and Passkeys |
| [File Uploads](#file-uploads) | Handling file uploads |
| [Background Tasks](#background-tasks) | Async task processing |
| [Real-time Updates](#real-time-websockets) | WebSocket integration |
| [Multi-tenancy](#multi-tenancy) | B2B with organizations |
| [Billing Integration](#billing-integration) | Stripe subscriptions |

---

## Basic CRUD API

### Simple Blog API

```python
# models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
```

```python
# schemas.py
from django_matt.core import ModelSchema
from .models import Post

class PostSchema(ModelSchema):
    class Meta:
        model = Post
        fields = ["id", "title", "slug", "content", "author_id", "published", "created_at"]

class PostCreate(ModelSchema):
    class Meta:
        model = Post
        fields = ["title", "content"]

class PostUpdate(ModelSchema):
    class Meta:
        model = Post
        fields = ["title", "content", "published"]
        fields_optional = "__all__"
```

```python
# api.py
from django_matt import MattAPI
from django_matt.core import CRUDController
from django_matt.permissions import IsAuthenticated, IsOwner
from django_matt.auth import jwt_required

from .models import Post
from .schemas import PostSchema, PostCreate, PostUpdate

api = MattAPI(title="Blog API", version="1.0.0")

@api.controller("/posts", tags=["Posts"])
class PostController(CRUDController):
    model = Post
    schema = PostSchema
    create_schema = PostCreate
    update_schema = PostUpdate

    # Public list, authenticated create
    permission_classes = []

    def get_queryset(self, request):
        qs = Post.objects.select_related("author")
        if not request.user.is_authenticated:
            qs = qs.filter(published=True)
        return qs

    @api.post("/")
    @jwt_required
    async def create(self, request, data: PostCreate):
        from django.utils.text import slugify
        post = await Post.objects.acreate(
            author=request.user,
            slug=slugify(data.title),
            **data.dict()
        )
        return PostSchema.from_orm(post)

    @api.put("/{id}")
    @jwt_required
    @IsOwner(owner_field="author_id")
    async def update(self, request, id: int, data: PostUpdate):
        post = await self.get_object(id)
        for key, value in data.dict(exclude_unset=True).items():
            setattr(post, key, value)
        await post.asave()
        return PostSchema.from_orm(post)

    @api.delete("/{id}")
    @jwt_required
    @IsOwner(owner_field="author_id")
    async def delete(self, request, id: int):
        post = await self.get_object(id)
        await post.adelete()
        return {"success": True}
```

---

## Authentication Examples

### Complete Auth Flow with JWT

```python
# auth_api.py
from django_matt import MattAPI
from django_matt.auth import jwt_required, create_token_pair
from django_matt.auth.schemas import RefreshTokenRequest
from django_matt.core import Schema
from django_matt.core.errors import AuthenticationAPIError, ValidationAPIError

from django.contrib.auth import authenticate, get_user_model
from pydantic import EmailStr, field_validator

User = get_user_model()
api = MattAPI(title="Auth API")

class RegisterSchema(Schema):
    email: EmailStr
    password: str
    password_confirm: str
    name: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

class LoginSchema(Schema):
    email: EmailStr
    password: str

class TokenResponse(Schema):
    access: str
    refresh: str
    user: dict

@api.post("/auth/register", tags=["Auth"])
async def register(request, data: RegisterSchema):
    """Register a new user."""
    if data.password != data.password_confirm:
        raise ValidationAPIError(
            message="Passwords don't match",
            errors={"password_confirm": ["Passwords don't match"]}
        )

    if await User.objects.filter(email=data.email).aexists():
        raise ValidationAPIError(
            message="Email already registered",
            errors={"email": ["Email already registered"]}
        )

    user = await User.objects.acreate_user(
        email=data.email,
        password=data.password,
        name=data.name,
    )

    tokens = create_token_pair(user)
    return TokenResponse(
        access=tokens.access_token,
        refresh=tokens.refresh_token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )

@api.post("/auth/login", tags=["Auth"])
async def login(request, data: LoginSchema):
    """Login with email and password."""
    user = await User.objects.filter(email=data.email).afirst()

    if not user or not user.check_password(data.password):
        raise AuthenticationAPIError("Invalid email or password")

    if not user.is_active:
        raise AuthenticationAPIError("Account is disabled")

    tokens = create_token_pair(user)
    return TokenResponse(
        access=tokens.access_token,
        refresh=tokens.refresh_token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )

@api.post("/auth/refresh", tags=["Auth"])
async def refresh(request, data: RefreshTokenRequest):
    """Refresh access token."""
    from django_matt.auth import async_refresh_tokens
    try:
        tokens = await async_refresh_tokens(data.refresh_token)
        return {"access": tokens.access_token}
    except Exception:
        raise AuthenticationAPIError("Invalid refresh token")

@api.get("/auth/me", tags=["Auth"])
@jwt_required
async def me(request):
    """Get current user profile."""
    user = request.user
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": user.date_joined.isoformat(),
    }

@api.post("/auth/logout", tags=["Auth"])
@jwt_required
async def logout(request):
    """Logout (client should discard tokens)."""
    # Optionally blacklist the token
    return {"success": True}
```

### OAuth Social Login

```python
# oauth_example.py
from django_matt import MattAPI
from django_matt.auth.oauth import (
    OAuthController,
    GoogleOAuthProvider,
    GitHubOAuthProvider,
)

api = MattAPI()

# Register OAuth controller (provides /oauth/* endpoints)
api.register_controller(OAuthController)

# Configure in settings.py
"""
MATT_OAUTH = {
    "google": {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": "http://localhost:8000/auth/oauth/google/callback",
    },
    "github": {
        "client_id": os.environ["GITHUB_CLIENT_ID"],
        "client_secret": os.environ["GITHUB_CLIENT_SECRET"],
        "redirect_uri": "http://localhost:8000/auth/oauth/github/callback",
    },
}
"""

# Frontend usage:
# 1. Redirect user to: GET /auth/oauth/google/authorize
# 2. User authorizes on Google
# 3. Google redirects to: /auth/oauth/google/callback?code=...
# 4. Backend exchanges code for tokens and creates/logs in user
# 5. Backend redirects to frontend with JWT tokens
```

### Passkey/WebAuthn Authentication

```python
# passkey_example.py
from django_matt import MattAPI
from django_matt.auth.passkeys import PasskeyController

api = MattAPI()

# Register passkey controller
api.register_controller(PasskeyController)

# Endpoints provided:
# POST /auth/passkeys/register/options - Get WebAuthn registration options
# POST /auth/passkeys/register/verify  - Complete registration
# POST /auth/passkeys/authenticate/options - Get authentication options
# POST /auth/passkeys/authenticate/verify  - Complete authentication

# Frontend example (using @simplewebauthn/browser):
"""
import { startRegistration, startAuthentication } from '@simplewebauthn/browser';

// Registration
async function registerPasskey() {
  // 1. Get options from server
  const optionsRes = await fetch('/auth/passkeys/register/options', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
  });
  const options = await optionsRes.json();

  // 2. Create credential
  const credential = await startRegistration(options);

  // 3. Verify with server
  const verifyRes = await fetch('/auth/passkeys/register/verify', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(credential),
  });

  return verifyRes.json();
}

// Authentication
async function loginWithPasskey(email) {
  // 1. Get options
  const optionsRes = await fetch('/auth/passkeys/authenticate/options', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  const options = await optionsRes.json();

  // 2. Get assertion
  const credential = await startAuthentication(options);

  // 3. Verify
  const verifyRes = await fetch('/auth/passkeys/authenticate/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credential),
  });

  return verifyRes.json(); // Returns JWT tokens
}
"""
```

---

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

---

## Complete Example: Task Management API

A full example combining multiple features:

```python
# models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    organization = models.ForeignKey("Organization", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

```python
# schemas.py
from django_matt.core import ModelSchema, Schema
from pydantic import Field
from typing import Optional
from datetime import date
from .models import Task, Project

class TaskSchema(ModelSchema):
    class Meta:
        model = Task
        fields = ["id", "title", "description", "status", "project_id",
                  "assignee_id", "due_date", "created_at", "updated_at"]

class TaskCreate(Schema):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    project_id: int
    assignee_id: Optional[int] = None
    due_date: Optional[date] = None

class TaskUpdate(Schema):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    assignee_id: Optional[int] = None
    due_date: Optional[date] = None

class ProjectSchema(ModelSchema):
    task_count: int = 0

    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_at"]
```

```python
# api.py
from django_matt import MattAPI
from django_matt.core import APIController
from django_matt.auth import jwt_required
from django_matt.permissions import IsAuthenticated
from django_matt.core.errors import NotFoundAPIError, PermissionDeniedAPIError
from django_matt.websockets.groups import broadcast

from .models import Task, Project
from .schemas import TaskSchema, TaskCreate, TaskUpdate, ProjectSchema

api = MattAPI(title="Task Management API", version="1.0.0")

@api.controller("/projects/{project_id}/tasks", tags=["Tasks"])
class TaskController(APIController):
    permission_classes = [IsAuthenticated]

    async def get_project(self, project_id: int, request):
        project = await Project.objects.filter(
            id=project_id,
            organization__members__user=request.user
        ).afirst()
        if not project:
            raise NotFoundAPIError("Project not found")
        return project

    @api.get("/")
    async def list(self, request, project_id: int, status: str = None):
        """List tasks in a project."""
        await self.get_project(project_id, request)

        qs = Task.objects.filter(project_id=project_id)
        if status:
            qs = qs.filter(status=status)

        tasks = await qs.select_related("assignee").all()
        return {"tasks": [TaskSchema.from_orm(t) for t in tasks]}

    @api.post("/")
    async def create(self, request, project_id: int, data: TaskCreate):
        """Create a new task."""
        project = await self.get_project(project_id, request)

        task = await Task.objects.acreate(
            project=project,
            **data.dict()
        )

        # Notify via WebSocket
        await broadcast(f"project_{project_id}", {
            "type": "task_created",
            "task": TaskSchema.from_orm(task).dict(),
        })

        return TaskSchema.from_orm(task)

    @api.get("/{task_id}")
    async def detail(self, request, project_id: int, task_id: int):
        """Get task details."""
        await self.get_project(project_id, request)

        task = await Task.objects.filter(
            id=task_id,
            project_id=project_id
        ).select_related("assignee").afirst()

        if not task:
            raise NotFoundAPIError("Task not found")

        return TaskSchema.from_orm(task)

    @api.patch("/{task_id}")
    async def update(self, request, project_id: int, task_id: int, data: TaskUpdate):
        """Update a task."""
        await self.get_project(project_id, request)

        task = await Task.objects.filter(
            id=task_id,
            project_id=project_id
        ).afirst()

        if not task:
            raise NotFoundAPIError("Task not found")

        for key, value in data.dict(exclude_unset=True).items():
            setattr(task, key, value)
        await task.asave()

        # Notify via WebSocket
        await broadcast(f"project_{project_id}", {
            "type": "task_updated",
            "task": TaskSchema.from_orm(task).dict(),
        })

        return TaskSchema.from_orm(task)

    @api.delete("/{task_id}")
    async def delete(self, request, project_id: int, task_id: int):
        """Delete a task."""
        await self.get_project(project_id, request)

        deleted, _ = await Task.objects.filter(
            id=task_id,
            project_id=project_id
        ).adelete()

        if not deleted:
            raise NotFoundAPIError("Task not found")

        # Notify via WebSocket
        await broadcast(f"project_{project_id}", {
            "type": "task_deleted",
            "task_id": task_id,
        })

        return {"success": True}

    @api.post("/{task_id}/assign")
    async def assign(self, request, project_id: int, task_id: int, assignee_id: int):
        """Assign a task to a user."""
        await self.get_project(project_id, request)

        task = await Task.objects.filter(
            id=task_id,
            project_id=project_id
        ).afirst()

        if not task:
            raise NotFoundAPIError("Task not found")

        task.assignee_id = assignee_id
        await task.asave()

        # Send notification to assignee
        from .tasks import send_task_assignment_notification
        send_task_assignment_notification.delay(task.id, assignee_id)

        return TaskSchema.from_orm(task)
```

```python
# urls.py
from django.urls import path
from .api import api

urlpatterns = [
    path("api/", api.urls),
]
```

This example demonstrates:
- CRUD operations with proper validation
- Organization-scoped access control
- Real-time WebSocket notifications
- Background task processing
- Comprehensive error handling

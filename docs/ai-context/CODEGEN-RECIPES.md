# Django Matt — Code Generation Recipes

> Step-by-step recipes for LLMs generating django-matt code. Each recipe is self-contained and copy-pasteable.

## Recipe 1: New App with Full CRUD

**Input**: Model name, fields, and relationships.

### Step 1: Model

```python
# myapp/models.py
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(
        "Category",
        on_delete=models.CASCADE,
        related_name="products",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "products"

    def __str__(self) -> str:
        return self.name
```

### Step 2: Schemas

```python
# myapp/schemas.py
from django_matt import ModelSchema, Schema
from decimal import Decimal

class ProductSchema(ModelSchema):
    class Config:
        model = Product
        include = ["id", "name", "description", "price", "category_id", "is_active", "created_at"]

class ProductCreateSchema(Schema):
    name: str
    description: str = ""
    price: Decimal
    category_id: int
    is_active: bool = True

class ProductUpdateSchema(Schema):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    category_id: int | None = None
    is_active: bool | None = None
```

### Step 3: Controller

```python
# myapp/controllers.py
from django_matt import APIController, get, post, put, delete
from django_matt.auth import jwt_required
from django_matt.core.errors import NotFoundAPIError
from config.api import api
from .models import Product
from .schemas import ProductSchema, ProductCreateSchema, ProductUpdateSchema

@api.controller("/products", tags=["Products"])
class ProductController(APIController):

    @get("/")
    async def list_products(self, request):
        products = [p async for p in Product.objects.select_related("category").all()]
        return [ProductSchema.from_orm(p) for p in products]

    @get("/{id}")
    async def get_product(self, request, id: int):
        try:
            product = await Product.objects.select_related("category").aget(id=id)
        except Product.DoesNotExist:
            raise NotFoundAPIError(message="Product not found")
        return ProductSchema.from_orm(product)

    @post("/")
    @jwt_required
    async def create_product(self, request, body: ProductCreateSchema):
        product = await Product.objects.acreate(**body.model_dump())
        return ProductSchema.from_orm(product)

    @put("/{id}")
    @jwt_required
    async def update_product(self, request, id: int, body: ProductUpdateSchema):
        try:
            product = await Product.objects.aget(id=id)
        except Product.DoesNotExist:
            raise NotFoundAPIError(message="Product not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        await product.asave()
        return ProductSchema.from_orm(product)

    @delete("/{id}")
    @jwt_required
    async def delete_product(self, request, id: int):
        try:
            product = await Product.objects.aget(id=id)
        except Product.DoesNotExist:
            raise NotFoundAPIError(message="Product not found")
        await product.adelete()
        return {"deleted": True}
```

### Step 4: URL Registration

```python
# config/urls.py
from django.urls import path
from config.api import api

import myapp.controllers  # noqa: F401

urlpatterns = [
    path("api/", api.urls),
]
```

### Step 5: Tests

```python
# tests/test_products.py
import pytest
import orjson
from django.test import AsyncClient
from myapp.models import Product, Category

@pytest.fixture
async def category(db):
    return await Category.objects.acreate(name="Electronics")

@pytest.fixture
async def product(db, category):
    return await Product.objects.acreate(
        name="Widget",
        price="9.99",
        category=category,
    )

@pytest.mark.django_db
async def test_list_products(product):
    client = AsyncClient()
    response = await client.get("/api/products/")
    assert response.status_code == 200
    data = orjson.loads(response.content)
    assert len(data) == 1
    assert data[0]["name"] == "Widget"

@pytest.mark.django_db
async def test_get_product(product):
    client = AsyncClient()
    response = await client.get(f"/api/products/{product.id}")
    assert response.status_code == 200
    data = orjson.loads(response.content)
    assert data["name"] == "Widget"

@pytest.mark.django_db
async def test_get_product_not_found():
    client = AsyncClient()
    response = await client.get("/api/products/99999")
    assert response.status_code == 404

@pytest.mark.django_db
async def test_create_product_requires_auth(category):
    client = AsyncClient()
    response = await client.post(
        "/api/products/",
        data=orjson.dumps({"name": "New", "price": "5.00", "category_id": category.id}),
        content_type="application/json",
    )
    assert response.status_code == 401

@pytest.mark.django_db
async def test_create_product_authenticated(category):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = await User.objects.acreate_user(username="testuser", password="pass")
    client = AsyncClient()
    client.force_login(user)
    response = await client.post(
        "/api/products/",
        data=orjson.dumps({"name": "New", "price": "5.00", "category_id": category.id}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = orjson.loads(response.content)
    assert data["name"] == "New"
```

---

## Recipe 2: ViewSet Alternative (Declarative CRUD)

When you want CRUD without writing each endpoint:

```python
# myapp/viewsets.py
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
from django_matt.auth import jwt_required
from config.api import api
from .models import Product
from .schemas import ProductSchema, ProductCreateSchema

class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema
    default_request_schema = ProductCreateSchema
    prefix = "products"
    permission_classes = []  # Public reads

    list = ListView()
    create = CreateView(permission_classes=[jwt_required])
    read = ReadView()
    update = UpdateView(permission_classes=[jwt_required])
    delete = DeleteView(permission_classes=[jwt_required])

    async def before_create(self, request, data):
        """Inject current user as creator."""
        data["created_by_id"] = request.user.id
        return data

    async def before_list(self, request, queryset):
        """Only show active products."""
        return queryset.filter(is_active=True)

    async def after_delete(self, request, instance):
        """Log deletion for audit."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Product {instance.id} deleted by {request.user.id}")
```

---

## Recipe 3: Auth Flow (Login + Register + Me)

```python
# accounts/schemas.py
from django_matt import Schema

class RegisterRequest(Schema):
    email: str
    username: str
    password: str

class LoginRequest(Schema):
    email: str
    password: str

class TokenResponse(Schema):
    access: str
    refresh: str

class UserResponse(Schema):
    id: int
    email: str
    username: str
```

```python
# accounts/controllers.py
from django_matt import APIController, get, post
from django_matt.auth import jwt_required, create_token_pair
from django_matt.core.errors import APIError, ValidationAPIError
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from config.api import api
from .schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse

User = get_user_model()

@api.controller("/auth", tags=["Auth"])
class AuthController(APIController):

    @post("/register")
    async def register(self, request, body: RegisterRequest):
        if await User.objects.filter(email=body.email).aexists():
            raise ValidationAPIError(message="Email already registered")
        user = await User.objects.acreate(
            email=body.email,
            username=body.username,
            password=make_password(body.password),
        )
        tokens = create_token_pair(user)
        return TokenResponse(**tokens)

    @post("/login")
    async def login(self, request, body: LoginRequest):
        try:
            user = await User.objects.aget(email=body.email)
        except User.DoesNotExist:
            raise APIError(message="Invalid credentials", status_code=401)
        if not check_password(body.password, user.password):
            raise APIError(message="Invalid credentials", status_code=401)
        tokens = create_token_pair(user)
        return TokenResponse(**tokens)

    @get("/me")
    @jwt_required
    async def me(self, request):
        return UserResponse.from_orm(request.user)
```

---

## Recipe 4: AI-Powered Endpoint

Add an LLM-powered endpoint to an existing controller:

```python
# myapp/controllers.py
from django_matt import APIController, post
from django_matt.auth import jwt_required
from django_matt.ai import get_provider, Message
from pydantic import BaseModel
from config.api import api

class SummaryResponse(BaseModel):
    summary: str
    key_points: list[str]
    sentiment: str

@api.controller("/ai", tags=["AI"])
class AIController(APIController):

    @post("/summarize")
    @jwt_required
    async def summarize(self, request, body: dict):
        llm = get_provider("openai")
        result = await llm.complete_structured(
            messages=[
                Message.system("Extract a summary, key points, and sentiment from the text."),
                Message.user(body.get("text", "")),
            ],
            response_model=SummaryResponse,
        )
        return result.model_dump()

    @post("/chat")
    @jwt_required
    async def chat(self, request, body: dict):
        llm = get_provider("anthropic")
        response = await llm.complete([
            Message.system("You are a helpful assistant for our product."),
            Message.user(body.get("message", "")),
        ])
        return {"reply": response.content}
```

### Streaming AI Endpoint

```python
from django.http import StreamingHttpResponse
from django_matt.ai import get_provider, Message, StreamingLLM

@api.controller("/ai", tags=["AI"])
class AIStreamController(APIController):

    @post("/stream")
    @jwt_required
    async def stream_chat(self, request, body: dict):
        llm = get_provider("openai")
        streaming = StreamingLLM(llm)

        async def event_stream():
            async for event in streaming.stream_sse(
                [Message.user(body.get("message", ""))]
            ):
                yield event

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
```

---

## Recipe 5: RAG Knowledge Base Endpoint

```python
from django_matt import APIController, post, get
from django_matt.auth import jwt_required
from django_matt.ai import (
    get_provider, OpenAIEmbeddings, PgVectorStore,
    RAGChain, RecursiveSplitter, Message,
)
from config.api import api

# Initialize once at module level
embedder = OpenAIEmbeddings()
store = PgVectorStore(
    embedding_provider=embedder,
    table_name="knowledge_embeddings",
)
splitter = RecursiveSplitter(chunk_size=1000, chunk_overlap=200)

@api.controller("/knowledge", tags=["Knowledge Base"])
class KnowledgeController(APIController):

    @post("/ingest")
    @jwt_required
    async def ingest_document(self, request, body: dict):
        """Split and embed a document into the knowledge base."""
        text = body.get("text", "")
        metadata = body.get("metadata", {})
        chunks = splitter.split(text)
        texts = [chunk.text for chunk in chunks]
        ids = await store.add_texts(texts, metadata=[metadata] * len(texts))
        return {"ingested": len(ids), "chunk_ids": [str(i) for i in ids]}

    @post("/query")
    @jwt_required
    async def query_knowledge(self, request, body: dict):
        """Ask a question against the knowledge base."""
        llm = get_provider("openai")
        rag = RAGChain(llm=llm, vector_store=store, k=5)
        response = await rag.query(body.get("question", ""))
        return {
            "answer": response.answer,
            "sources": [
                {"text": s.text[:200], "score": s.score}
                for s in response.sources
            ],
        }
```

---

## Recipe 6: Multi-Tenant B2B Setup

```python
from django_matt.multitenancy.models import Organization, Membership
from django_matt.multitenancy.middleware import TenantMiddleware

# settings.py
MIDDLEWARE = [
    ...
    "django_matt.multitenancy.middleware.TenantMiddleware",
    ...
]

# controllers.py
@api.controller("/orgs", tags=["Organizations"])
class OrgController(APIController):

    @get("/")
    @jwt_required
    async def list_orgs(self, request):
        """List organizations the user belongs to."""
        memberships = [
            m async for m in Membership.objects.filter(
                user=request.user
            ).select_related("organization")
        ]
        return [
            {
                "id": m.organization.id,
                "name": m.organization.name,
                "role": m.role,
            }
            for m in memberships
        ]

    @post("/")
    @jwt_required
    async def create_org(self, request, body: OrgCreateSchema):
        org = await Organization.objects.acreate(**body.model_dump())
        await Membership.objects.acreate(
            user=request.user,
            organization=org,
            role="owner",
        )
        return OrgSchema.from_orm(org)
```

---

## Recipe 7: WebSocket Real-Time

```python
from django_matt.websockets import AuthenticatedConsumer, websocket_route

class ChatConsumer(AuthenticatedConsumer):
    async def connect(self):
        self.room = self.scope["url_route"]["kwargs"]["room"]
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive_json(self, content):
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "chat.message",
                "message": content["message"],
                "user": self.scope["user"].username,
            },
        )

    async def chat_message(self, event):
        await self.send_json(event)

# routing.py
websocket_urlpatterns = [
    websocket_route(r"ws/chat/(?P<room>\w+)/$", ChatConsumer),
]
```

---

## Recipe 8: Background Task Integration

```python
from django_matt.tasks import shared_task, TaskConfig

@shared_task(config=TaskConfig(queue="default", retries=3))
async def send_welcome_email(user_id: int):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = await User.objects.aget(id=user_id)
    await send_email(
        to=user.email,
        template="welcome",
        context={"username": user.username},
    )

# In a controller
@post("/register")
async def register(self, request, body: RegisterRequest):
    user = await User.objects.acreate(**body.model_dump())
    await send_welcome_email.delay(user.id)
    return UserSchema.from_orm(user)
```

---

## Recipe 9: Feature Flags

```python
from django_matt.flags import flag_enabled, require_flag

# Check in code
if await flag_enabled("new_dashboard", user=request.user):
    return new_dashboard_data()

# Decorator
@get("/beta")
@jwt_required
@require_flag("beta_features")
async def beta_endpoint(self, request):
    return {"beta": True}
```

---

## Recipe 10: Generate AI Context for Your Project

```python
# Run from management command
python manage.py generate_ai_context --format all

# Or programmatically
from django_matt.ai.context import ContextGenerator

generator = ContextGenerator()
files = generator.generate_all()
# Creates: CLAUDE.md, .cursorrules, .copilot-instructions, introspection.json

# Watch mode for development
python manage.py generate_ai_context --watch
```

---

## Decision Guide: Controller vs ViewSet

| Use Case | Choice |
|---|---|
| Standard CRUD with minimal customization | **ViewSet** |
| Complex business logic per endpoint | **Controller** |
| Need lifecycle hooks (before_create, etc.) | **ViewSet** |
| Mixed auth per endpoint | **Controller** |
| Rapid prototyping | **ViewSet** |
| Non-CRUD endpoints (search, aggregate, AI) | **Controller** |
| Both CRUD and custom endpoints | **ViewSet** for CRUD + **Controller** for custom |

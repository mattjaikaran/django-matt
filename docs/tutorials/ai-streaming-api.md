# Build an AI/LLM Streaming API

Build a streaming AI chat endpoint with Server-Sent Events, CQRS
command/query separation, interceptors for logging and timing, and rate
limiting.

## Prerequisites

- Completed [Add Real-Time Features](realtime-features.md) tutorial
- An OpenAI API key (or Anthropic, Ollama, Groq, etc.)
- `uv add openai` (or the provider SDK you want to use)

## 1. Configure the AI Provider

Django Matt supports 10+ LLM providers through a unified interface.

```python
# settings.py
OPENAI_API_KEY = "sk-..."  # or set as env var
```

```python
# ai/providers.py
from django_matt.ai import OpenAIProvider, Message

llm = OpenAIProvider()  # Reads OPENAI_API_KEY from env

# Basic completion
response = await llm.complete([
    Message.system("You are a helpful assistant."),
    Message.user("What is Django?"),
])
print(response.content)

# Streaming
async for chunk in llm.stream([Message.user("Tell me a story")]):
    print(chunk.content, end="", flush=True)
```

### Other providers

```python
from django_matt.ai import (
    AnthropicProvider,   # ANTHROPIC_API_KEY
    OllamaProvider,      # Local, no key needed
    GroqProvider,        # GROQ_API_KEY (fast inference)
    PerplexityProvider,  # PERPLEXITY_API_KEY (search-augmented)
)

# Local LLM with Ollama
local_llm = OllamaProvider(model="llama3.2")

# Fast inference with Groq
fast_llm = GroqProvider()
```

## 2. Streaming SSE Endpoint

Combine the AI provider with `sse_response()` to stream tokens to the
client in real time:

```python
# ai/controllers.py
from django.http import HttpRequest
from django_matt.core.controller import Controller
from django_matt.auth import jwt_required
from django_matt.streaming import sse_response, event, SSEEvent
from django_matt.ai import OpenAIProvider, Message
from .api import api

llm = OpenAIProvider()


@api.controller("/ai", tags=["AI"])
class AIController(Controller):

    @api.post("/chat")
    @jwt_required
    async def chat_stream(self, request: HttpRequest, data: dict):
        """
        Stream an LLM response as Server-Sent Events.

        Request body:
            {"message": "What is Django?", "conversation_id": "optional-uuid"}

        SSE events:
            event: token    -> {"content": "partial text"}
            event: done     -> {"content": "full response", "usage": {...}}
            event: error    -> {"detail": "error message"}
        """
        user_message = data.get("message", "")
        conversation_id = data.get("conversation_id")

        messages = [
            Message.system("You are a helpful assistant."),
            Message.user(user_message),
        ]

        async def generate():
            full_response = ""
            try:
                async for chunk in llm.stream(messages):
                    if chunk.content:
                        full_response += chunk.content
                        yield event(
                            {"content": chunk.content},
                            event_type="token",
                        )

                yield event(
                    {"content": full_response},
                    event_type="done",
                )
            except Exception as e:
                yield event(
                    {"detail": str(e)},
                    event_type="error",
                )

        return sse_response(generate())
```

### Client-side consumption

```javascript
const response = await fetch("/api/ai/chat", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify({ message: "Explain async/await" }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop();

    for (const block of lines) {
        const eventMatch = block.match(/^event: (.+)$/m);
        const dataMatch = block.match(/^data: (.+)$/m);
        if (!eventMatch || !dataMatch) continue;

        const eventType = eventMatch[1];
        const data = JSON.parse(dataMatch[1]);

        if (eventType === "token") {
            appendToChat(data.content);
        } else if (eventType === "done") {
            finishChat(data.content);
        } else if (eventType === "error") {
            showError(data.detail);
        }
    }
}
```

## 3. CQRS for Chat History

Separate read and write operations using the command/query buses.

### Define commands and queries

```python
# ai/cqrs.py
from django_matt.cqrs import Command, Query


class SaveConversation(Command):
    """Write side: persist a conversation turn."""
    conversation_id: str
    user_id: int
    user_message: str
    assistant_message: str


class GetConversationHistory(Query):
    """Read side: fetch conversation history."""
    conversation_id: str
    user_id: int
    limit: int = 50
```

### Implement handlers

```python
# ai/handlers.py
from django_matt.cqrs import command_handler, query_handler, CommandHandler, QueryHandler
from .cqrs import SaveConversation, GetConversationHistory
from .models import Conversation, ConversationMessage


@command_handler(SaveConversation)
class SaveConversationHandler:
    async def execute(self, command: SaveConversation) -> str:
        conversation, _ = await Conversation.objects.aget_or_create(
            id=command.conversation_id,
            defaults={"user_id": command.user_id},
        )
        await ConversationMessage.objects.acreate(
            conversation=conversation,
            role="user",
            content=command.user_message,
        )
        msg = await ConversationMessage.objects.acreate(
            conversation=conversation,
            role="assistant",
            content=command.assistant_message,
        )
        return str(msg.id)


@query_handler(GetConversationHistory)
class GetConversationHistoryHandler:
    async def execute(self, query: GetConversationHistory) -> list[dict]:
        messages = []
        async for msg in ConversationMessage.objects.filter(
            conversation_id=query.conversation_id,
            conversation__user_id=query.user_id,
        ).order_by("created_at")[:query.limit]:
            messages.append({
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            })
        return messages
```

### Wire into the controller

```python
# ai/controllers.py (updated)
from django_matt.cqrs import get_command_bus, get_query_bus
from .cqrs import SaveConversation, GetConversationHistory

command_bus = get_command_bus()
query_bus = get_query_bus()


@api.controller("/ai", tags=["AI"])
class AIController(Controller):

    @api.post("/chat")
    @jwt_required
    async def chat_stream(self, request: HttpRequest, data: dict):
        user_message = data.get("message", "")
        conversation_id = data.get("conversation_id", str(uuid.uuid4()))

        # Load history for context
        history = await query_bus.dispatch(GetConversationHistory(
            conversation_id=conversation_id,
            user_id=request.user.id,
        ))

        messages = [Message.system("You are a helpful assistant.")]
        for msg in history:
            if msg["role"] == "user":
                messages.append(Message.user(msg["content"]))
            else:
                messages.append(Message.assistant(msg["content"]))
        messages.append(Message.user(user_message))

        async def generate():
            full_response = ""
            try:
                async for chunk in llm.stream(messages):
                    if chunk.content:
                        full_response += chunk.content
                        yield event(
                            {"content": chunk.content},
                            event_type="token",
                        )

                # Persist the conversation
                await command_bus.dispatch(SaveConversation(
                    conversation_id=conversation_id,
                    user_id=request.user.id,
                    user_message=user_message,
                    assistant_message=full_response,
                ))

                yield event(
                    {
                        "content": full_response,
                        "conversation_id": conversation_id,
                    },
                    event_type="done",
                )
            except Exception as e:
                yield event({"detail": str(e)}, event_type="error")

        return sse_response(generate())

    @api.get("/conversations/{conversation_id}")
    @jwt_required
    async def get_conversation(self, request: HttpRequest, conversation_id: str):
        messages = await query_bus.dispatch(GetConversationHistory(
            conversation_id=conversation_id,
            user_id=request.user.id,
        ))
        return {"conversation_id": conversation_id, "messages": messages}
```

### Bus middleware

Add logging and transaction middleware to the buses:

```python
# ai/bus_config.py
from django_matt.cqrs import (
    get_command_bus,
    get_query_bus,
    LoggingMiddleware,
    TransactionMiddleware,
    CachingMiddleware,
)

command_bus = get_command_bus()
command_bus.use(LoggingMiddleware())
command_bus.use(TransactionMiddleware())

query_bus = get_query_bus()
query_bus.use(LoggingMiddleware())
query_bus.use(CachingMiddleware(ttl=60))  # Cache queries for 60s
```

## 4. Interceptors for Logging and Timing

Interceptors are route-scoped middleware that run before/after specific
controller methods.

### Built-in interceptors

```python
from django_matt.interceptors import (
    Interceptor,            # Base class
    LoggingInterceptor,     # Structured request/response logging
    TimingInterceptor,      # X-Interceptor-Time header
    RateLimitInterceptor,   # Per-route rate limiting
    CachingInterceptor,     # Response caching
    RetryInterceptor,       # Retry on failure
    TransformInterceptor,   # Response transformation
)
```

### Apply interceptors to a controller

```python
from django_matt.interceptors import intercept, LoggingInterceptor, TimingInterceptor

@api.controller("/ai", tags=["AI"])
class AIController(Controller):
    middleware_classes = [
        LoggingInterceptor(log_body=True),
        TimingInterceptor(),
    ]

    @api.post("/chat")
    @jwt_required
    async def chat_stream(self, request, data: dict):
        ...
```

### Per-route interceptors with the decorator

```python
from django_matt.interceptors import intercept, TimingInterceptor

@api.controller("/ai", tags=["AI"])
class AIController(Controller):

    @api.post("/chat")
    @intercept(TimingInterceptor(), LoggingInterceptor(log_body=True))
    async def chat_stream(self, request, data: dict):
        ...

    @api.get("/models")
    @intercept(CachingInterceptor(ttl=300))
    async def list_models(self, request):
        """Cache model list for 5 minutes."""
        models = await llm.list_models()
        return {"models": models}
```

### Custom interceptor

```python
from django_matt.interceptors import Interceptor
from django.http import HttpRequest, HttpResponse, JsonResponse


class AIUsageInterceptor(Interceptor):
    """Track token usage per user."""

    order = 10  # Run after logging

    async def before_request(self, request: HttpRequest, **kwargs):
        request._ai_start_time = __import__("time").monotonic()
        return None  # continue processing

    async def after_response(self, request: HttpRequest, response: HttpResponse, **kwargs):
        import time
        duration = time.monotonic() - getattr(request, "_ai_start_time", 0)
        # Log usage metrics
        import logging
        logging.getLogger("ai.usage").info(
            "ai_request",
            extra={
                "user_id": getattr(request.user, "id", None),
                "duration_ms": f"{duration * 1000:.1f}",
                "path": request.path,
            },
        )
        return response

    async def on_error(self, request: HttpRequest, exc: Exception, **kwargs):
        import logging
        logging.getLogger("ai.usage").error(f"AI error: {exc}")
        return JsonResponse({"detail": "AI service error"}, status=503)
```

## 5. Rate Limiting

Protect your AI endpoints from abuse:

```python
from django_matt.throttling import throttle, UserRateThrottle

@api.controller("/ai", tags=["AI"])
class AIController(Controller):

    @api.post("/chat")
    @jwt_required
    @throttle(rate="30/hour")
    async def chat_stream(self, request, data: dict):
        """Limited to 30 requests per hour per user."""
        ...

    @api.post("/complete")
    @jwt_required
    @throttle(UserRateThrottle, rate="100/day")
    async def complete(self, request, data: dict):
        """Limited to 100 completions per day per user."""
        ...
```

### Tiered rate limits with API keys

```python
from django_matt.auth.api_keys import requires_plan

@api.post("/chat")
@requires_plan("pro")  # Only pro plan API keys
@throttle(rate="1000/hour")
async def chat_pro(self, request, data: dict):
    ...
```

## 6. Structured Output

Extract structured data from LLM responses using Pydantic models:

```python
from pydantic import BaseModel
from django_matt.ai import OpenAIProvider, Message

llm = OpenAIProvider()


class ExtractedEntity(BaseModel):
    name: str
    entity_type: str
    confidence: float


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity]
    summary: str


@api.post("/ai/extract")
@jwt_required
async def extract_entities(self, request, data: dict):
    result = await llm.complete_structured(
        messages=[
            Message.system("Extract entities from the text."),
            Message.user(data["text"]),
        ],
        response_model=ExtractionResult,
    )
    return result.model_dump()
```

## 7. RAG Pipeline

Combine vector search with LLM generation:

```python
from django_matt.ai import (
    OpenAIProvider,
    OpenAIEmbeddings,
    InMemoryVectorStore,
    RAGChain,
    Message,
)

llm = OpenAIProvider()
embedder = OpenAIEmbeddings()
store = InMemoryVectorStore(embedding_provider=embedder)


@api.post("/ai/index")
@jwt_required
async def index_documents(self, request, data: dict):
    """Index documents for RAG retrieval."""
    texts = data.get("texts", [])
    metadata = data.get("metadata", [{}] * len(texts))
    await store.add_texts(texts, metadatas=metadata)
    return {"indexed": len(texts)}


@api.post("/ai/ask")
@jwt_required
async def ask_with_context(self, request, data: dict):
    """Answer a question using RAG."""
    rag = RAGChain(llm=llm, vector_store=store)
    response = await rag.query(data["question"])
    return {
        "answer": response.answer,
        "sources": [
            {"text": s.text, "score": s.score}
            for s in response.sources
        ],
    }
```

## 8. Complete Code Listing

```python
# ai/models.py
import uuid
from django.conf import settings
from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ConversationMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20)  # "user", "assistant", "system"
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
```

```python
# ai/cqrs.py
from django_matt.cqrs import Command, Query


class SaveConversation(Command):
    conversation_id: str
    user_id: int
    user_message: str
    assistant_message: str


class GetConversationHistory(Query):
    conversation_id: str
    user_id: int
    limit: int = 50
```

```python
# ai/controllers.py
import uuid

from django.http import HttpRequest
from django_matt.core.controller import Controller
from django_matt.auth import jwt_required
from django_matt.streaming import sse_response, event
from django_matt.throttling import throttle
from django_matt.interceptors import intercept, LoggingInterceptor, TimingInterceptor
from django_matt.cqrs import get_command_bus, get_query_bus
from django_matt.ai import OpenAIProvider, Message
from .api import api
from .cqrs import SaveConversation, GetConversationHistory

llm = OpenAIProvider()
command_bus = get_command_bus()
query_bus = get_query_bus()


@api.controller("/ai", tags=["AI"])
class AIController(Controller):
    middleware_classes = [LoggingInterceptor(log_body=True), TimingInterceptor()]

    @api.post("/chat")
    @jwt_required
    @throttle(rate="30/hour")
    async def chat_stream(self, request: HttpRequest, data: dict):
        user_message = data.get("message", "")
        conversation_id = data.get("conversation_id", str(uuid.uuid4()))

        history = await query_bus.dispatch(GetConversationHistory(
            conversation_id=conversation_id,
            user_id=request.user.id,
        ))

        messages = [Message.system("You are a helpful assistant.")]
        for msg in history:
            if msg["role"] == "user":
                messages.append(Message.user(msg["content"]))
            else:
                messages.append(Message.assistant(msg["content"]))
        messages.append(Message.user(user_message))

        async def generate():
            full_response = ""
            try:
                async for chunk in llm.stream(messages):
                    if chunk.content:
                        full_response += chunk.content
                        yield event({"content": chunk.content}, event_type="token")

                await command_bus.dispatch(SaveConversation(
                    conversation_id=conversation_id,
                    user_id=request.user.id,
                    user_message=user_message,
                    assistant_message=full_response,
                ))

                yield event(
                    {"content": full_response, "conversation_id": conversation_id},
                    event_type="done",
                )
            except Exception as e:
                yield event({"detail": str(e)}, event_type="error")

        return sse_response(generate())

    @api.get("/conversations/{conversation_id}")
    @jwt_required
    async def get_conversation(self, request: HttpRequest, conversation_id: str):
        messages = await query_bus.dispatch(GetConversationHistory(
            conversation_id=conversation_id,
            user_id=request.user.id,
        ))
        return {"conversation_id": conversation_id, "messages": messages}
```

## Next Steps

- [Testing Your Django Matt App](testing-guide.md) -- test streaming endpoints
- [Build a Multi-Tenant SaaS API](build-a-saas-app.md) -- per-org AI usage billing
- [Add Real-Time Features](realtime-features.md) -- WebSocket-based chat with AI

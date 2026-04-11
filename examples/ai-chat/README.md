# AI Chat Example

AI-powered chat application demonstrating django-matt's SSE streaming, CQRS, and event bus.

## Features Demonstrated

- **SSE Streaming** — token-by-token AI responses via `sse_response()`
- **CQRS** — separate command/query buses for writes and reads
- **Event Bus** — async domain events (`chat.message.sent`, `chat.stream.complete`)
- **Controllers** — async API controller with typed schemas
- **ModelSchema** — Pydantic schemas derived from Django models

## Architecture

```
POST /conversations/              → CreateConversationCommand → CommandBus
GET  /conversations/              → GetConversationsQuery     → QueryBus
GET  /conversations/{id}/         → GetConversationQuery      → QueryBus
POST /conversations/{id}/messages → SendMessageCommand        → LLM → save
POST /conversations/{id}/stream   → SendMessageCommand        → LLM SSE stream
```

## Setup

```bash
cd examples/ai-chat

# Set your API key
export OPENAI_API_KEY=sk-...

# Run migrations
uv run python manage.py migrate

# Start the server
uv run uvicorn ai_chat_project.asgi:application --reload
```

## Usage

```bash
# Create a conversation
curl -X POST http://localhost:8000/conversations/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "system_prompt": "You are a pirate."}'

# Send a message (non-streaming)
curl -X POST http://localhost:8000/conversations/{id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Tell me a joke"}'

# Stream a response (SSE)
curl -N http://localhost:8000/conversations/{id}/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "Tell me a story"}'
```

## Key Files

| File | Purpose |
|------|---------|
| `api/controllers.py` | Main controller with SSE streaming endpoint |
| `chat/commands/` | CQRS commands (create conversation, send message) |
| `chat/queries/` | CQRS queries (list/get conversations) |
| `chat/events.py` | Event handlers (auto-title, analytics logging) |
| `chat/schemas.py` | Pydantic ModelSchema definitions |
| `chat/models.py` | Conversation and Message models |

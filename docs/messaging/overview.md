# Messaging System Overview

django-matt includes a full-featured real-time messaging system for building chat applications, support systems, and in-app communication.

## Features

- Direct and group conversations
- Message delivery tracking (sent, delivered, read)
- Typing indicators and presence
- File attachments
- Message reactions and threading
- WebSocket real-time delivery
- HTTP polling fallback

## Architecture

```mermaid
flowchart TB
    subgraph "Clients"
        WEB[Web Client]
        MOBILE[Mobile Client]
    end

    subgraph "Transport Layer"
        WS[WebSocket Consumer]
        POLL[Polling Controller]
    end

    subgraph "Service Layer"
        CONV[ConversationService]
        MSG[MessageService]
        PRES[PresenceService]
    end

    subgraph "Data Layer"
        CACHE[(Redis Cache)]
        DB[(PostgreSQL)]
    end

    WEB -->|WebSocket| WS
    WEB -->|HTTP| POLL
    MOBILE -->|WebSocket| WS
    MOBILE -->|HTTP| POLL

    WS --> CONV
    WS --> MSG
    WS --> PRES
    POLL --> CONV
    POLL --> MSG

    CONV --> DB
    MSG --> DB
    PRES --> CACHE
    MSG --> CACHE
```

## Data Model

```mermaid
erDiagram
    Conversation ||--o{ ConversationMember : has
    Conversation ||--o{ Message : contains
    User ||--o{ ConversationMember : participates
    User ||--o{ Message : sends
    Message ||--o{ MessageStatus : tracked_by
    Message ||--o{ MessageReaction : has
    Message ||--o{ Attachment : has
    Message ||--o| Message : replies_to

    Conversation {
        uuid id PK
        string type
        string name
        string avatar
        datetime created_at
    }

    ConversationMember {
        uuid id PK
        uuid conversation_id FK
        uuid user_id FK
        string role
        datetime joined_at
        json settings
    }

    Message {
        uuid id PK
        uuid conversation_id FK
        uuid sender_id FK
        uuid reply_to_id FK
        string type
        text content
        datetime created_at
        datetime deleted_at
    }

    MessageStatus {
        uuid id PK
        uuid message_id FK
        uuid user_id FK
        string status
        datetime timestamp
    }

    Attachment {
        uuid id PK
        uuid message_id FK
        string filename
        string content_type
        string url
        int size
    }
```

## Quick Start

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    'django_matt.messaging',
]
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Register Controllers

```python
from django_matt import DjangoMattAPI
from django_matt.messaging.controllers import (
    ConversationController,
    MessageController,
)

api = DjangoMattAPI()
api.register_controller(ConversationController)
api.register_controller(MessageController)
```

### 4. Configure WebSocket (Optional)

```python
# routing.py
from django_matt.messaging.realtime import MessagingConsumer

websocket_urlpatterns = [
    path("ws/messaging/", MessagingConsumer.as_asgi()),
]
```

## Related Documentation

- [Conversations](./conversations.md)
- [Messages](./messages.md)
- [Real-time](./realtime.md)
- [Attachments](./attachments.md)

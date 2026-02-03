# Real-Time Chat Application

A Slack-like real-time chat application showcasing django-matt WebSocket and messaging features.

## Features

- **Real-time messaging** - Live message delivery via WebSockets
- **Workspaces** - Multi-workspace support (like Slack workspaces)
- **Channels** - Public and private channels within workspaces
- **Direct Messages** - Private conversations between users
- **Presence** - Online/away/offline status tracking
- **Typing Indicators** - Real-time typing notifications
- **Read Receipts** - Track message read status
- **Message Threading** - Reply to messages in threads
- **Reactions** - Emoji reactions on messages
- **@Mentions** - Tag users in messages
- **File Attachments** - Upload and share files
- **Message Search** - Full-text search across messages

## Tech Stack

- **Backend**: Django 5.2+ with django-matt
- **WebSockets**: Django Channels with Redis
- **Authentication**: JWT tokens
- **Database**: PostgreSQL (SQLite for development)
- **Cache/Pub-Sub**: Redis
- **Frontend**: Simple HTML/JS demo client
- **Package Manager**: uv

## Project Structure

```
realtime-chat/
├── chat/                    # Django app
│   ├── models.py           # Chat models (Workspace, Channel, Message, etc.)
│   ├── schemas.py          # Pydantic schemas for API/WebSocket
│   ├── controllers.py      # REST API endpoints
│   ├── consumers.py        # WebSocket consumers
│   ├── services.py         # Business logic layer
│   └── routing.py          # WebSocket routing
├── config/
│   ├── settings.py         # Django settings
│   ├── urls.py             # URL configuration
│   └── asgi.py             # ASGI application with WebSocket support
├── templates/
│   └── chat/
│       └── index.html      # Demo frontend
├── static/
│   └── chat/
│       ├── chat.js         # WebSocket client
│       └── chat.css        # Styles
├── docker-compose.yml      # Docker services (Redis, PostgreSQL)
├── Dockerfile              # Container configuration
├── Makefile                # Development commands
├── pyproject.toml          # Python dependencies (uv)
└── README.md               # This file
```

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker and Docker Compose (for Redis)

### 1. Install uv (if not already installed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install Dependencies

```bash
# Using make
make install

# Or directly with uv
uv sync
```

### 3. Start Redis (required for WebSockets)

```bash
# Using Docker Compose
make docker-up

# Or start only Redis
docker-compose up -d redis

# Or install locally
# macOS: brew install redis && brew services start redis
# Ubuntu: sudo apt install redis-server && sudo systemctl start redis
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 5. Run Migrations

```bash
make migrate
```

### 6. Create Test User

```bash
make shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> User.objects.create_user('demo', 'demo@example.com', 'demo123')
```

### 7. Start Development Server

```bash
# Using Django development server
make dev

# Using Daphne (ASGI server, recommended for WebSockets)
make run-daphne

# Using Uvicorn
make run-uvicorn
```

### 8. Open the Demo

Visit http://localhost:8000/chat/ to see the demo application.

## Available Make Commands

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies with uv |
| `make dev` | Start Django development server |
| `make run-daphne` | Start with Daphne (WebSocket support) |
| `make run-uvicorn` | Start with Uvicorn (WebSocket support) |
| `make migrate` | Run database migrations |
| `make makemigrations` | Create new migrations |
| `make test` | Run tests |
| `make shell` | Open Django shell |
| `make createsuperuser` | Create admin user |
| `make collectstatic` | Collect static files |
| `make docker-up` | Start Docker services |
| `make docker-down` | Stop Docker services |
| `make setup` | Full setup (install + docker + migrate) |
| `make clean` | Remove compiled Python files |

## WebSocket Events

### Client to Server

| Event | Description | Payload |
|-------|-------------|---------|
| `message.send` | Send a new message | `{ channel_id, content, thread_id? }` |
| `message.update` | Edit a message | `{ message_id, content }` |
| `message.delete` | Delete a message | `{ message_id }` |
| `typing.start` | Start typing indicator | `{ channel_id }` |
| `typing.stop` | Stop typing indicator | `{ channel_id }` |
| `presence.update` | Update presence status | `{ status }` |
| `reaction.add` | Add emoji reaction | `{ message_id, emoji }` |
| `reaction.remove` | Remove emoji reaction | `{ message_id, emoji }` |
| `channel.join` | Join a channel | `{ channel_id }` |
| `channel.leave` | Leave current channel | `{}` |
| `read_receipt.mark` | Mark messages as read | `{ channel_id, message_id }` |

### Server to Client

| Event | Description | Payload |
|-------|-------------|---------|
| `message.new` | New message received | `{ message }` |
| `message.updated` | Message was edited | `{ message }` |
| `message.deleted` | Message was deleted | `{ message_id }` |
| `typing.update` | Typing indicator update | `{ channel_id, users }` |
| `presence.changed` | User presence changed | `{ user_id, status }` |
| `reaction.added` | Reaction added | `{ message_id, emoji, user_id }` |
| `reaction.removed` | Reaction removed | `{ message_id, emoji, user_id }` |
| `channel.joined` | Joined channel successfully | `{ channel }` |
| `channel.left` | Left channel | `{ channel_id }` |
| `read_receipt.updated` | Read receipts updated | `{ channel_id, receipts }` |
| `user.joined` | User joined channel | `{ user }` |
| `user.left` | User left channel | `{ user }` |

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login and get JWT tokens |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Get current user |

### Workspaces

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workspaces` | List user's workspaces |
| POST | `/api/workspaces` | Create workspace |
| GET | `/api/workspaces/{id}` | Get workspace details |
| PUT | `/api/workspaces/{id}` | Update workspace |
| DELETE | `/api/workspaces/{id}` | Delete workspace |
| POST | `/api/workspaces/{id}/invite` | Invite user to workspace |

### Channels

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workspaces/{id}/channels` | List channels |
| POST | `/api/workspaces/{id}/channels` | Create channel |
| GET | `/api/channels/{id}` | Get channel details |
| PUT | `/api/channels/{id}` | Update channel |
| DELETE | `/api/channels/{id}` | Delete channel |
| POST | `/api/channels/{id}/members` | Add member |
| DELETE | `/api/channels/{id}/members/{user_id}` | Remove member |

### Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/channels/{id}/messages` | List messages (paginated) |
| POST | `/api/channels/{id}/messages` | Send message |
| GET | `/api/messages/{id}` | Get message details |
| PUT | `/api/messages/{id}` | Edit message |
| DELETE | `/api/messages/{id}` | Delete message |
| GET | `/api/messages/{id}/thread` | Get thread replies |
| POST | `/api/messages/{id}/reactions` | Add reaction |
| DELETE | `/api/messages/{id}/reactions/{emoji}` | Remove reaction |

### Direct Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dm` | List DM conversations |
| POST | `/api/dm` | Start DM conversation |
| GET | `/api/dm/{id}/messages` | Get DM messages |
| POST | `/api/dm/{id}/messages` | Send DM |

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/search/messages` | Search messages |

### File Uploads

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/files/upload` | Upload file |
| GET | `/api/files/{id}` | Get file info |
| DELETE | `/api/files/{id}` | Delete file |

## WebSocket Connection

### Connecting

```javascript
// Get JWT token from login
const token = await login('user@example.com', 'password');

// Connect to WebSocket with token
const ws = new WebSocket(`ws://localhost:8000/ws/chat/?token=${token}`);

ws.onopen = () => {
    console.log('Connected!');

    // Join a channel
    ws.send(JSON.stringify({
        type: 'channel.join',
        channel_id: 'channel-uuid'
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data.type, data);

    switch (data.type) {
        case 'message.new':
            displayMessage(data.message);
            break;
        case 'typing.update':
            updateTypingIndicator(data.users);
            break;
        case 'presence.changed':
            updateUserStatus(data.user_id, data.status);
            break;
    }
};
```

### Sending Messages

```javascript
// Send a message
ws.send(JSON.stringify({
    type: 'message.send',
    channel_id: 'channel-uuid',
    content: 'Hello, world!'
}));

// Send with @mention
ws.send(JSON.stringify({
    type: 'message.send',
    channel_id: 'channel-uuid',
    content: 'Hey @john, check this out!'
}));

// Reply in thread
ws.send(JSON.stringify({
    type: 'message.send',
    channel_id: 'channel-uuid',
    content: 'This is a thread reply',
    thread_id: 'parent-message-uuid'
}));

// Send with attachment
ws.send(JSON.stringify({
    type: 'message.send',
    channel_id: 'channel-uuid',
    content: 'Check out this file',
    attachment_ids: ['file-uuid-1', 'file-uuid-2']
}));
```

### Typing Indicators

```javascript
// Start typing
ws.send(JSON.stringify({
    type: 'typing.start',
    channel_id: 'channel-uuid'
}));

// Stop typing (or send message)
ws.send(JSON.stringify({
    type: 'typing.stop',
    channel_id: 'channel-uuid'
}));
```

### Reactions

```javascript
// Add reaction
ws.send(JSON.stringify({
    type: 'reaction.add',
    message_id: 'message-uuid',
    emoji: 'thumbsup'  // or unicode: '\ud83d\udc4d'
}));

// Remove reaction
ws.send(JSON.stringify({
    type: 'reaction.remove',
    message_id: 'message-uuid',
    emoji: 'thumbsup'
}));
```

## Configuration

### settings.py

```python
# Channel layers configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
            # For production with Redis Cluster:
            # "hosts": [("redis-node1", 6379), ("redis-node2", 6379)],
        },
    },
}

# WebSocket configuration
DJANGO_MATT_WEBSOCKETS = {
    "ENABLED": True,
    "AUTH_REQUIRED": False,  # Allow anonymous initial connection
    "HEARTBEAT_INTERVAL": 30,
    "RATE_LIMIT": {
        "ENABLED": True,
        "MESSAGES_PER_SECOND": 10,
        "BURST_SIZE": 20,
    },
}

# JWT configuration for WebSocket auth
DJANGO_MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ALGORITHM": "HS256",
}
```

## Docker Deployment

### Full Stack Deployment

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

### Development (Redis only)

```bash
# Start only Redis for local development
docker-compose up -d redis

# Run the app locally with uv
make dev
```

## Performance Considerations

- **Redis pub/sub** for horizontal scaling across multiple server instances
- **Presence tracking** using Redis with automatic expiration
- **Message pagination** with cursor-based pagination for efficiency
- **Rate limiting** to prevent spam (configurable per-user)
- **Connection pooling** for database connections

## Security

- **JWT authentication** for WebSocket connections
- **Channel membership validation** before allowing joins
- **Rate limiting** on all operations
- **Input validation** using Pydantic schemas
- **XSS prevention** - content is escaped before display

## License

MIT

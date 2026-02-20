# Django Matt Examples

This directory contains example applications that demonstrate the features and capabilities of the Django Matt framework.

## Available Examples

### 1. Todo App Example

A simple Todo application that demonstrates the basic features of Django Matt:
- API router setup
- Controller-based views
- Pydantic schema integration
- CRUD operations

**Location:** `examples/todo_app.py`

**To run:**
```bash
python examples/todo_app.py
```

### 2. Error Handling Demo

Demonstrates Django Matt's advanced error handling capabilities:
- Detailed error messages
- Traceback formatting
- Validation error handling
- Custom error middleware

**Location:** `examples/error_handling_demo.py`

**To run:**
```bash
python examples/error_handling_demo.py
```

### 3. Hot Reloading Demo

Shows how to use Django Matt's hot reloading feature:
- Automatic code reloading without server restart
- WebSocket-based browser refresh
- File change detection

**Location:** `examples/hot_reload_demo.py`

**To run:**
```bash
python examples/hot_reload_demo.py
```

### 4. Performance Demo

Demonstrates Django Matt's performance utilities:
- Faster JSON rendering with orjson/ujson
- API endpoint benchmarking
- Performance metrics collection
- Comparison between standard and optimized responses

**Location:** `examples/performance_demo.py`

**To run:**
```bash
# For best results, install orjson first
uv add orjson

# Then run the demo
python examples/performance_demo.py
```

### 5. Real-Time Chat Application

A comprehensive Slack-like chat application demonstrating django-matt WebSocket and real-time messaging features:
- WebSocket connections with JWT authentication
- Real-time message delivery
- Typing indicators
- Online presence tracking
- Message reactions
- Message threading
- Read receipts
- Channel and workspace management
- Direct messages

**Location:** `examples/realtime-chat/`

**To run:**
```bash
cd examples/realtime-chat

# Install dependencies
uv add -r requirements.txt

# Start Redis (required for WebSockets)
docker-compose up -d redis

# Run migrations
python manage.py migrate

# Create a test user
python manage.py createsuperuser

# Start the ASGI server
daphne -p 8000 config.asgi:application

# Or use uvicorn
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
```

Then visit http://localhost:8000/chat/ to access the demo.

**Features demonstrated:**
- `django_matt.websockets` module (consumers, routing, auth middleware)
- `django_matt.auth` JWT integration with WebSockets
- Real-time event broadcasting
- Presence tracking with Redis
- REST API with controllers

## Prerequisites

Before running the examples, make sure you have installed Django Matt and its dependencies:

```bash
# Install Django Matt from the local directory
uv add -e .

# Or install required dependencies
uv add django pydantic websockets

# Optional dependencies for enhanced features
uv add orjson  # For faster JSON rendering
```

## Usage Tips

1. Each example is a standalone application that can be run directly with Python.
2. The examples are designed to be simple and easy to understand.
3. Look at the code comments for detailed explanations of how each feature works.
4. Modify the examples to experiment with different configurations and features.

## Additional Resources

- Check the main [Django Matt documentation](../README.md) for more information.
- See the [todos.md](../todos.md) file for the development roadmap. 
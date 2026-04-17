# Hot Reload

File-watching development server with browser live reload, automatic migration detection, stateful WebSocket preservation, and error overlay.

## Quick Start

```python
# Run the hot reloader from Python
from django_matt.dev.hot_reload import HotReloader

reloader = HotReloader(
    project_dir=".",
    use_websocket=True,
    auto_migrations=True,
)
reloader.start(server_command=["python", "manage.py", "runserver"])
```

Or use the convenience function:

```python
from django_matt.dev.hot_reload import run_hot_reload

run_hot_reload(project_dir=".", server_command=["python", "manage.py", "runserver"])
```

## Configuration

### LiveReloadMiddleware

Inject the live reload script into HTML responses automatically:

```python
# settings.py
MIDDLEWARE = [
    "django_matt.dev.hot_reload.LiveReloadMiddleware",
    ...
]
```

The middleware reads from environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LIVE_RELOAD_HOST` | `localhost` | WebSocket server host |
| `LIVE_RELOAD_PORT` | `35729` | WebSocket server port |
| `DJANGO_DEBUG` | `False` | Must be `true` to inject the script |

### ErrorOverlayMiddleware

Display a styled full-screen error overlay on 500 errors during development:

```python
# settings.py
MIDDLEWARE = [
    "django_matt.dev.error_overlay.ErrorOverlayMiddleware",
    ...
]

DJANGO_MATT_ERROR_OVERLAY = {
    "ENABLED": True,           # Enable/disable (default: True when DEBUG)
    "SHOW_LOCALS": False,      # Show local variables
    "CATCH_4XX": False,        # Also show overlay for 4xx errors
}
```

The overlay shows the exception type, message, and traceback with syntax-highlighted frames. Dismiss with the Escape key or the close button.

## Key Features

### HotReloader

The main `HotReloader` class watches your project directory for file changes and takes action:

- **Python files** (.py): restarts the Django dev server process
- **Static files** (.html, .js, .css): sends a WebSocket reload message to the browser

```python
reloader = HotReloader(
    project_dir=".",
    watched_extensions={".py", ".html", ".js", ".css"},
    ignored_dirs={"__pycache__", ".git", "node_modules", "venv"},
    reload_delay=0.5,          # Debounce delay in seconds
    use_websocket=True,        # Enable browser notifications
    websocket_host="localhost",
    websocket_port=35729,
    auto_migrations=True,      # Auto-detect and run migrations
)
```

### MigrationDetector

Watches for model file changes and automatically runs `makemigrations` and `migrate`:

```python
from django_matt.dev.hot_reload import MigrationDetector

detector = MigrationDetector(
    auto_make=True,     # Run makemigrations on model changes
    auto_migrate=True,  # Run migrate after makemigrations
    console_output=True,
)

# Called by HotReloader when models.py changes
if detector.should_check("myapp/models.py"):
    detector.check_and_apply()
```

The detector only triggers for files named `models.py`, `model.py`, or files inside a `models/` directory. Migration files themselves are ignored.

### StatefulReloader

Preserve WebSocket connection state across code reloads. Normal reloads kill all WebSocket connections -- this module serializes consumer states before reload and reconstructs them after:

```python
from django_matt.dev.stateful_reload import StatefulReloader

reloader = StatefulReloader()

# Before reload: capture all consumer states
snapshot = reloader.capture_states(consumers)
reloader.save_snapshot(snapshot)

# After reload: restore states
snapshot = reloader.load_snapshot()
instructions = reloader.restore_states(snapshot)

# Notify clients
frame = StatefulReloader.build_reload_frame()
```

Register callbacks for pre/post reload hooks:

```python
@reloader.on_pre_reload
def save_extra_state(snapshot):
    snapshot.metadata["custom"] = "data"

@reloader.on_post_reload
def restore_extra_state(snapshot, instructions):
    print(f"Restored {len(instructions)} consumers")
```

### WebSocketServer

The built-in WebSocket server sends SSE-formatted reload messages to connected browsers:

```python
from django_matt.dev.hot_reload import WebSocketServer

server = WebSocketServer(host="localhost", port=35729)
server.start()

# When a file changes:
server.send_reload_message("/path/to/changed/file.css")
```

### inject_live_reload_script

Utility to manually inject the live reload client into an HTML response:

```python
from django_matt.dev.hot_reload import inject_live_reload_script

response = inject_live_reload_script(response, host="localhost", port=35729)
```

The injected script connects via WebSocket, listens for `reload` commands, and auto-reconnects with a 2-second delay on disconnect.

## Practical Example

A typical development setup combining all features:

```python
# settings.py (development only)
DEBUG = True

MIDDLEWARE = [
    "django_matt.dev.error_overlay.ErrorOverlayMiddleware",
    "django_matt.dev.hot_reload.LiveReloadMiddleware",
    ...
]

DJANGO_MATT_ERROR_OVERLAY = {
    "ENABLED": True,
}
```

```python
# dev.py (run with: python dev.py)
from django_matt.dev.hot_reload import HotReloader

reloader = HotReloader(
    project_dir=".",
    auto_migrations=True,
    reload_delay=0.5,
)
reloader.start(server_command=["python", "manage.py", "runserver", "0.0.0.0:8000"])
```

The reloader registers SIGINT/SIGTERM handlers for clean shutdown. Press Ctrl+C to stop.

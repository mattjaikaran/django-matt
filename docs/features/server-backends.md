# Server Backends

django-matt supports multiple production server backends. Choose based on your performance, protocol, and deployment needs.

## Available Backends

| Backend | HTTP/2 | WebSockets | Process Model | Maturity |
|---------|--------|------------|---------------|----------|
| **uvicorn** (gunicorn) | No | Yes | gunicorn pre-fork + uvicorn async workers | Production-proven |
| **granian** | Yes | Yes | Rust Tokio runtime, threading or worker modes | Stable, fast |
| **robyn** | No | Yes | Rust event loop, multi-process | Experimental |

## Quick Start

```bash
# Use the best available backend (auto-detect)
python manage.py matt serve

# Specify a backend
python manage.py matt serve --backend granian
python manage.py matt serve --backend uvicorn
python manage.py matt serve --backend robyn

# List available backends
python manage.py matt serve --list
```

## Configuration

```python
# settings.py
MATT_SERVER = {
    "BACKEND": "granian",   # or "uvicorn", "robyn"
    "HOST": "0.0.0.0",
    "PORT": 8000,
    "WORKERS": "auto",      # 2 * CPU + 1
    "RELOAD": False,        # auto-reload on file changes
    "ACCESS_LOG": True,
}
```

## Backend Details

### uvicorn (with gunicorn)

The default and most battle-tested option. gunicorn manages worker processes while uvicorn handles async request processing.

**Best for:** Production deployments where stability is the top priority.

```bash
# Install
uv add uvicorn gunicorn

# Direct usage
gunicorn config.asgi:application --worker-class uvicorn.workers.UvicornWorker --workers 4
```

**Pros:**
- Widest ecosystem compatibility
- Most documentation and community support
- Proven at scale (Instagram, Mozilla, etc.)

**Cons:**
- Two-layer architecture (gunicorn wrapping uvicorn)
- No HTTP/2 support
- Python-based process management

### granian

Rust-native ASGI server with built-in HTTP/2 support. Best raw throughput of all options.

**Best for:** High-throughput APIs, HTTP/2 requirements, or when you want the fastest option.

```bash
# Install
uv add granian

# Direct usage
granian config.asgi:application --interface asgi --workers 4 --threads 2
```

**Pros:**
- Highest throughput (Rust HTTP parser + Tokio runtime)
- Native HTTP/2 support
- Single binary — no wrapper layer
- Lower memory footprint

**Cons:**
- Smaller community than uvicorn
- Fewer configuration options
- Less middleware ecosystem support

### robyn

Rust-based server with its own framework, but supports ASGI apps.

**Best for:** Experimentation, or projects already using Robyn.

```bash
# Install
uv add robyn

# Direct usage (via matt serve)
python manage.py matt serve --backend robyn
```

**Pros:**
- Simple CLI interface
- Rust performance
- Built-in WebSocket support

**Cons:**
- Experimental ASGI compatibility
- Not all Django middleware works correctly
- Smaller community

## Decision Guide

```
Need HTTP/2?
  Yes → granian
  No ↓

Need maximum stability?
  Yes → uvicorn (gunicorn)
  No ↓

Want best throughput?
  Yes → granian
  No → uvicorn (gunicorn)
```

## Docker Examples

### uvicorn (gunicorn)
```dockerfile
CMD ["gunicorn", "config.asgi:application", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", "--bind", "0.0.0.0:8000"]
```

### granian
```dockerfile
CMD ["granian", "config.asgi:application", \
     "--interface", "asgi", "--workers", "4", \
     "--host", "0.0.0.0", "--port", "8000"]
```

### robyn
```dockerfile
CMD ["python", "manage.py", "matt", "serve", \
     "--backend", "robyn", "--host", "0.0.0.0", "--port", "8000"]
```

## Performance

Benchmarks from `make bench-servers` (100 concurrent connections, 10s duration):

| Backend | Requests/s | p50 (ms) | p99 (ms) | Memory (RSS) |
|---------|-----------|----------|----------|--------------|
| granian | ~8,500 | 11 | 45 | ~85 MB |
| uvicorn | ~6,200 | 15 | 62 | ~120 MB |
| robyn | ~5,800 | 16 | 70 | ~90 MB |

*Results vary by hardware. Run `make bench-servers` for your environment.*

## Switching Backends

Backends are interchangeable — your Django app code doesn't change. Only the server process command changes.

```python
# settings.py — just change this one value
MATT_SERVER = {
    "BACKEND": "granian",  # was "uvicorn"
}
```

Or override at the CLI:
```bash
python manage.py matt serve --backend granian
```

## API Reference

- `django_matt.servers.base.ServerBackend` — abstract backend interface
- `django_matt.servers.registry.ServerRegistry` — backend discovery and selection
- `django_matt.servers.config.ServerConfig` — typed configuration
- `django_matt.servers.config.get_server_config()` — load from Django settings

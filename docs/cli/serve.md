# Server Commands

Commands for running the development server and interactive shell.

## matt serve

Start the Django development server with hot reload enabled by default.

```bash
matt serve [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port`, `-p` | `8000` | Port to run the server on |
| `--host`, `-h` | `127.0.0.1` | Host to bind to |
| `--https` | `false` | Enable HTTPS (requires django-extensions) |
| `--no-hot` | `false` | Disable hot reload |

### Examples

```bash
# Start on default port (8000)
matt serve

# Start on custom port
matt serve --port 8080

# Start on all interfaces (accessible from network)
matt serve --host 0.0.0.0

# Start with HTTPS
matt serve --https

# Disable hot reload
matt serve --no-hot
```

### Expected Output

```
Starting development server on 127.0.0.1:8000...

Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
February 03, 2026 - 10:30:00
Django version 5.2, using settings 'myproject.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

!!! tip "HTTPS Development"
    For HTTPS, you need `django-extensions` installed:
    ```bash
    uv add django-extensions
    ```
    The command will auto-generate SSL certificates in a temp directory.

---

## matt dev

Alias for `matt serve`. Start development server quickly.

```bash
matt dev [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port`, `-p` | `8000` | Port to run the server on |

### Examples

```bash
# Quick start
matt dev

# Custom port
matt dev --port 3000
```

---

## matt shell

Open Django's interactive Python shell with your project loaded.

```bash
matt shell [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--ipython`, `-i` | `false` | Use IPython shell if available |

### Examples

```bash
# Standard Django shell
matt shell

# IPython shell (if installed)
matt shell --ipython
```

### Expected Output

```
Starting Django shell...

Python 3.12.0 (main, Oct 10 2025, 14:23:43)
Type 'copyright', 'credits' or 'license' for more information
IPython 8.18.0 -- An enhanced Interactive Python. Type '?' for help.

In [1]: from myapp.models import User
In [2]: User.objects.count()
Out[2]: 42
```

!!! tip "IPython"
    For an enhanced shell experience, install IPython:
    ```bash
    uv add ipython
    ```

---

## matt serve test

Run project tests using pytest (if available) or Django's test runner.

```bash
matt serve test [OPTIONS] [PATH]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `PATH` | Test path or module (optional) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--verbose`, `-v` | `false` | Verbose output |
| `--failfast`, `-f` | `false` | Stop on first failure |
| `--coverage`, `-c` | `false` | Run with coverage |

### Examples

```bash
# Run all tests
matt serve test

# Run specific test file
matt serve test tests/test_api.py

# Verbose with coverage
matt serve test --verbose --coverage

# Stop on first failure
matt serve test --failfast
```

### Expected Output

```
Running tests...

============================= test session starts ==============================
platform darwin -- Python 3.12.0, pytest-8.0.0
collected 42 items

tests/test_auth.py ....                                                   [  9%]
tests/test_api.py ............                                            [ 38%]
tests/test_models.py ..................                                   [ 81%]
tests/test_views.py ........                                              [100%]

============================== 42 passed in 2.34s ==============================
```

---

## matt serve check

Run Django system checks.

```bash
matt serve check
```

### Examples

```bash
matt serve check
```

### Expected Output

```
Running Django system checks...

System check identified no issues (0 silenced).
```

---

## matt serve collectstatic

Collect static files for production deployment.

```bash
matt serve collectstatic [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--no-input` | `true` | Skip confirmation prompts |
| `--clear` | `false` | Clear existing files first |

### Examples

```bash
# Collect static files
matt serve collectstatic

# Clear and collect
matt serve collectstatic --clear
```

---

## Best Practices

### Development Workflow

```bash
# Terminal 1: Start server
matt dev

# Terminal 2: Watch types
matt types ts --watch

# Terminal 3: Run tests on change
matt serve test --watch  # (if configured)
```

### Port Management

```bash
# If port 8000 is busy
matt serve --port 8001

# Find what's using a port
lsof -i :8000
```

### Environment-Specific Settings

```bash
# Development
DJANGO_SETTINGS_MODULE=config.settings.local matt serve

# Staging
DJANGO_SETTINGS_MODULE=config.settings.staging matt serve
```

## Troubleshooting

!!! warning "Port Already in Use"
    If you see "Address already in use":
    ```bash
    # Find and kill process
    lsof -i :8000 | grep LISTEN
    kill -9 <PID>

    # Or use a different port
    matt serve --port 8001
    ```

!!! warning "Settings Not Found"
    If Django settings aren't detected:
    ```bash
    export DJANGO_SETTINGS_MODULE=myproject.settings
    matt serve
    ```

## See Also

- [Database Commands](database.md)
- [Testing Documentation](testing.md)
- [Hot Reload Configuration](../features/hot-reload.md)

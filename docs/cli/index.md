# CLI Overview

Django Matt provides two command-line interfaces for managing your project:

1. **`matt` CLI** - A standalone, modern command-line tool with a beautiful interface
2. **`manage.py` commands** - Traditional Django management commands

## Installation

The `matt` CLI is automatically installed when you install django-matt:

```bash
uv add django-matt
```

Verify installation:

```bash
matt --version
```

## Quick Comparison

| Feature | `matt` CLI | `manage.py` commands |
|---------|-----------|---------------------|
| Interactive UI | Yes (Rich-based) | Basic text output |
| Auto-detect settings | Yes | Requires `DJANGO_SETTINGS_MODULE` |
| Tab completion | Yes (via Typer) | Via django-extensions |
| Grouped commands | Yes | Flat structure |
| Best for | Development workflow | CI/CD, scripts |

## Command Structure

### matt CLI

The `matt` command groups related functionality:

```bash
matt                    # Show available commands
matt serve              # Development server commands
matt db migrate         # Database commands
matt new controller     # Code generation
matt types ts           # Type generation
matt analyze            # Project analysis
matt deploy fly         # Deployment commands
```

### manage.py Commands

Django Matt adds these management commands:

```bash
python manage.py startapi          # Create new API project
python manage.py generate_crud     # Generate CRUD for models
python manage.py sync_types        # Generate TypeScript/Swift types
python manage.py benchmark         # Run performance benchmarks
python manage.py generate_ai_context  # Generate AI context files
```

## Getting Started

### Using matt CLI

```bash
# Start development server
matt serve

# Or use the shorter alias
matt dev

# Create database migrations
matt db make

# Apply migrations
matt db migrate

# Generate CRUD for a model
matt crud myapp.Product

# Generate TypeScript types
matt types ts --output frontend/src/types/api.ts
```

### Using manage.py

```bash
# Start API project
python manage.py startapi myproject --template b2b

# Generate CRUD
python manage.py generate_crud myapp.Product --full

# Sync types with watch mode
python manage.py sync_types --target typescript --watch
```

## Auto-Detection

The `matt` CLI automatically detects your Django settings:

1. Checks `DJANGO_SETTINGS_MODULE` environment variable
2. Looks for common patterns: `config.settings`, `settings`, `core.settings`
3. Searches for `manage.py` in current and parent directories

!!! tip "Manual Settings"
    If auto-detection fails, set the environment variable:
    ```bash
    export DJANGO_SETTINGS_MODULE=myproject.settings
    matt serve
    ```

## Shell Completion

### Bash

```bash
matt --install-completion bash
```

### Zsh

```bash
matt --install-completion zsh
```

### Fish

```bash
matt --install-completion fish
```

## Common Workflows

### Starting a New Project

```bash
# Create project with matt CLI
matt new api myproject --template b2b --auth jwt --docker

# Or with manage.py
python manage.py startapi myproject --template b2b --auth jwt --docker
```

### Development Cycle

```bash
# 1. Start server
matt dev

# 2. Make model changes, create migrations
matt db make

# 3. Apply migrations
matt db migrate

# 4. Generate types for frontend
matt types ts --watch
```

### Adding a New Feature

```bash
# 1. Create model (manually)
# 2. Generate CRUD
matt crud myapp.NewModel --full

# 3. Run tests
matt serve test

# 4. Update types
matt types ts
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SETTINGS_MODULE` | Django settings module | Auto-detected |
| `MATT_DEBUG` | Enable CLI debug mode | `false` |
| `NO_COLOR` | Disable colored output | Not set |

## Next Steps

- [matt Command Reference](matt-command.md) - Complete CLI documentation
- [Server Commands](serve.md) - Development server and shell
- [Database Commands](database.md) - Migrations and data management
- [Code Generation](generate.md) - Scaffolding and CRUD generation
- [Type Generation](types.md) - TypeScript/Swift/Zod generation
- [Analysis Tools](analyze.md) - Project introspection
- [Deployment](deploy.md) - Cloud deployment commands

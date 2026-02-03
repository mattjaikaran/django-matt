# Django Management Commands

Django Matt extends Django's management command system with powerful commands for API development.

## Overview

Management commands are run via `manage.py`:

```bash
python manage.py COMMAND [OPTIONS]
```

## Available Commands

### Project Setup

| Command | Description |
|---------|-------------|
| `startapi` | Create a new Django Matt API project |
| `config` | Manage project configuration |

### Code Generation

| Command | Description |
|---------|-------------|
| `generate_crud` | Generate CRUD controllers, schemas, services |
| `generate_admin` | Generate Django Unfold admin configuration |
| `matt new` | Scaffold components (controllers, schemas, services) |

### Type Synchronization

| Command | Description |
|---------|-------------|
| `sync_types` | Generate TypeScript/Swift/Zod types |
| `init_codegen` | Initialize type generation configuration |

### Development

| Command | Description |
|---------|-------------|
| `runserver` | Development server with hot reload |
| `runserver_hot` | Explicit hot reload server |

### Analysis & Diagnostics

| Command | Description |
|---------|-------------|
| `matt_analyze` | Analyze project structure |
| `matt_status` | Show project status |
| `matt_endpoints` | List API endpoints |
| `matt_schemas` | List Pydantic schemas |
| `matt_explain` | Explain framework concepts |

### Performance

| Command | Description |
|---------|-------------|
| `benchmark` | Run performance benchmarks |

### AI Integration

| Command | Description |
|---------|-------------|
| `generate_ai_context` | Generate AI assistant context files |

### Deployment

| Command | Description |
|---------|-------------|
| `deploy` | Deploy to cloud platforms |

## Quick Reference

### Create a New Project

```bash
# Basic project
python manage.py startapi myproject

# B2B project with JWT and Docker
python manage.py startapi myproject --template b2b --auth jwt --docker
```

### Generate CRUD for a Model

```bash
# Basic CRUD
python manage.py generate_crud myapp.Product

# Full generation (controller, schema, service, admin, tests)
python manage.py generate_crud myapp.Product --full

# Interactive wizard
python manage.py generate_crud --wizard
```

### Sync Types to Frontend

```bash
# TypeScript types
python manage.py sync_types --target typescript --output frontend/types/api.ts

# Watch mode
python manage.py sync_types --target typescript --watch

# Swift types
python manage.py sync_types --target swift --output ios/API/Models.swift
```

### Run Benchmarks

```bash
# All benchmarks
python manage.py benchmark

# Specific scenario
python manage.py benchmark --scenario json

# With comparison
python manage.py benchmark --compare --save
```

### Generate AI Context

```bash
# Generate all AI context files
python manage.py generate_ai_context

# Specific format
python manage.py generate_ai_context --format claude

# Watch mode
python manage.py generate_ai_context --watch
```

## Command vs matt CLI

Most management commands have corresponding `matt` CLI commands:

| Management Command | matt CLI |
|-------------------|----------|
| `python manage.py startapi` | `matt new api` |
| `python manage.py generate_crud` | `matt crud` |
| `python manage.py sync_types` | `matt types ts` |
| `python manage.py runserver` | `matt serve` |

**When to use management commands:**

- CI/CD pipelines
- Scripts and automation
- Explicit Django settings control
- Programmatic access

**When to use matt CLI:**

- Interactive development
- Quick tasks
- Better visual output
- Tab completion

## Getting Help

All commands support `--help`:

```bash
python manage.py startapi --help
python manage.py generate_crud --help
python manage.py sync_types --help
```

## Next Steps

- [startapi Command](startapi.md) - Create new projects
- [generate_crud Command](generate-crud.md) - Generate CRUD operations
- [sync_types Command](sync-types.md) - Type synchronization
- [benchmark Command](benchmark.md) - Performance testing
- [generate_ai_context Command](generate-ai-context.md) - AI context files

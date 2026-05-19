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

### Migration Tools

| Command | Description |
|---------|-------------|
| `matt_baseline create <version>` | Create a SQL schema baseline for fast DB setup |
| `matt_baseline load <version>` | Load a baseline onto a fresh database |
| `matt_baseline list` | List available baselines |
| `matt_baseline verify <version>` | Verify a baseline's integrity |
| `matt_baseline delete <version>` | Delete a baseline |
| `matt_migrate --stats` | Show migration statistics for the project |
| `matt_migrate --profile` | Profile pending migrations and estimate time |
| `matt_migrate --parallel` | Run migrations in parallel waves |
| `matt_migrate --check` | Analyze pending migrations for unsafe DDL patterns |
| `matt_migrate --graph` | Visualize the migration dependency graph |
| `matt_squash <app> <start> <end>` | Squash a migration range |
| `matt_squash --analyze` | Identify squash opportunities across all apps |
| `matt_squash --all --to-tag <tag>` | Squash all apps up to a git tag |

### Documentation

| Command | Description |
|---------|-------------|
| `matt_docs coverage` | Show docstring coverage statistics |
| `matt_docs stubs` | Generate docstring stubs for undocumented code |
| `matt_docs hints` | Find functions and classes missing type hints |

### Background Tasks (Native Engine)

| Command | Description |
|---------|-------------|
| `matt_tasks list` | List all registered tasks |
| `matt_tasks schedules` | List all periodic schedules |
| `matt_tasks run <name>` | Run a task manually (enqueued or `--sync`) |
| `matt_tasks status` | Show queue health and pending task counts |
| `matt_tasks purge` | Delete old completed/failed tasks |
| `matt_tasks retry` | Bulk retry failed tasks |

### AI-Assisted Audits

| Command | Description |
|---------|-------------|
| `matt_audit` | Run all audit categories |
| `matt_audit security` | Security vulnerability scan |
| `matt_audit performance` | Performance bottleneck analysis |
| `matt_audit scalability` | Scalability review |
| `matt_audit best_practices` | Code quality checks |
| `matt_audit maintainability` | Code health analysis |
| `matt_audit accessibility` | Accessibility review |
| `matt_audit bundle` | Bundle size and startup time analysis |
| `matt_audit context` | Generate LLM context for code review |

Shared options: `--level relaxed|standard|strict|paranoid`, `--format text|json|markdown|sarif`, `--output <file>`, `--ci`, `--fail-on critical|high|medium|low|info`, `--exclude <pattern>`, `--diff <git-ref>`, `--fix`, `--fix-preview`. For `context`: `--for claude|gpt|generic`.

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

# Zod schemas
python manage.py sync_types --target zod --output frontend/src/schemas/api.ts

# Typed API client
python manage.py sync_types --target api-client --output frontend/src/api/client.ts

# Swift types
python manage.py sync_types --target swift --output ios/API/Models.swift

# Watch mode
python manage.py sync_types --target typescript --watch

# Specific apps
python manage.py sync_types --target typescript --apps myapp,users

# Use config file
python manage.py sync_types --config
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

### Migration Baselines

```bash
# Create a baseline from current state
python manage.py matt_baseline create v1.0.0 --notes "Release 1.0 schema"

# Load on a fresh database
python manage.py matt_baseline load v1.0.0

# List available baselines
python manage.py matt_baseline list
```

### Migration Analysis and Acceleration

```bash
# Show statistics
python manage.py matt_migrate --stats

# Profile pending migrations
python manage.py matt_migrate --profile

# Run migrations in parallel
python manage.py matt_migrate --parallel

# Check for unsafe DDL
python manage.py matt_migrate --check
```

### Squashing Migrations

```bash
# Squash a range
python manage.py matt_squash myapp 0001 0042

# Preview first
python manage.py matt_squash myapp 0001 0042 --preview

# Find squash opportunities
python manage.py matt_squash --analyze
```

### Documentation Tools

```bash
# Show coverage stats
python manage.py matt_docs coverage

# Generate docstring stubs
python manage.py matt_docs stubs

# Find missing type hints
python manage.py matt_docs hints
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
- [matt_tasks Command](matt-tasks.md) - Native background task management
- [matt_audit Command](matt-audit.md) - AI-assisted codebase audits
- [matt_baseline / matt_migrate / matt_squash](migration-tools.md) - Migration acceleration

# generate_ai_context Command

Generate AI assistant context files for Claude, Cursor, GitHub Copilot, and other AI tools.

## Synopsis

```bash
python manage.py generate_ai_context [OPTIONS]
```

## Description

The `generate_ai_context` command analyzes your Django project and generates context files that help AI assistants understand your codebase:

- **CLAUDE.md** - Context file for Claude (Anthropic)
- **.cursorrules** - Rules file for Cursor IDE
- **.copilot-instructions** - Instructions for GitHub Copilot
- **introspection.json** - Machine-readable project data

These files help AI assistants:

- Understand your project structure
- Follow your coding conventions
- Generate code that matches your patterns
- Provide more accurate suggestions

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | `.` | Output directory for generated files |
| `--format`, `-f` | `default` | Format: `all`, `claude`, `cursor`, `copilot`, `json` |
| `--include-third-party` | `false` | Include third-party apps in analysis |
| `--exclude-apps` | None | Apps to exclude from analysis |
| `--include-examples` | `false` | Include code examples from codebase |
| `--output-json` | `false` | Output JSON introspection to stdout |
| `--watch`, `-w` | `false` | Watch for changes and auto-regenerate |
| `--debounce` | `1.0` | Debounce delay for watch mode |
| `--install-hook` | `false` | Install pre-commit hook |
| `--show-hook` | `false` | Show pre-commit hook script |
| `--dry-run` | `false` | Show what would be generated |
| `--quiet`, `-q` | `false` | Minimal output |

## Examples

### Basic Generation

```bash
# Generate all default context files
python manage.py generate_ai_context
```

Generates:
- `CLAUDE.md`
- `.cursorrules`
- `.copilot-instructions`

### Specific Format

```bash
# Only CLAUDE.md
python manage.py generate_ai_context --format claude

# Only Cursor rules
python manage.py generate_ai_context --format cursor

# All formats including JSON
python manage.py generate_ai_context --format all
```

### Custom Output Directory

```bash
# Generate to docs folder
python manage.py generate_ai_context --output docs/

# Generate to project root
python manage.py generate_ai_context --output .
```

### Include Code Examples

```bash
# Include actual code snippets from your codebase
python manage.py generate_ai_context --include-examples
```

### Watch Mode

```bash
# Auto-regenerate on file changes
python manage.py generate_ai_context --watch

# Custom debounce
python manage.py generate_ai_context --watch --debounce 2.0
```

### JSON Output

```bash
# Output machine-readable JSON
python manage.py generate_ai_context --output-json > project.json

# Or save to file
python manage.py generate_ai_context --format json
```

### Pre-commit Hook

```bash
# Install pre-commit hook for auto-regeneration
python manage.py generate_ai_context --install-hook

# Show hook script without installing
python manage.py generate_ai_context --show-hook
```

### Exclude Apps

```bash
# Exclude migrations and admin
python manage.py generate_ai_context --exclude-apps migrations admin
```

### Preview

```bash
# See what would be generated without writing files
python manage.py generate_ai_context --dry-run
```

## Generated Files

### CLAUDE.md

Context file for Claude Code and other Claude interfaces:

```markdown
# Project Context

## Overview
- **Project**: myproject
- **Framework**: Django Matt (django-matt)
- **Python**: 3.12
- **Django**: 5.2

## Project Structure
```
myproject/
├── api/
│   ├── controllers/
│   ├── models/
│   └── schemas/
├── users/
└── products/
```

## Models

### User (users.models.User)
- email: EmailField
- name: CharField
- created_at: DateTimeField

### Product (products.models.Product)
- name: CharField (max_length=255)
- price: DecimalField
- description: TextField

## API Endpoints

### Users API
- GET /api/users/ - List users
- POST /api/users/ - Create user
- GET /api/users/{id}/ - Get user
- PUT /api/users/{id}/ - Update user
- DELETE /api/users/{id}/ - Delete user

### Products API
...

## Schemas

### UserSchema
```python
class UserSchema(BaseModel):
    id: int
    email: str
    name: str
```

## Coding Conventions
- Use async/await for all handlers
- Pydantic for all request/response schemas
- Service layer for business logic
- Django Matt controllers for endpoints

## Authentication
- JWT authentication enabled
- Access token lifetime: 15 minutes
- Refresh token lifetime: 7 days
```

### .cursorrules

Rules file for Cursor IDE:

```yaml
# Cursor Rules for myproject

## Project Type
Django API project using django-matt framework

## Code Style
- Use Python 3.12+ features
- Async-first design (use async def for handlers)
- Type hints everywhere
- Pydantic for schemas

## File Patterns
- Controllers: *_controller.py
- Schemas: *_schemas.py or schemas.py
- Services: *_service.py
- Tests: test_*.py

## Imports
Prefer these import patterns:
```python
from django_matt.core import APIController
from django_matt.permissions import IsAuthenticated
from pydantic import BaseModel
```

## Testing
- Use pytest and pytest-asyncio
- Use APITestClient for endpoint tests
- Use factories for test data

## Don't
- Don't use Django REST framework
- Don't use class-based views (use controllers)
- Don't forget type hints
```

### .copilot-instructions

Instructions for GitHub Copilot:

```markdown
# GitHub Copilot Instructions

This is a Django Matt API project.

## Framework
- Django Matt (django-matt) - Modern Django API framework
- Pydantic for schemas
- Async-first design

## When generating code:
1. Use async def for view handlers
2. Use Pydantic BaseModel for schemas
3. Use Django Matt decorators (@get, @post, etc.)
4. Include type hints
5. Use service layer for business logic

## Example Controller:
```python
from django_matt.core import APIController
from django_matt.core.router import get, post

class ProductController(APIController):
    prefix = "/products"

    @get("/")
    async def list_products(self, request):
        ...
```

## Example Schema:
```python
from pydantic import BaseModel

class ProductSchema(BaseModel):
    id: int
    name: str
    price: float

    class Config:
        from_attributes = True
```
```

### introspection.json

Machine-readable project data:

```json
{
  "project": {
    "name": "myproject",
    "framework": "django-matt",
    "python_version": "3.12.0",
    "django_version": "5.2.0"
  },
  "apps": [
    {
      "name": "api",
      "models": [...],
      "controllers": [...],
      "schemas": [...]
    }
  ],
  "endpoints": [
    {
      "method": "GET",
      "path": "/api/users/",
      "name": "user-list",
      "controller": "UserController"
    }
  ],
  "models": [
    {
      "name": "User",
      "app": "users",
      "table": "users_user",
      "fields": [
        {"name": "id", "type": "AutoField"},
        {"name": "email", "type": "EmailField"}
      ]
    }
  ],
  "schemas": [
    {
      "name": "UserSchema",
      "module": "users.schemas",
      "fields": [
        {"name": "id", "type": "int"},
        {"name": "email", "type": "str"}
      ]
    }
  ]
}
```

## Pre-commit Hook

The pre-commit hook automatically regenerates context files on each commit:

### Manual Installation

```bash
python manage.py generate_ai_context --show-hook
```

Copy the output to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Auto-regenerate AI context files before commit

python manage.py generate_ai_context --quiet

# Add generated files to the commit
git add CLAUDE.md .cursorrules .copilot-instructions 2>/dev/null || true
```

### Automatic Installation

```bash
python manage.py generate_ai_context --install-hook
```

### pre-commit Framework

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ai-context
        name: Generate AI Context
        entry: python manage.py generate_ai_context --quiet
        language: system
        always_run: true
        pass_filenames: false
```

## Watch Mode

Watch mode automatically regenerates context files when your code changes:

```bash
python manage.py generate_ai_context --watch
```

Output:

```
Generating initial context files...
  Found 24 endpoints, 12 models, 18 schemas
  Generated: CLAUDE.md
  Generated: .cursorrules
  Generated: .copilot-instructions

Starting watch mode...
Watcher started. Press Ctrl+C to stop.

[10:30:45] File changed: users/schemas.py
[10:30:46] Regenerated context files
```

## Best Practices

### Keep Context Updated

Use watch mode during development:

```bash
python manage.py generate_ai_context --watch
```

Or install the pre-commit hook:

```bash
python manage.py generate_ai_context --install-hook
```

### Include Examples for Better AI Suggestions

```bash
python manage.py generate_ai_context --include-examples
```

This includes actual code snippets from your codebase, helping AI understand your patterns.

### Version Control

Commit generated files to version control:

```gitignore
# Don't ignore - these are useful for AI assistants
# CLAUDE.md
# .cursorrules
# .copilot-instructions

# But do ignore the JSON introspection
introspection.json
```

### Review Generated Content

After generation, review the files to ensure they:

- Accurately represent your project
- Don't expose sensitive information
- Include project-specific conventions

### Customize After Generation

Add project-specific instructions to the generated files:

```markdown
# In CLAUDE.md, add:

## Project-Specific Rules
- Always use `timezone.now()` instead of `datetime.now()`
- Use `Decimal` for money fields
- All API responses must include pagination
```

## See Also

- [CLI: matt ai](../cli/index.md)
- [AI Integration Guide](../ai/overview.md)
- [Code Style Guide](../contributing.md)

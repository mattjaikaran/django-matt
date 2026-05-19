# Django Matt CLI Tools

Django Matt provides management commands for scaffolding, code generation, configuration, and development. All commands are run via `manage.py`.

## Scaffolding Commands

### `startapp` — Create a New App

Overrides Django's built-in `startapp` to create a package-based directory structure with models, schemas, controllers, admin, services, tests, and factories — each in their own file.

```bash
# Basic app with model derived from name
python manage.py startapp blog

# App with specific models
python manage.py startapp blog --models Post Comment Tag

# Preview without writing
python manage.py startapp blog --models Post --dry-run

# Skip service layer
python manage.py startapp blog --models Post --no-service
```

See [startapp documentation](startapp.md) for generated file examples and full options.

### `generate_crud` — Generate CRUD from Models

Reads an existing Django model and generates matching schemas, controllers, services, admin, and tests.

```bash
# Schema + controller only
python manage.py generate_crud blog.Post

# Everything: schema, controller, service, admin, tests
python manage.py generate_crud blog.Post --full

# Interactive wizard
python manage.py generate_crud --wizard

# With permissions and soft delete
python manage.py generate_crud blog.Post --full --permissions IsAuthenticated --soft-delete

# Preview without writing
python manage.py generate_crud blog.Post --full --dry-run
```

See [CRUD generator documentation](crud-generator.md) for all options.

### `startapi` — Create a Full Project

Generates a complete Django Matt project with settings, URL config, Docker, frontend scaffold, and authentication.

```bash
# Minimal API project (default template)
python manage.py startapi myproject

# B2B SaaS project with Docker
python manage.py startapi myproject --template b2b --auth jwt --docker

# AI-SaaS project
python manage.py startapi myproject --template ai-saas --auth jwt --docker

# With React frontend
python manage.py startapi myproject --frontend react-vite --docker
```

Available templates: `api-only` (default), `starter`, `b2b`, `b2c`, `saas`, `ai-saas`, `marketplace`, `internal-tools`.

### Typical Workflow

```bash
# 1. Create the app skeleton
python manage.py startapp blog --models Post Comment

# 2. Edit models to add real fields
#    edit blog/models/post.py, blog/models/comment.py

# 3. Migrate
python manage.py makemigrations blog && python manage.py migrate

# 4. Regenerate scaffolding from real model fields
python manage.py generate_crud blog.Post --full
python manage.py generate_crud blog.Comment --full
```

See [Scaffolding Workflow](scaffolding.md) for the full guide.

---

## Type Generation (`sync_types`)

Generate TypeScript, Zod, Swift, or API client types from Pydantic schemas.

```bash
# TypeScript interfaces
python manage.py sync_types --target typescript --output frontend/src/types/api.ts

# Zod schemas (runtime validation)
python manage.py sync_types --target zod --output frontend/src/schemas/api.ts

# Typed API client
python manage.py sync_types --target api-client --output frontend/src/api/client.ts

# Swift Codable structs
python manage.py sync_types --target swift --output ios/App/API/Models.swift

# Watch mode — regenerate on file changes
python manage.py sync_types --target typescript --output frontend/src/types/api.ts --watch

# Scan specific apps
python manage.py sync_types --target typescript --apps myapp,users

# Include React Query hooks in API client
python manage.py sync_types --target api-client --include-react-query

# Use config file (django_matt_codegen.py or pyproject.toml)
python manage.py sync_types --config
```

---

## AI Context Generation (`generate_ai_context`)

Analyze your project and generate context files for Claude, Cursor, and GitHub Copilot.

```bash
# Generate all context files (CLAUDE.md, .cursorrules, .copilot-instructions)
python manage.py generate_ai_context

# Specific format
python manage.py generate_ai_context --format claude
python manage.py generate_ai_context --format cursor
python manage.py generate_ai_context --format all

# Watch mode — auto-regenerate on file changes
python manage.py generate_ai_context --watch

# Install pre-commit hook for automatic regeneration
python manage.py generate_ai_context --install-hook

# Include code examples from the codebase
python manage.py generate_ai_context --include-examples

# Preview without writing
python manage.py generate_ai_context --dry-run
```

---

## Configuration Management

The `config` command provides utilities for managing Django Matt configuration files. It can help you initialize configuration files for your project, generate settings files for different environments, and create environment variable files.

### Subcommands

#### `init`

Initializes configuration files for your project. This includes:

- Creating a `config` directory in your project
- Creating an `__init__.py` file in the `config` directory
- Creating a `settings.py` file in your project
- Creating `.env` files for different environments

```bash
python manage.py config init [--force] [--env {development,staging,production,all}]
```

Options:
- `--force`: Overwrite existing files
- `--env`: Environment to initialize (default: all)

Example:
```bash
# Initialize configuration files for all environments
python manage.py config init

# Initialize configuration files for production only
python manage.py config init --env production

# Force overwrite of existing files
python manage.py config init --force
```

#### `generate`

Generates a `settings.py` file for a specific environment.

```bash
python manage.py config generate [--env {development,staging,production}] [--components COMPONENTS [COMPONENTS ...]] [--output OUTPUT]
```

Options:
- `--env`: Environment to generate settings for (default: development)
- `--components`: Components to include in the settings (default: database cache security performance)
- `--output`: Output file path (default: settings.py)

Example:
```bash
# Generate a settings.py file for development
python manage.py config generate

# Generate a settings.py file for production with specific components
python manage.py config generate --env production --components database cache security

# Generate a settings.py file with a custom output path
python manage.py config generate --output myproject/settings/development.py
```

#### `env`

Generates a `.env` file for a specific environment.

```bash
python manage.py config env [--env {development,staging,production}] [--output OUTPUT]
```

Options:
- `--env`: Environment to generate .env file for (default: development)
- `--output`: Output file path (default: .env)

Example:
```bash
# Generate a .env file for development
python manage.py config env

# Generate a .env file for production
python manage.py config env --env production

# Generate a .env file with a custom output path
python manage.py config env --output .env.local
```

### Generated Files

#### Settings File

The generated `settings.py` file uses the Django Matt configuration system to load settings from different environments and components. It includes:

- Environment detection
- Component loading
- Project-specific settings
- Django Matt middleware

Example:
```python
"""
My Project settings.

Generated by Django Matt config management command.
"""

import os
from pathlib import Path

# Import the Django Matt configuration system
from django_matt.config import configure

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Determine the environment
ENVIRONMENT = os.environ.get("DJANGO_ENV", "development")

# Configure the application
settings = configure(
    # Specify the environment (development, staging, production)
    environment=ENVIRONMENT,
    
    # Specify the components to load
    components=["database", "cache", "security", "performance"],
    
    # Specify additional settings
    extra_settings={
        # Project-specific settings
        "ROOT_URLCONF": "my_project.urls",
        "WSGI_APPLICATION": "my_project.wsgi.application",
        
        # Add your project's apps
        "INSTALLED_APPS": [
            # Django Matt apps
            "django_matt",
            
            # Your project's apps
            "my_project.core",
        ],
        
        # Add your project's middleware
        "MIDDLEWARE": [
            # Django Matt middleware
            "django_matt.middleware.BenchmarkMiddleware",
        ],
        
        # Add your project's templates
        "TEMPLATES": [
            {
                "DIRS": [
                    os.path.join(BASE_DIR, "my_project", "templates"),
                ],
            },
        ],
        
        # Add your project's static files
        "STATICFILES_DIRS": [
            os.path.join(BASE_DIR, "my_project", "static"),
        ],
        
        # Add your project's media files
        "MEDIA_ROOT": os.path.join(BASE_DIR, "my_project", "media"),
    },
    
    # Apply the settings to Django's settings module
    apply_to_django=True,
)

# You can access the settings directly if needed
DEBUG = settings["DEBUG"]
SECRET_KEY = settings["SECRET_KEY"]

# You can also add additional settings after configuration
SOME_CUSTOM_SETTING = "custom value"

# For demonstration purposes, print the environment
if DEBUG:
    print(f"Running in {ENVIRONMENT} environment")
```

#### Environment Files

The generated `.env` files contain environment variables for different environments. They include:

- Core settings (environment, secret key, allowed hosts)
- Database settings
- Cache settings
- Security settings (for production)
- Django Matt settings
- Email settings (for production)

Example for development:
```
# My Project development environment variables
DJANGO_ENV=development
DJANGO_SECRET_KEY=1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
ALLOWED_HOSTS=localhost,127.0.0.1,[::1]

# Database settings
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

# Cache settings
CACHE_BACKEND=django.core.cache.backends.locmem.LocMemCache
CACHE_LOCATION=django_matt
CACHE_TIMEOUT=300

# Django Matt settings
DJANGO_MATT_BENCHMARK_ENABLED=True
DJANGO_MATT_CACHE_ENABLED=True
DJANGO_MATT_CACHE_TIMEOUT=300
```

Example for production:
```
# My Project production environment variables
DJANGO_ENV=production
DJANGO_SECRET_KEY=1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
ALLOWED_HOSTS=example.com,www.example.com

# Database settings
DB_ENGINE=django.db.backends.postgresql
DB_NAME=my_project
DB_USER=my_project
DB_PASSWORD=change_me
DB_HOST=localhost
DB_PORT=5432

# Cache settings
CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
CACHE_LOCATION=redis://localhost:6379/1
CACHE_TIMEOUT=3600
REDIS_URL=redis://localhost:6379/0

# Security settings
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Django Matt settings
DJANGO_MATT_BENCHMARK_ENABLED=False
DJANGO_MATT_CACHE_ENABLED=True
DJANGO_MATT_CACHE_TIMEOUT=3600

# Email settings
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=user@example.com
EMAIL_HOST_PASSWORD=change_me
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@example.com
```

### Best Practices

- Initialize your project with `python manage.py config init` to create the basic configuration files
- Use environment-specific `.env` files for different environments
- Add `.env` to your `.gitignore` file to avoid committing sensitive information
- Use `.env.example` as a template for other developers
- Generate environment-specific settings files for complex projects

## Hot Reloading

The `runserver_hot` command runs the Django development server with hot reloading enabled. It automatically reloads the browser when you make changes to your code.

```bash
python manage.py runserver_hot [addrport]
```

Options:
- `addrport`: Optional port number, or ipaddr:port

Example:
```bash
# Run the server on the default port (8000)
python manage.py runserver_hot

# Run the server on a specific port
python manage.py runserver_hot 8080

# Run the server on a specific IP address and port
python manage.py runserver_hot 0.0.0.0:8000
```

For more information on hot reloading, see the [Hot Reloading documentation](hot_reloading.md).

---

## Native Task Engine (`matt_tasks`)

Manage background tasks registered with the django-matt native task engine (Stage 17A).

```bash
python manage.py matt_tasks list                              # List all registered tasks
python manage.py matt_tasks run send_email --payload '{}'     # Enqueue a task
python manage.py matt_tasks run send_email --payload '{}' --sync  # Run synchronously
python manage.py matt_tasks status                            # Queue health and counts
python manage.py matt_tasks status --queue emails             # Filter by queue
python manage.py matt_tasks purge --older-than 30d            # Remove old completed tasks
python manage.py matt_tasks purge --state failed --older-than 7d  # Remove old failures
python manage.py matt_tasks purge --dry-run                   # Preview without deleting
python manage.py matt_tasks retry --failed --last 24h         # Bulk retry failures
python manage.py matt_tasks retry --task send_email --last 7d # Retry specific task
python manage.py matt_tasks schedules                         # List all schedules
python manage.py matt_tasks schedules --enabled-only          # Only enabled schedules
```

Output formats for `list`, `status`, `schedules`: `--format table` (default) or `--format json`.

---

## AI-Assisted Audits (`matt_audit`)

Run AI-assisted codebase audits (Stage 17B). Accepts a positional `audit_type` argument.

```bash
python manage.py matt_audit                         # Run all audits
python manage.py matt_audit security                # Security vulnerability scan
python manage.py matt_audit performance             # Performance bottleneck analysis
python manage.py matt_audit scalability             # Scalability review
python manage.py matt_audit best_practices          # Code quality checks
python manage.py matt_audit maintainability         # Code health analysis
python manage.py matt_audit accessibility           # Accessibility review
python manage.py matt_audit bundle                  # Bundle size and startup time
python manage.py matt_audit context                 # Generate LLM context
```

Options:

| Option | Default | Description |
|--------|---------|-------------|
| `--level` | `standard` | Strictness: `relaxed`, `standard`, `strict`, `paranoid` |
| `--format` | `text` | Output: `text`, `json`, `markdown`, `sarif` |
| `--output` | stdout | Write report to file |
| `--ci` | `false` | Exit non-zero if issues found |
| `--fail-on` | `critical` | Min severity to fail: `critical`, `high`, `medium`, `low`, `info` |
| `--exclude` | None | Glob patterns to exclude (repeatable) |
| `--diff` | None | Only audit files changed since this git ref |
| `--fix` | `false` | Apply safe auto-fixes |
| `--fix-preview` | `false` | Show what would be auto-fixed |
| `--for` | `generic` | For `context`: optimize for `claude`, `gpt`, or `generic` |

---

## Migration Baselines (`matt_baseline`)

Create and load SQL schema baselines to dramatically speed up fresh database setup.

```bash
# Create a baseline from current database state
python manage.py matt_baseline create v1.0.0 --notes "Release 1.0 schema"

# Load a baseline on a fresh database (skips running all migrations)
python manage.py matt_baseline load v1.0.0

# List available baselines
python manage.py matt_baseline list

# Verify integrity
python manage.py matt_baseline verify v1.0.0

# Delete
python manage.py matt_baseline delete v1.0.0
```

---

## Migration Analysis (`matt_migrate`)

Analyze, profile, and safely accelerate migrations in large projects.

```bash
python manage.py matt_migrate --stats             # Show project migration statistics
python manage.py matt_migrate --profile           # Profile pending migrations, estimate time
python manage.py matt_migrate --parallel          # Run pending migrations in parallel waves
python manage.py matt_migrate --check             # Detect unsafe DDL in pending migrations
python manage.py matt_migrate --check --rewrite   # Show safe rewrites for unsafe patterns
python manage.py matt_migrate --graph             # Show migration dependency graph
python manage.py matt_migrate --graph --format mermaid  # Mermaid diagram output
python manage.py matt_migrate --check-cycles      # Detect circular dependencies
python manage.py matt_migrate --check-conflicts   # Detect branch conflicts
python manage.py matt_migrate --app myapp         # Filter to a specific app
```

---

## Migration Squashing (`matt_squash`)

Smart migration squashing with preview and safety checks.

```bash
# Preview what would be squashed
python manage.py matt_squash myapp 0001 0042 --preview

# Execute the squash
python manage.py matt_squash myapp 0001 0042

# Find squash opportunities across all apps
python manage.py matt_squash --analyze

# Squash all apps up to a git tag boundary
python manage.py matt_squash --all --to-tag v1.0.0
```

---

## Documentation Tools (`matt_docs`)

Analyze and improve code documentation coverage.

```bash
python manage.py matt_docs coverage              # Show coverage stats (default threshold: 80%)
python manage.py matt_docs coverage --ci         # Exit non-zero if below threshold
python manage.py matt_docs coverage --threshold 90  # Custom threshold
python manage.py matt_docs stubs                 # Generate docstring stubs for all modules
python manage.py matt_docs stubs --module core   # Generate for a specific module
python manage.py matt_docs stubs --style google  # Docstring style: google, numpy, sphinx
python manage.py matt_docs hints                 # Find missing type hints
```
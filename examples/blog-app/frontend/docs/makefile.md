# Makefile Commands Reference

This document provides a comprehensive guide to all available Makefile commands in the React Vite Boilerplate project.

## Quick Start

```bash
# Show all available commands
make help

# Show commands by category
make help-all

# Setup project with all dependencies
make setup

# Start development server
make dev
```

## Command Categories

### Development Commands (`make help-dev`)

| Command          | Description                                      |
| ---------------- | ------------------------------------------------ |
| `make install`   | Install dependencies with Bun                    |
| `make dev`       | Start development server                         |
| `make dev-open`  | Start dev server and open browser                |
| `make dev-debug` | Start dev server with debug mode                 |
| `make dev-https` | Start development server with HTTPS              |
| `make dev-host`  | Start development server accessible from network |
| `make build`     | Build for production                             |
| `make preview`   | Preview production build                         |

### Testing Commands (`make help-test`)

| Command              | Description             |
| -------------------- | ----------------------- |
| `make test`          | Run tests               |
| `make test-ui`       | Run tests with UI       |
| `make test-coverage` | Run tests with coverage |

### Shadcn/ui Commands (`make help-shadcn`)

#### Individual Component Management

| Command                                      | Description                     |
| -------------------------------------------- | ------------------------------- |
| `make setup-shadcn`                          | Setup Shadcn/ui components      |
| `make add-shadcn-component COMPONENT=button` | Add a specific component        |
| `make shadcn-list`                           | List all available components   |
| `make shadcn-update`                         | Update all shadcn/ui components |

#### Bulk Component Installation

| Command                  | Description                                                             |
| ------------------------ | ----------------------------------------------------------------------- |
| `make shadcn-common`     | Install common components (button, input, card, badge, avatar)          |
| `make shadcn-forms`      | Install form components (form, input, textarea, select, etc.)           |
| `make shadcn-data`       | Install data display components (table, pagination, badge, etc.)        |
| `make shadcn-navigation` | Install navigation components (navigation-menu, breadcrumb, tabs, etc.) |
| `make shadcn-feedback`   | Install feedback components (alert, dialog, toast, etc.)                |
| `make shadcn-layout`     | Install layout components (aspect-ratio, resizable, scroll-area, etc.)  |
| `make shadcn-all`        | Install all component categories                                        |

#### Examples

```bash
# Add a specific component
make add-shadcn-component COMPONENT=button

# Install all form-related components
make shadcn-forms

# Install everything
make shadcn-all
```

### Django Integration Commands (`make help-django`)

#### Build & Deployment

| Command             | Description                                                    |
| ------------------- | -------------------------------------------------------------- |
| `make django-prep`  | Prepare build for Django static files integration              |
| `make django-build` | Build and prepare for Django with proper static file structure |

#### API Integration

| Command                                                          | Description                                   |
| ---------------------------------------------------------------- | --------------------------------------------- |
| `make api-schema`                                                | Download API schema from Django backend       |
| `make api-types`                                                 | Generate TypeScript types from OpenAPI schema |
| `make api-client`                                                | Generate API client from schema               |
| `make django-types SCHEMA_URL=http://localhost:8000/api/schema/` | Generate types from Django API schema         |

#### Configuration Helpers

| Command                | Description                                           |
| ---------------------- | ----------------------------------------------------- |
| `make cors-setup`      | Generate CORS configuration helper for Django         |
| `make django-urls`     | Generate Django URL configuration helper              |
| `make django-settings` | Generate Django settings helper for React integration |
| `make django-all`      | Generate all Django integration helpers               |

#### Examples

```bash
# Download schema and generate types
make api-schema
make api-types

# Generate Django configuration files
make django-all

# Build for Django deployment
make django-build
```

### Docker Commands (`make help-docker`)

| Command             | Description                                     |
| ------------------- | ----------------------------------------------- |
| `make docker-build` | Build Docker image                              |
| `make docker-run`   | Run Docker container                            |
| `make docker-stop`  | Stop Docker container                           |
| `make docker-dev`   | Run development environment with Docker Compose |

### Utility Commands (`make help-utils`)

#### Code Generation

| Command                           | Description                    |
| --------------------------------- | ------------------------------ |
| `make component NAME=MyComponent` | Generate a new React component |
| `make hook NAME=useMyHook`        | Generate a custom React hook   |

#### Development Tools

| Command                | Description                        |
| ---------------------- | ---------------------------------- |
| `make storybook-init`  | Initialize Storybook               |
| `make storybook`       | Start Storybook development server |
| `make storybook-build` | Build Storybook for production     |

#### Security & Performance

| Command                 | Description                        |
| ----------------------- | ---------------------------------- |
| `make security-audit`   | Run security audit                 |
| `make performance-test` | Run Lighthouse CI performance test |

#### Maintenance

| Command              | Description                       |
| -------------------- | --------------------------------- |
| `make update-all`    | Update all dependencies and tools |
| `make reset-project` | Reset project to clean state      |

#### Git Utilities

| Command          | Description                              |
| ---------------- | ---------------------------------------- |
| `make git-setup` | Setup Git repository with initial commit |
| `make git-hooks` | Setup Git hooks                          |

#### Environment Management

| Command          | Description                            |
| ---------------- | -------------------------------------- |
| `make env-setup` | Copy environment file from example     |
| `make env-dev`   | Create development environment file    |
| `make env-prod`  | Create production environment template |
| `make env-all`   | Create all environment files           |

#### Examples

```bash
# Generate a new component
make component NAME=UserCard

# Generate a custom hook
make hook NAME=useLocalStorage

# Update everything
make update-all

# Setup development environment
make env-all
```

## Django Integration Workflow

### 1. Initial Setup

```bash
# Generate Django configuration helpers
make django-all
```

This creates configuration files in `docs/django-integration/`:

- `cors-settings.py` - CORS configuration for Django
- `urls-example.py` - URL routing example
- `settings-example.py` - Django settings for React integration

### 2. API Integration

```bash
# Download API schema (make sure Django server is running)
make api-schema

# Generate TypeScript types
make api-types

# Generate API client
make api-client
```

### 3. Build for Django

```bash
# Build React app for Django static files
make django-build
```

This creates a `dist/static/` directory that can be copied to your Django `STATIC_ROOT`.

### 4. Environment Variables

Set these environment variables for API integration:

```bash
# For schema download
export DJANGO_SCHEMA_URL=http://localhost:8000/api/schema/
# or
export SCHEMA_URL=http://localhost:8000/api/schema/

# Then run
make api-schema
```

## Advanced Usage

### Chaining Commands

```bash
# Full project setup
make clean && make install && make shadcn-common && make env-all

# Complete Django integration setup
make django-all && make api-schema && make api-types

# Pre-deployment checks
make check-all && make build && make django-prep
```

### Custom Component Generation

```bash
# Generate a component with proper structure
make component NAME=ProductCard
# Creates:
# - src/components/productcard/ProductCard.tsx
# - src/components/productcard/index.ts
```

### Performance Monitoring

```bash
# Run full performance audit
make build && make performance-test
```

## Environment Variables

The Makefile respects these environment variables:

- `SCHEMA_URL` or `DJANGO_SCHEMA_URL` - API schema endpoint
- `DEBUG` - Enable debug mode for development server

## Tips

1. **Use tab completion**: Most shells support tab completion for Makefile targets
2. **Chain commands**: Use `&&` to chain multiple commands
3. **Check help**: Use `make help-<category>` to see specific command groups
4. **Environment files**: Always run `make env-setup` after cloning the project

## Troubleshooting

### Common Issues

1. **Command not found**: Make sure you have Bun installed
2. **Permission denied**: Check file permissions or run with appropriate privileges
3. **API schema download fails**: Ensure your Django server is running and accessible
4. **Component generation fails**: Check that the target directory is writable

### Getting Help

```bash
# Show all commands
make help

# Show specific category
make help-shadcn
make help-django
make help-utils

# Show all commands organized by category
make help-all
```

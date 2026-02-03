# matt Command Reference

The `matt` CLI is a modern, feature-rich command-line tool for Django Matt projects.

## Overview

```bash
matt [OPTIONS] COMMAND [ARGS]...
```

## Global Options

| Option | Description |
|--------|-------------|
| `--version`, `-V` | Show version and exit |
| `--help` | Show help message and exit |

## Command Groups

### Development

| Command | Description |
|---------|-------------|
| `matt serve` | Start the development server |
| `matt dev` | Alias for `matt serve` |
| `matt shell` | Open Django interactive shell |

### Database

| Command | Description |
|---------|-------------|
| `matt db migrate` | Run database migrations |
| `matt db make` | Create new migrations |
| `matt db show` | Show migration status |
| `matt db reset` | Reset the database |
| `matt db seed` | Seed database with data |
| `matt db dump` | Export database to fixture |
| `matt db squash` | Squash migrations |

### Code Generation

| Command | Description |
|---------|-------------|
| `matt new controller` | Generate an API controller |
| `matt new schema` | Generate Pydantic schemas |
| `matt new service` | Generate a service layer |
| `matt new test` | Generate test files |
| `matt crud` | Generate full CRUD for a model |
| `matt new api` | Create a new API project |

### Type Generation

| Command | Description |
|---------|-------------|
| `matt types ts` | Generate TypeScript interfaces |
| `matt types zod` | Generate Zod schemas |
| `matt types swift` | Generate Swift Codable structs |
| `matt types client` | Generate typed API client |
| `matt types watch` | Watch mode for type generation |

### Analysis

| Command | Description |
|---------|-------------|
| `matt analyze` | Full project analysis |
| `matt analyze models` | List all Django models |
| `matt analyze routes` | List all API routes |
| `matt routes` | Alias for `analyze routes` |
| `matt endpoints` | Alias for `analyze routes` |

### Status & Diagnostics

| Command | Description |
|---------|-------------|
| `matt status` | Show project status |
| `matt doctor` | Run project diagnostics |

### Deployment

| Command | Description |
|---------|-------------|
| `matt deploy fly` | Deploy to Fly.io |
| `matt deploy railway` | Deploy to Railway |
| `matt deploy render` | Deploy to Render |
| `matt deploy docker` | Generate Docker configuration |
| `matt deploy build` | Build Docker image |
| `matt deploy up` | Start Docker containers |
| `matt deploy down` | Stop Docker containers |

### AI Context

| Command | Description |
|---------|-------------|
| `matt ai` | Generate AI context files |

## Usage Examples

### Basic Usage

```bash
# Show help
matt --help

# Show version
matt --version

# Start development server
matt serve

# Start on custom port
matt serve --port 8080

# Run migrations
matt db migrate

# Generate CRUD
matt crud myapp.Product
```

### Advanced Usage

```bash
# Generate full CRUD with wizard
matt crud myapp.Product --wizard

# Watch for type changes
matt types ts --watch --output frontend/types/api.ts

# Deploy to Fly.io
matt deploy fly --app myapp

# Run diagnostics
matt doctor --fix
```

## Interactive Banner

When run without arguments, `matt` displays an interactive banner:

```
     ___  _                          __  __       _   _
    |   \(_)__ _ _ _  __ _ ___      |  \/  |__ _ | |_| |_
    | |) | / _` | ' \/ _` / _ \     | |\/| / _` ||  _|  _|
    |___// \__,_|_||_\__, \___/     |_|  |_\__,_| \__|\__|
       |__/          |___/

v0.1.0

Available Commands:

+- Development ---------+
| serve   Start the development server
| shell   Open Django interactive shell
| test    Run project tests
+-----------------------+

+- Database ------------+
| db migrate  Run database migrations
| db make     Create new migrations
| db show     Show migration status
| db reset    Reset the database
+-----------------------+

...
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

## Tips and Best Practices

!!! tip "Command Aliases"
    Many commands have shorter aliases:

    - `matt dev` = `matt serve`
    - `matt routes` = `matt analyze routes`
    - `matt endpoints` = `matt analyze routes`

!!! tip "Tab Completion"
    Install shell completion for faster workflow:
    ```bash
    matt --install-completion
    ```

!!! warning "Project Root"
    The `matt` CLI looks for `manage.py` to identify project root.
    Run commands from your project directory or a subdirectory.

## See Also

- [Server Commands](serve.md)
- [Database Commands](database.md)
- [Code Generation](generate.md)
- [Type Generation](types.md)

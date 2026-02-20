# sync_types Command

Synchronize types between Django and frontend with automatic code generation.

!!! tip "See Also"
    For CLI equivalent commands, see [matt types](types.md).

## Usage

```bash
python manage.py sync_types --target typescript --output frontend/types
```

## Options

| Option | Description |
|--------|-------------|
| `--target`, `-t` | Target language (`typescript`, `ts`, `zod`, `swift`, `api-client`, `all`) |
| `--output`, `-o` | Output file path |
| `--apps`, `-a` | Comma-separated list of Django apps to scan |
| `--modules`, `-m` | Comma-separated list of Python modules to scan for schemas |
| `--models` | Include Django models (not just Pydantic schemas) |
| `--camel-case` | Convert field names to camelCase |
| `--base-url` | Base URL for API client (default: /api) |
| `--include-react-query` | Include React Query hooks in API client |
| `--include-swr` | Include SWR hooks in API client |

### Watch Mode Options

| Option | Description |
|--------|-------------|
| `--watch`, `-w` | Watch for changes and regenerate automatically |
| `--watch-interval` | Polling interval in seconds (default: 1.0) |
| `--watch-dirs` | Comma-separated directories to watch (auto-detected if not specified) |
| `--debounce` | Debounce delay in seconds for watch mode (default: 0.5) |
| `--force-polling` | Force polling mode instead of watchdog (for debugging) |
| `--clear-screen` | Clear screen before each regeneration in watch mode |

## Examples

### Basic Generation

```bash
# Generate TypeScript interfaces
python manage.py sync_types --target typescript --output frontend/src/types/api.ts --apps myapp

# Generate Zod schemas for runtime validation
python manage.py sync_types --target zod --output frontend/src/schemas/api.ts --apps myapp

# Generate Swift types for iOS
python manage.py sync_types --target swift --output ios/Generated/Models.swift --apps myapp

# Generate all formats at once
python manage.py sync_types --target all --output frontend/types --apps myapp
```

### Watch Mode

The watch mode automatically regenerates types when your Python files change. It uses [watchdog](https://pypi.org/project/watchdog/) for efficient file system monitoring when available, with a polling fallback.

```bash
# Basic watch mode (auto-detects directories from --apps/--modules)
python manage.py sync_types --target typescript --output frontend/types --apps myapp --watch

# Watch specific directories
python manage.py sync_types --target typescript --output frontend/types --watch --watch-dirs myapp,otherapp

# Customize debounce and interval
python manage.py sync_types --target typescript --output frontend/types --apps myapp --watch \
    --debounce 1.0 --watch-interval 2.0

# Clear screen on each regeneration (useful for terminals)
python manage.py sync_types --target typescript --output frontend/types --apps myapp --watch --clear-screen

# Force polling mode (useful for debugging or networked file systems)
python manage.py sync_types --target typescript --output frontend/types --apps myapp --watch --force-polling
```

### API Client Generation

```bash
# Generate TypeScript types + fetch-based API client
python manage.py sync_types --target api-client --output frontend/src/api/client.ts --apps myapp

# Include React Query hooks
python manage.py sync_types --target api-client --output frontend/src/api/client.ts \
    --apps myapp --include-react-query

# Include SWR hooks
python manage.py sync_types --target api-client --output frontend/src/api/client.ts \
    --apps myapp --include-swr

# Custom base URL
python manage.py sync_types --target api-client --output frontend/src/api/client.ts \
    --apps myapp --base-url /api/v2
```

### CamelCase Conversion

```bash
# Convert snake_case fields to camelCase (matches JavaScript conventions)
python manage.py sync_types --target typescript --output frontend/types --apps myapp --camel-case
```

### Scanning Specific Modules

```bash
# Scan specific schema modules
python manage.py sync_types --target typescript --modules myapp.schemas,otherapp.schemas

# Combine apps and modules
python manage.py sync_types --target typescript --apps myapp --modules shared.types
```

### Using Config File

You can use a config file to store your code generation settings. Create one with `init_codegen`:

```bash
# Create default config file
python manage.py init_codegen

# Create with specific framework
python manage.py init_codegen --framework svelte

# Create with models from specific apps
python manage.py init_codegen --apps users,posts

# Add config to pyproject.toml instead
python manage.py init_codegen --toml

# Preview config without creating file
python manage.py init_codegen --dry-run
```

Then use the config with sync_types:

```bash
# Use config file (auto-discovers django_matt_codegen.py or pyproject.toml)
python manage.py sync_types --config

# Use specific config file
python manage.py sync_types --config path/to/custom_config.py

# Use config with watch mode
python manage.py sync_types --config --watch
```

Example `django_matt_codegen.py`:

```python
CODEGEN = {
    "framework": "react",
    "ui_library": "shadcn",
    "output_dir": "./frontend/src/generated",
    "models": [
        "users.User",
        {
            "path": "posts.Post",
            "exclude_fields": ["internal_notes"],
            "generate_crud": True,
        },
    ],
    "use_typescript": True,
    "camel_case": True,
    "generate_zod": True,
    "base_url": "/api",
}
```

Or in `pyproject.toml`:

```toml
[tool.django-matt.codegen]
framework = "react"
ui_library = "shadcn"
output_dir = "./frontend/src/generated"
models = ["users.User", "posts.Post"]
use_typescript = true
camel_case = true
generate_zod = true
```

## Watch Mode Details

### How It Works

1. **Initial Generation**: When watch mode starts, it immediately generates the output
2. **File Monitoring**: Watches Python files in specified directories for changes
3. **Debouncing**: Rapid changes are debounced to avoid excessive regeneration
4. **Module Reload**: Changed modules are reloaded to pick up schema changes
5. **Regeneration**: Types are regenerated after each change

### Watchdog vs Polling

- **Watchdog** (default when installed): Uses OS-level file system events for instant detection
- **Polling** (fallback): Periodically checks file modification times

Install watchdog for better performance:
```bash
uv add watchdog
```

### Output During Watch Mode

```
Found 5 Pydantic schemas and 3 Django models
Starting watch mode (watchdog)...
  Debounce: 0.5s, Poll interval: 1.0s
  Watching 2 directories:
    - /path/to/myapp
    - /path/to/otherapp
Performing initial generation...
Generated typescript types to frontend/types/api.ts
Watcher started. Press Ctrl+C to stop.

[14:23:45] Detected 1 file change(s):
  - schemas.py
Regenerating...
[14:23:45] Generated typescript types to frontend/types/api.ts

^C
Stopped watching. Generated 3 time(s) in 127s.
```

## Generated Output Examples

### TypeScript Interface

```typescript
// Auto-generated by django-matt sync_types
// Do not edit manually

export interface User {
  id: number;
  email: string;
  username: string;
  firstName: string | null;
  lastName: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface UserCreate {
  email: string;
  username: string;
  password: string;
  firstName?: string | null;
  lastName?: string | null;
}
```

### Zod Schema

```typescript
// Auto-generated by django-matt sync_types

import { z } from 'zod';

export const UserSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  username: z.string(),
  firstName: z.string().nullable(),
  lastName: z.string().nullable(),
  isActive: z.boolean(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export type User = z.infer<typeof UserSchema>;
```

### Swift Struct

```swift
// Auto-generated by django-matt sync_types

import Foundation

struct User: Codable, Identifiable {
    let id: Int
    let email: String
    let username: String
    let firstName: String?
    let lastName: String?
    let isActive: Bool
    let createdAt: Date
    let updatedAt: Date
}
```

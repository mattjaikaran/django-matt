# sync_types Command

Synchronize types between Django and frontend.

## Usage

```bash
python manage.py sync_types --target typescript --output frontend/types
```

## Options

| Option | Description |
|--------|-------------|
| `--target` | Target language (`typescript`, `swift`) |
| `--output` | Output directory |
| `--watch` | Watch for changes and regenerate |
| `--models` | Specific models to include |

## Examples

```bash
# TypeScript types
python manage.py sync_types --target typescript --output frontend/src/types

# Swift types
python manage.py sync_types --target swift --output ios/Generated

# Watch mode (coming soon)
python manage.py sync_types --target typescript --output frontend/types --watch
```

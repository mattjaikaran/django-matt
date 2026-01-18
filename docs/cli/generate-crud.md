# generate_crud Command

Generate CRUD API from Django models.

## Usage

```bash
python manage.py generate_crud myapp.MyModel
```

## Options

| Option | Description |
|--------|-------------|
| `--output-dir` | Output directory |
| `--components` | Components to generate (`all`, `controller`, `schemas`, `tests`) |
| `--with-tests` | Include test files |
| `--permissions` | Permission class to use |
| `--soft-delete` | Use soft delete |
| `--dry-run` | Preview without writing |

## Examples

```bash
# Basic generation
python manage.py generate_crud myapp.Product

# Full generation with tests
python manage.py generate_crud myapp.Product --components all --with-tests

# Preview changes
python manage.py generate_crud myapp.Product --dry-run
```

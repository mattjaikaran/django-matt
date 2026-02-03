# generate_crud Command

!!! note "Comprehensive Documentation"
    For complete documentation, see [Management: generate_crud](../management/generate-crud.md).

## Quick Reference

Generate CRUD operations for a Django model:

```bash
# Basic CRUD (schemas + controller)
python manage.py generate_crud myapp.Product

# Full generation (all components)
python manage.py generate_crud myapp.Product --full

# Interactive wizard
python manage.py generate_crud --wizard
```

## CLI Equivalent

```bash
matt crud myapp.Product --full
matt crud myapp.Product --wizard
```

## Options Summary

| Option | Default | Description |
|--------|---------|-------------|
| `--full`, `-f` | `false` | Generate all: controller, schema, service, admin, tests |
| `--with-tests`, `-t` | `false` | Generate test file |
| `--with-admin` | `false` | Generate Django Unfold admin |
| `--no-service` | `false` | Skip service layer |
| `--soft-delete` | `false` | Use soft delete |
| `--permissions` | None | Permission classes |
| `--dry-run` | `false` | Preview without writing |
| `--wizard`, `-w` | `false` | Interactive wizard |

## Generated Components

With `--full`, generates:

| File | Description |
|------|-------------|
| `schemas.py` | Pydantic schemas (Create, Update, Response, List) |
| `controllers.py` | API controller with all CRUD endpoints |
| `services.py` | Business logic layer |
| `admin.py` | Django Unfold admin configuration |
| `tests.py` | Pytest test cases |

## Example

```bash
python manage.py generate_crud myapp.Product \
  --permissions IsAuthenticated \
  --with-tests \
  --with-admin \
  --soft-delete
```

## See Also

- [Complete generate_crud Documentation](../management/generate-crud.md)
- [CLI: matt crud](generate.md#matt-crud)
- [Controllers Guide](../core/controllers.md)

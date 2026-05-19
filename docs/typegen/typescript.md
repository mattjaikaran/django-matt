# TypeScript Generation

Generate TypeScript interfaces from Pydantic schemas and Django models.

## Quick Start

```bash
python manage.py sync_types --target typescript --output frontend/types/api.ts --apps myapp
```

## How It Works

The `TypeScriptGenerator` class (in `django_matt/typegen/typescript.py`) iterates over
`schema.model_fields` and resolves each field's type using `get_type_hints()` from the
standard library. This correctly handles:

- **Inherited fields** — `get_type_hints()` walks the MRO so fields defined on a base
  class are included even when the subclass does not re-declare them.
- **Forward references** — string annotations (e.g. `"UserSchema"`) are resolved against
  the schema's own module namespace.
- **`X | None` union syntax** — Python 3.10+ `types.UnionType` is detected and emitted
  as `T | null` rather than the older `Optional[T]` form.
- **`EmailStr`** — Pydantic's `EmailStr` type is mapped to `string` (not `any`).

## Type Mapping

| Python / Pydantic type | TypeScript |
|------------------------|------------|
| `str` | `string` |
| `int` | `number` |
| `float` | `number` |
| `bool` | `boolean` |
| `bytes` | `string` |
| `datetime.datetime` | `string` |
| `datetime.date` | `string` |
| `datetime.time` | `string` |
| `decimal.Decimal` | `number` |
| `uuid.UUID` | `string` |
| `EmailStr` | `string` |
| `Optional[T]` / `T \| None` | `T \| null` |
| `list[T]` | `T[]` |
| `dict[K, V]` | `Record<K, V>` |
| `set[T]` | `T[]` |
| `tuple[A, B]` | `[A, B]` |
| `Literal["a", "b"]` | `"a" \| "b"` |
| `Enum` subclass | union of literal values |
| Pydantic `BaseModel` subclass | interface name (cross-reference) |

## Generated Output

Input:

```python
# myapp/schemas.py
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID

class BaseSchema(BaseModel):
    id: UUID
    created_at: datetime

class UserSchema(BaseSchema):
    email: EmailStr
    username: str
    bio: str | None = None
    is_active: bool = True
```

Generated TypeScript (inherited fields resolved via `get_type_hints()`):

```typescript
// Auto-generated TypeScript types from Pydantic schemas
// Do not edit manually - regenerate with sync_types command

export interface UserSchema {
  id: string;
  created_at: string;
  email: string;
  username: string;
  bio: string | null;
  isActive: boolean;  // with --camel-case
}
```

## Programmatic Usage

```python
from django_matt.typegen.typescript import TypeScriptGenerator, generate_typescript

# Simple generation
generator = TypeScriptGenerator()
ts_code = generator.generate([UserSchema, PostSchema])

# With options
generator = TypeScriptGenerator(
    export_style="named",   # "named" (default) → export interface; "default" → no export
    use_interface=True,     # True (default) for interface; False for type aliases
    add_readonly=False,     # Add readonly modifier to all fields
    camel_case=True,        # Convert snake_case to camelCase
    include_validators=False,
)

# Convenience function — writes to file if output_path is given
code = generate_typescript(
    schemas=[UserSchema],
    models=[MyDjangoModel],
    output_path="frontend/src/types/api.ts",
    camel_case=True,
)
```

## Configuration via Settings

```python
# settings.py
DJANGO_MATT = {
    "TYPEGEN": {
        "OUTPUT_DIR": "frontend/src/generated",
        "INCLUDE_ZOD": True,
        "INCLUDE_API_CLIENT": True,
    },
}
```

## Known Fix: Inherited Fields and Forward References

Before the `get_type_hints()` fix, `_generate_field()` read from
`field_info.annotation` directly. That approach returned `str` for forward
references and omitted fields inherited from base classes.

The current implementation calls:

```python
hints = get_type_hints(schema, localns=vars(sys.modules[schema.__module__]))
python_type = hints.get(field_name, Any)
```

This resolves the annotation in the schema's own module namespace, correctly
expanding forward references and walking the MRO for inherited fields.

## See Also

- [sync\_types management command](../management/sync-types.md)
- [Swift Generator](swift.md)
- [Zod Schemas](../codegen/zod-schemas.md)

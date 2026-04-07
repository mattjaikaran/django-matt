# django-matt Migration Tools

Scripts and LLM prompts for migrating existing Django/FastAPI projects to django-matt.

## LLM Prompts

Paste one of these prompts into Claude, GPT, or Copilot along with your existing code:

| File | Source Framework | Use When |
|------|-----------------|----------|
| `llm-prompt-drf.md` | Django REST Framework | Migrating serializers, viewsets, routers, permissions |
| `llm-prompt-ninja.md` | Django Ninja / ninja-extra | Migrating routers, schemas, auth, ninja-crud |
| `llm-prompt-fastapi.md` | FastAPI | Migrating from SQLAlchemy + FastAPI to Django ORM + django-matt |
| `llm-prompt-universal.md` | Any framework | One prompt that auto-detects the source and converts |

### How to use

1. Copy the full contents of the appropriate prompt file
2. Paste it as the system prompt (or first message) in your LLM
3. Paste your source code after it
4. The LLM will produce django-matt equivalents with service layer separation

## Automated Scripts

### `analyze.py` -- Migration report

Scans an existing project and generates a structured migration plan.

```bash
uv run python scripts/migrate/analyze.py /path/to/your/project
```

Output:
- Framework detection (DRF, Ninja, FastAPI)
- Count of models, serializers/schemas, views, routers
- Auth patterns in use
- File-by-file migration map

### `convert.py` -- Mechanical conversion (best-effort)

Generates django-matt stubs from existing code. Not a complete migration -- meant as a starting point.

```bash
# Convert a DRF app
uv run python scripts/migrate/convert.py /path/to/app --framework drf

# Convert and write to output directory
uv run python scripts/migrate/convert.py /path/to/app --framework drf --output ./migrated

# Convert Django Ninja
uv run python scripts/migrate/convert.py /path/to/app --framework ninja

# Convert FastAPI
uv run python scripts/migrate/convert.py /path/to/app --framework fastapi
```

What it generates:
- `schemas.py` -- ModelSchema stubs from serializers
- `controllers.py` -- Controller stubs from viewsets/routers
- `services.py` -- Service layer stubs extracted from view logic
- `urls.py` -- Updated URL configuration

## Migration strategy

1. Run `analyze.py` to understand scope
2. Use `convert.py` to generate stubs
3. Paste complex files into an LLM with the appropriate prompt for manual conversion
4. Wire up `MattAPI` in `urls.py`
5. Run tests, fix what breaks

# Phase 3: CLI and Type Generation - Research

**Researched:** 2026-03-08
**Domain:** Django management commands, Typer CLI, Pydantic type generation, code scaffolding, OpenAPI, DI containers, content negotiation, API versioning
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Generated code patterns (generate_crud)**
- Service layer always — controller is thin, service handles all business logic and ORM
- Async-first — all generated handlers are `async def`, all ORM calls use async variants (`aget`, `asave`, `adelete`, etc.)
- Generated tests use pytest + AsyncAPITestClient with full CRUD coverage (list, create, read, update, patch, delete)
- `--full` generates: controller, schema, service, admin (Unfold), tests

**Project scaffolding (startapi)**
- Template-driven: templates (basic, b2b, saas) determine how much is generated
- Basic template: settings.py with django-matt configured, a single API app, urls.py
- b2b/saas templates: include auth, multitenancy, billing scaffolding, docker-compose, Makefile, CI config, CLAUDE.md

**Type generation (sync_types)**
- Default path: read directly from Pydantic schemas and Django models (fast, no OpenAPI dependency)
- `--from-openapi` flag: generate from OpenAPI spec for guaranteed no-drift verification
- Separate targets: `--target typescript` for interfaces, `--target zod` for Zod schemas, `--target swift` for Codable structs
- API client generator: fetch-based (native fetch with typed wrappers, no dependencies)
- Swift target: generates Codable structs AND typed URLSession/async-await API client (full SDK experience)

**AI context export (generate_ai_context)**
- Layered depth: `--depth minimal` (routes only), `--depth standard` (routes + types), `--depth full` (everything: routes, types, model relationships, conventions, settings overview)
- Tailored per tool: CLAUDE.md optimized for Claude (detailed, structured), .cursorrules follows Cursor conventions (rules-based), .copilot-instructions follows GitHub Copilot format
- JSON format available via `--format json` or `--format all` (useful for MCP servers, custom tooling, agent pipelines)
- `--include-examples` flag pulls actual controller/schema/test snippets from the user's codebase

**CLI UX**
- `matt doctor`: Error / Warning / Info tiers — Errors = broken (missing settings, import failures), Warnings = suboptimal (no cache backend, debug=True in prod), Info = suggestions
- `matt routes`: compact table (Method | Path | Handler), `--verbose` for schema details (request/response types)
- All commands work non-interactively with flags (CI-friendly); `--wizard` or `-w` enables interactive mode
- Django-ninja migration tool (`matt migrate-from ninja`): auto-rewrite imports and simple patterns + TODO markers where manual review is needed

### Claude's Discretion
- Exact Rich table formatting and color scheme across CLI commands
- OpenAPI schema generation implementation details
- DI container ContextVar scoping internals
- Content negotiation parser/renderer registration mechanism
- API versioning strategy implementation details (URL, header, query param)
- Static-before-parameterized URL ordering algorithm
- Watch mode debouncing and file change detection

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DX-01 | `startapi` CLI command scaffolds new project with template selection (basic, b2b, etc.) | Command exists at `management/commands/startapi.py`; needs completion of b2b/saas templates with CLAUDE.md, CI config |
| DX-02 | `generate_crud` generates controller, schema, service, admin, and tests from model | Command exists at `management/commands/generate_crud.py`; generated code must use async ORM, pass ruff without modifications |
| DX-03 | `sync_types` generates TypeScript types from Django models and Pydantic schemas | `typegen/typescript.py` + `TypeScriptGenerator` working; needs `--from-openapi` flag and drift verification |
| DX-04 | `sync_types` generates Swift types for iOS/macOS clients | `typegen/swift.py` + `SwiftGenerator` working; needs full SDK (structs + async API client) |
| DX-05 | `sync_types` generates Zod schemas for frontend runtime validation | `typegen/zod.py` + `ZodGenerator` working; verify correct Zod syntax and import |
| DX-06 | `generate_ai_context` exports project structure, types, routes for LLM consumption | Command exists; needs `--depth` flag (minimal/standard/full) and `--include-examples` |
| DX-07 | Rich CLI with `matt info`, `doctor`, `routes`, `models`, `new` commands | Typer CLI app with Rich exists at `cli/main.py`; `doctor` and `routes` need Error/Warning/Info tiers and `--verbose` |
| DX-08 | CLI migration tool rewrites django-ninja imports/patterns to django-matt with TODO markers | `migrate-from` command in `cli/main.py` delegates to management command; rewrite logic needs implementation |
| DX-09 | Async test client with `force_authenticate()` using async token creation | `AsyncAPITestClient` at `testing/client.py` already uses `acreate_access_token()` — this is DONE per Phase 1 |
| DX-10 | Test factories and assertion helpers for common API testing patterns | `testing/` module complete with `ModelFactory`, `UserFactory`, assertions, generators — DONE |
| DX-11 | Example apps demonstrating all major features (todo, ecommerce, saas-starter, realtime-chat) | All four example apps exist in `examples/`; need to verify they use current APIs and pass linting |
| CORE-01 | Router supports async and sync view registration with automatic URL generation | `core/router.py` exists; verify static-before-parameterized ordering (CORE-11 link) |
| CORE-02 | Controller pattern provides class-based API endpoints with decorator-driven routing | `core/controller.py` exists; verify `_setup_methods()` single-pass DI+error wrapping |
| CORE-04 | CRUD ViewSet generates list/create/read/update/delete endpoints from model + schema | `views/viewset.py` + `views/list.py`, `create.py`, etc. all exist; tests pass |
| CORE-05 | OpenAPI 3.1 schema auto-generated from routes, schemas, and type hints | `openapi/schema.py` exists; needs verification all routes are introspected correctly |
| CORE-06 | Swagger UI and ReDoc served at configurable endpoints | `openapi/docs.py` exists; needs verification configurable endpoint behavior |
| CORE-11 | Static-before-parameterized URL ordering prevents `/users/me` vs `/users/<id>` conflicts | No dedicated ordering code found in router — this is a gap to implement |
| CORE-13 | DI container with ContextVar-based request scoping | `di/container.py` exists with `ServiceLifetime.SCOPED` using `ContextVar`; tests pass |
| CORE-14 | Content negotiation supporting JSON, XML, CSV, YAML, MsgPack | `negotiation/` module fully exists; tests pass (408 tests include negotiation) |
| CORE-15 | API versioning strategies (URL, header, query param) | `versioning/` module with `URLPathVersioning`, `HeaderVersioning`, `QueryParamVersioning`; tests pass |
</phase_requirements>

---

## Summary

Phase 3 is a **completion and polish phase** for infrastructure that is substantially scaffolded. The codebase contains working implementations of nearly every required component: management commands (`generate_crud`, `sync_types`, `generate_ai_context`, `startapi`), a full Typer CLI (`cli/main.py` with `doctor`, `routes`, `crud`, `ai`, `migrate-from`), type generators (TypeScriptGenerator, ZodGenerator, SwiftGenerator, APIClientGenerator), the CRUD ViewSet, OpenAPI schema generation, DI container, content negotiation, and API versioning. All 4143 tests pass, and the relevant modules (views, DI, versioning, negotiation, openapi, typegen, CLI) are fully green.

The work in this phase is not building from scratch but **making everything fully functional according to the success criteria**: generated code from `generate_crud --full` must pass ruff lint without modification, `sync_types` must add the `--from-openapi` flag for drift verification, `generate_ai_context` needs the `--depth` flag, `matt doctor` needs the Error/Warning/Info tier structure, and `matt routes` needs `--verbose`. The migration tool needs its actual rewrite logic. CORE-11 (static-before-parameterized URL ordering) has no dedicated implementation and must be built.

**Primary recommendation:** Start with `generate_crud --full` generated code quality (DX-02) because it is the highest-visibility success criterion — linting failure on generated code is immediately obvious. Then fix gaps in `sync_types` (DX-03/04/05), `generate_ai_context` depth (DX-06), CLI polish (DX-07), and the migration tool (DX-08). CORE-11 is the only CORE requirement with no existing implementation.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 5.2+ | Management commands, URL routing, ORM | Project foundation |
| Typer | 0.12+ | CLI framework wrapping management commands | Already in use in `cli/main.py` |
| Rich | 13.x | Console output, tables, panels, progress | Already in use, dependency of Typer |
| Pydantic | 2.x | Schema introspection for type generation | Core project dependency |
| ruff | current | Generated code must pass lint without modification | Project linting standard |
| orjson | 3.x | JSON serialization everywhere | Base project dependency — not optional |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| watchdog | optional | File system watching for `--watch` mode | Already integrated in `codegen/watcher.py` |
| questionary | optional | Interactive wizard prompts | Already integrated in `cli/prompts.py` |
| django-unfold | current | Admin registration in generated code | `--full` generates Unfold admin |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native fetch TS client | axios/ky | fetch is dependency-free; decision is locked |
| Direct Pydantic read | OpenAPI round-trip | Direct is faster; `--from-openapi` flag added for drift check |
| questionary prompts | InquirerPy | questionary already integrated |

**Installation:** No new dependencies required — all stack components are already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

The existing structure is correct and should not change:

```
django_matt/
├── management/commands/
│   ├── generate_crud.py      # --full generates 5 files
│   ├── startapi.py           # template-driven project scaffold
│   ├── sync_types.py         # --target ts/zod/swift + --from-openapi
│   └── generate_ai_context.py # --depth minimal/standard/full --format all
├── cli/
│   ├── main.py               # Typer app, all aliases
│   ├── base.py               # GeneratorCommand, MattCommand, InteractiveCommand
│   ├── commands/
│   │   ├── analyze.py        # matt routes (needs --verbose)
│   │   ├── status.py         # matt doctor (needs Error/Warning/Info tiers)
│   │   └── generate.py       # matt crud, matt new
│   └── utils.py              # run_manage_command(), setup_django()
├── typegen/
│   ├── typescript.py         # TypeScriptGenerator
│   ├── zod.py                # ZodGenerator
│   ├── swift.py              # SwiftGenerator
│   └── api_client.py         # APIClientGenerator
└── testing/
    ├── client.py             # APITestClient, AsyncAPITestClient
    ├── factories.py          # UserFactory, OrganizationFactory, etc.
    └── assertions.py         # assert_query_count, assert_status, etc.
```

### Pattern 1: Management Command Code Generation

Generated code from `generate_crud --full` MUST comply with project code style:

```python
# Source: django_matt/management/commands/generate_crud.py pattern
# Generated controller template - must use async ORM throughout
async def list_{model_lower}s(self, request: HttpRequest) -> dict[str, Any]:
    qs = await sync_to_async(list)(
        {ModelName}.objects.select_related(...).prefetch_related(...)
    )
    # OR with Django 5.x async ORM:
    items = [{ModelName}Schema.model_validate(obj) async for obj in qs]
    return {"items": items, "count": len(items)}

async def create_{model_lower}(
    self, request: HttpRequest, data: {ModelName}CreateSchema
) -> {ModelName}Schema:
    obj = await {ModelName}.objects.acreate(**data.model_dump())
    return {ModelName}Schema.model_validate(obj)

async def get_{model_lower}(
    self, request: HttpRequest, id: uuid.UUID
) -> {ModelName}Schema:
    obj = await {ModelName}.objects.aget(id=id)
    return {ModelName}Schema.model_validate(obj)

async def update_{model_lower}(
    self, request: HttpRequest, id: uuid.UUID, data: {ModelName}UpdateSchema
) -> {ModelName}Schema:
    obj = await {ModelName}.objects.aget(id=id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await obj.asave()
    return {ModelName}Schema.model_validate(obj)

async def delete_{model_lower}(
    self, request: HttpRequest, id: uuid.UUID
) -> None:
    await {ModelName}.objects.filter(id=id).adelete()
```

**CRITICAL:** Generated service layer must own ALL ORM calls. Controller calls service, service calls ORM.

### Pattern 2: Type Generation via Pydantic Introspection

```python
# Source: django_matt/typegen/typescript.py
# TypeScriptGenerator reads model_fields (Pydantic v2 API)
for field_name, field_info in schema.model_fields.items():
    annotation = field_info.annotation
    ts_type = python_type_to_typescript(annotation, schema_names=self._schema_names)
    ...
```

Key: use `model_fields` not `__fields__` (Pydantic v2). `get_args()` and `get_origin()` from `typing` for generics.

### Pattern 3: Static-Before-Parameterized URL Ordering (CORE-11)

This is the only CORE requirement with no existing implementation. The algorithm:

```python
# Source: Must be implemented in core/router.py
def _sort_routes(routes: list[Route]) -> list[Route]:
    """Static segments sort before parameterized segments at the same depth."""
    def sort_key(route: Route) -> tuple:
        parts = route.path.strip("/").split("/")
        # Static segment = 0, parameterized (contains < or {) = 1
        return tuple(1 if ("<" in p or "{" in p) else 0 for p in parts)
    return sorted(routes, key=sort_key)
```

This ensures `/users/me` is registered before `/users/<id>` so Django's URL resolver matches static paths first.

### Pattern 4: AsyncAPITestClient in Generated Tests

Generated tests MUST use:

```python
# Source: django_matt/testing/client.py — AsyncAPITestClient.force_authenticate()
@pytest.mark.asyncio
async def test_list_{model_lower}s(async_client, {model_lower}_factory):
    client = AsyncAPITestClient()
    user = await UserFactory.acreate()
    await client.force_authenticate(user)  # uses acreate_access_token()
    response = await client.get("/api/{model_lower}s/")
    assert response.status_code == 200
    data = client.json(response)
    assert "items" in data
```

### Pattern 5: Doctor Command Tier Structure

```python
# Source: django_matt/cli/commands/status.py (to be completed)
class CheckResult:
    tier: Literal["error", "warning", "info"]  # Error=broken, Warning=suboptimal, Info=suggestion
    name: str
    message: str
    fix: str | None = None

# Error tier (must fix): missing SECRET_KEY, import failures, missing INSTALLED_APPS
# Warning tier (should fix): DEBUG=True in production, no cache backend, no HTTPS
# Info tier (suggestion): recommend caching, logging config, etc.
```

### Anti-Patterns to Avoid

- **Sync ORM in generated code:** Never generate `Task.objects.get()` — always `await Task.objects.aget()`. Ruff won't catch this but tests will fail.
- **`__fields__` for Pydantic v2:** Use `model_fields` — `__fields__` is a deprecated v1 compat shim.
- **`json.loads()` in new code:** Use `orjson.loads()` — it is a base dependency, not optional.
- **Blocking `time.sleep()` in watch mode:** Use debounce with `threading.Timer` or `asyncio.sleep`.
- **Hardcoded app names in generated code:** Use `app_label` from `model._meta.app_label` for imports.
- **Generating async tests without `@pytest.mark.asyncio`:** pytest-asyncio requires the decorator or `asyncio_mode=auto` in config (project uses `asyncio_mode=auto` in `pyproject.toml` — no decorator needed).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI framework | Custom argparse wrappers | Typer (already in use) | Help text, subcommands, type coercion are free |
| Rich console output | Custom ANSI codes | Rich + existing `cli/console.py` | Tables, panels, progress all built |
| File watching | Manual poll loop | `codegen/watcher.py` + watchdog | Already handles watchdog fallback to polling |
| Interactive prompts | Custom readline | `cli/prompts.py` (questionary) | Already has select, multiselect, autocomplete |
| Generator base | Custom file writing | `GeneratorCommand` in `cli/base.py` | `--dry-run`, `--force`, file tracking are free |
| Type name conversion | Custom regex | `typegen/utils.py` (snake_to_camel, etc.) | Already tested and handles edge cases |

**Key insight:** The entire scaffolding infrastructure is complete and tested. Phase 3 work is wiring existing generators to produce correct output and closing small gaps, not building new infrastructure.

---

## Common Pitfalls

### Pitfall 1: Generated Code Failing Ruff Lint

**What goes wrong:** Generated string templates have import ordering, unused imports, or UP-rule violations (e.g., `typing.Optional` instead of `X | None`, `typing.List` instead of `list`).
**Why it happens:** Python template strings in the generator don't go through ruff before being written.
**How to avoid:** Run `ruff check --fix` on generated files in tests as part of DX-02 verification. Use modern Python 3.12 syntax in all templates: `list[X]` not `List[X]`, `X | None` not `Optional[X]`.
**Warning signs:** Any generated file uses `from typing import List, Dict, Optional` — these are UP006/UP007 violations.

### Pitfall 2: Generated Tests Not Running Async Properly

**What goes wrong:** Generated test file uses `async def test_...` but pytest runs it synchronously (returns coroutine object, never executes).
**Why it happens:** Forgetting that `pytest-asyncio` with `asyncio_mode=auto` is required, or the conftest is not in scope.
**How to avoid:** The project `pyproject.toml` already sets `asyncio_mode = "auto"` — generated tests do NOT need `@pytest.mark.asyncio`. Verify this in pyproject.toml before generating decorators.
**Warning signs:** Tests "pass" with 0 assertions because the coroutine is returned without awaiting.

### Pitfall 3: Swift SDK Missing `CodingKeys` for snake_case

**What goes wrong:** Generated Swift structs use `snake_case` field names from Python, but URLSession's JSONDecoder doesn't automatically convert to Swift convention.
**Why it happens:** The existing `SwiftGenerator` generates plain struct property names without `CodingKeys` or the `convertFromSnakeCase` decoder strategy.
**How to avoid:** The existing `APIClient.swift` in `startapi` already uses `decoder.keyDecodingStrategy = .convertFromSnakeCase`. Ensure generated model file specifies the same decoder strategy or uses `CodingKeys`. Swift target must produce usable `Codable` structs that work with the `APIClient.swift` decoder.
**Warning signs:** Decoding fails at runtime because `created_at` (Python) maps to `createdAt` (Swift key strategy) but struct property is named `created_at`.

### Pitfall 4: Ruff Lint Error in Existing Codebase

**What goes wrong:** `uv run ruff check django_matt/` finds `F401` in `benchmarks/reporters.py` (unused `StringIO` import).
**Why it happens:** Pre-existing lint issue not caught in CI.
**How to avoid:** Fix this as part of Plan 03-01 Wave 0 cleanup. `uv run ruff check --fix django_matt/` resolves it.
**Warning signs:** Any plan's lint verification step fails on this file.

### Pitfall 5: `--from-openapi` Flag Requires Running App

**What goes wrong:** `sync_types --from-openapi` requires Django to be running or at least importable with all models to generate the OpenAPI schema.
**Why it happens:** OpenAPI generation introspects live URL patterns.
**How to avoid:** Use `django.setup()` before OpenAPI introspection. The management command context already does this. Document that `--from-openapi` requires `python manage.py sync_types` not `matt types ts --from-openapi` (Typer runs outside Django).
**Warning signs:** Import errors or `Apps not ready` errors when running from Typer CLI context without Django setup.

### Pitfall 6: CORE-11 Static URLs Must Be Registered First

**What goes wrong:** Django's URL resolver tries patterns in registration order. If `/users/<id>/` is registered before `/users/me/`, then `GET /users/me` matches the parameterized route with `id="me"` and raises `ValueError`.
**Why it happens:** Python `list.append()` order is insertion order — controllers may register routes in arbitrary order.
**How to avoid:** The `_sort_routes()` function must be called in `APIRouter.get_urls()` before returning URL patterns, not at registration time.
**Warning signs:** `GET /users/me` returns a 404 or 422 (UUID parse error) instead of the expected response.

---

## Code Examples

Verified patterns from existing source:

### Async ORM Pattern (required in all generated code)

```python
# Source: existing controller examples in examples/todo_app/controllers.py
# List with async iteration
items = [TaskSchema.model_validate(obj) async for obj in Task.objects.all()]

# Get single object
obj = await Task.objects.aget(id=task_id)

# Create
obj = await Task.objects.acreate(**data.model_dump())

# Update
obj = await Task.objects.aget(id=task_id)
for k, v in data.model_dump(exclude_unset=True).items():
    setattr(obj, k, v)
await obj.asave()

# Delete
await Task.objects.filter(id=task_id).adelete()
```

### GeneratorCommand File Writing Pattern

```python
# Source: django_matt/cli/base.py GeneratorCommand.write_file()
# Handles --dry-run, --force, conflict detection, file tracking
self.write_file(
    path=app_dir / "controllers" / f"{model_lower}.py",
    content=self._render_controller_template(model, schema),
    preview=True,  # Shows content in dry-run
)
self.show_summary()  # Prints created/modified/skipped summary
```

### TypeScript Type Generation

```python
# Source: django_matt/typegen/typescript.py
generator = TypeScriptGenerator(camel_case=False)
ts_code = generator.generate([UserSchema, ProductSchema])
# Produces:
# export interface UserSchema {
#   id: string;
#   email: string;
#   created_at: string;
# }
```

### Zod Schema Generation

```python
# Source: django_matt/typegen/zod.py
generator = ZodGenerator(camel_case=False)
zod_code = generator.generate([UserSchema])
# Produces:
# export const UserSchemaSchema = z.object({
#   id: z.string().uuid(),
#   email: z.string().email(),
#   created_at: z.string().datetime(),
# });
# export type UserSchema = z.infer<typeof UserSchemaSchema>;
```

### Doctor Command Check Pattern

```python
# Source: django_matt/cli/commands/status.py (existing pattern to extend)
def _check_django_settings() -> dict:
    """Returns: {passed: bool, tier: 'error'|'warning'|'info', message: str}"""
    try:
        from django.conf import settings
        if not hasattr(settings, 'SECRET_KEY'):
            return {"passed": False, "tier": "error", "message": "SECRET_KEY not configured"}
        if settings.SECRET_KEY == 'change-me':
            return {"passed": True, "tier": "warning", "message": "SECRET_KEY is default value"}
        return {"passed": True, "tier": "info", "message": "Settings OK"}
    except Exception as e:
        return {"passed": False, "tier": "error", "message": f"Django not configured: {e}"}
```

### Static-Before-Parameterized Sort (CORE-11)

```python
# Source: Must be implemented in core/router.py APIRouter.get_urls()
import re

_PARAM_PATTERN = re.compile(r"<[^>]+>|{[^}]+}")

def _static_first_key(url_pattern_str: str) -> tuple[int, ...]:
    """
    Returns sort key: static segments score 0, parameterized segments score 1.
    Shorter (more-static) paths sort first at same depth.
    """
    parts = url_pattern_str.strip("/").split("/")
    return tuple(1 if _PARAM_PATTERN.search(p) else 0 for p in parts)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `typing.Optional[X]` | `X \| None` | Python 3.10+ / PEP 604 | Generated code must use new syntax (ruff UP007) |
| `typing.List[X]` | `list[X]` | Python 3.9+ / PEP 585 | Generated code must use builtin generics (ruff UP006) |
| `__fields__` (Pydantic v1) | `model_fields` (Pydantic v2) | Pydantic 2.0 | Type generators must use v2 API |
| `json.loads()` | `orjson.loads()` | Project decision | All new code uses orjson |
| Factory Boy | Built-in `ModelFactory` | Phase 2 completion | No factory-boy dependency; use `django_matt.testing.model_factory` |
| Faker | Built-in `DataGenerator`/`fake` | Phase 2 completion | No Faker dependency; use `django_matt.testing.generators` |

**Deprecated/outdated:**
- `utils/errors.py`: Deleted in Phase 1. Use `django_matt.core.errors` only.
- `DJANGO_ALLOW_ASYNC_UNSAFE=True`: Removed in Phase 1. All async ORM must use async variants.
- Sync `create_access_token()` in `AsyncAPITestClient`: Fixed in Phase 1. Uses `acreate_access_token()`.

---

## Open Questions

1. **`--depth` flag vs `--format` flag in `generate_ai_context`**
   - What we know: CONTEXT.md specifies `--depth minimal/standard/full` as a new flag
   - What's unclear: The existing command has `--format all/claude/cursor/copilot/json` which controls output format, not depth. The `--depth` flag is additive, not replacing.
   - Recommendation: Add `--depth` as a separate argument; `--format` controls which files are generated, `--depth` controls how much content goes into each file.

2. **`--from-openapi` flag implementation**
   - What we know: The existing `sync_types` reads Pydantic schemas directly; `--from-openapi` must generate from OpenAPI spec
   - What's unclear: Whether to call `OpenAPISchema.build()` directly (requires django setup + route registration) or read from a pre-generated `openapi.json` file
   - Recommendation: Call `OpenAPISchema.build()` in-process (management command context has Django set up). Add `--openapi-file` as an alternative for CI that has a pre-generated schema file.

3. **Example apps (DX-11) current state**
   - What we know: All four example apps exist (`todo_app`, `ecommerce-api`, `saas-starter`, `realtime-chat`) with substantive code
   - What's unclear: Whether they import from current django-matt APIs or from older patterns; whether they pass ruff lint
   - Recommendation: Plan 03-03 should run `ruff check examples/` and fix any violations. Don't rewrite examples; just update API calls that changed in Phases 1-2.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-django 4.11.1 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_typegen.py tests/test_management_commands.py tests/test_cli_module.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

**Important:** `asyncio_mode = "auto"` is set in `pyproject.toml`. Generated async tests do NOT need `@pytest.mark.asyncio`.

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DX-01 | `startapi` creates project with correct files for each template | integration | `pytest tests/test_management_commands.py -k "startapi" -x` | Partial — extend `test_management_commands.py` |
| DX-02 | `generate_crud --full` output passes `ruff check` | integration+lint | `pytest tests/test_management_commands.py -k "generate_crud" -x` | Partial — add ruff lint assertion |
| DX-03 | `sync_types --target typescript` produces valid TS for all schemas | unit+integration | `pytest tests/test_typegen.py -k "typescript" -x` | YES |
| DX-04 | `sync_types --target swift` produces valid Codable structs + API client | unit | `pytest tests/test_typegen.py -k "swift" -x` | YES |
| DX-05 | `sync_types --target zod` produces valid Zod schema syntax | unit | `pytest tests/test_typegen.py -k "zod" -x` | YES |
| DX-06 | `generate_ai_context --format all` produces CLAUDE.md, .cursorrules, introspection.json | integration | `pytest tests/test_ai_context.py tests/test_ai_context_enhanced.py -x` | YES |
| DX-07 | `matt doctor` reports errors/warnings/info; `matt routes` lists routes | integration | `pytest tests/test_management_commands.py -k "doctor or routes" -x` | Partial — extend |
| DX-08 | `matt migrate-from ninja` rewrites imports, adds TODO markers | unit | `pytest tests/test_management_commands.py -k "migrate_from" -x` | Partial — extend |
| DX-09 | `AsyncAPITestClient.force_authenticate()` uses `acreate_access_token` | unit | `pytest tests/test_testing_module.py -k "authenticate" -x` | YES |
| DX-10 | Factories and assertions work | unit | `pytest tests/test_testing_module.py -x` | YES (67 tests pass) |
| DX-11 | Example apps pass ruff lint | lint | `uv run ruff check examples/` | Needs verification |
| CORE-01 | Router registers async and sync handlers | unit | `pytest tests/test_core_controller.py -x` | YES |
| CORE-02 | Controller DI+error wrapping in single closure | unit | `pytest tests/test_di_autowire.py -x` | YES |
| CORE-04 | ViewSet generates all 5 CRUD endpoints | unit | `pytest tests/test_views.py -x` | YES (passes) |
| CORE-05 | OpenAPI schema includes all routes | unit | `pytest tests/test_openapi.py -x` | YES |
| CORE-06 | Swagger/ReDoc served at configurable path | unit | `pytest tests/test_openapi.py -k "docs or swagger or redoc" -x` | YES |
| CORE-11 | Static routes sorted before parameterized | unit | `pytest tests/test_core_controller.py -k "static" -x` | NO — Wave 0 |
| CORE-13 | DI container resolves Scoped services per-request | unit | `pytest tests/test_di.py -x` | YES (passes) |
| CORE-14 | Content negotiation returns correct format per Accept header | unit | `pytest tests/test_negotiation.py -x` | YES (passes) |
| CORE-15 | URL/header/query versioning extract correct version | unit | `pytest tests/test_versioning.py -x` | YES (passes) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_typegen.py tests/test_management_commands.py tests/test_cli_module.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_core_controller.py` — add `test_static_before_parameterized_url_order` — covers CORE-11
- [ ] `tests/test_management_commands.py` — add `test_generate_crud_full_passes_ruff` — covers DX-02 success criterion
- [ ] `tests/test_management_commands.py` — add `test_startapi_b2b_template_files` — covers DX-01 b2b/saas templates
- [ ] Fix pre-existing lint: `uv run ruff check --fix django_matt/benchmarks/reporters.py`

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `django_matt/management/commands/generate_crud.py` — complete CRUD generator with wizard mode
- Direct code inspection: `django_matt/management/commands/sync_types.py` — full TS/Zod/Swift generation with watch mode
- Direct code inspection: `django_matt/management/commands/generate_ai_context.py` — multi-format AI context export
- Direct code inspection: `django_matt/cli/main.py` — complete Typer app with all command aliases
- Direct code inspection: `django_matt/cli/base.py` — GeneratorCommand, InteractiveCommand base classes
- Direct code inspection: `django_matt/typegen/typescript.py`, `zod.py`, `swift.py`, `api_client.py` — all generators
- Direct code inspection: `django_matt/testing/client.py` — AsyncAPITestClient with `acreate_access_token`
- Test execution: 333 tests (typegen + management_commands + cli_module) — all pass
- Test execution: 128 tests (codegen + ai_context) — all pass
- Test execution: 408 tests (views + di + versioning + negotiation + openapi) — all pass
- Test execution: 67 tests (testing_module) — all pass
- Lint check: `uv run ruff check django_matt/` — 1 pre-existing fixable error in `benchmarks/reporters.py`

### Secondary (MEDIUM confidence)
- Project CONTEXT.md decisions — locked implementation choices for this phase
- REQUIREMENTS.md traceability table — confirmed DX-01 through DX-11 and CORE requirements map to Phase 3

### Tertiary (LOW confidence)
- None — all findings verified from source code

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in use from existing code
- Architecture: HIGH — patterns derived from existing passing implementation
- Pitfalls: HIGH — Pitfalls 1-5 confirmed from code inspection; Pitfall 6 (CORE-11) confirmed by absence of sorting in router
- Gaps: HIGH — CORE-11 absence confirmed; `--depth` flag absence in `generate_ai_context` confirmed; `--from-openapi` flag absence in `sync_types` confirmed

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable stack; no fast-moving dependencies)

---

## Key Findings Summary

1. **All 4143 tests pass** — the codebase is in good shape entering Phase 3
2. **Most Phase 3 work is completion, not creation** — all required modules exist with substantial implementation
3. **CORE-11 is the only missing implementation** — no static-before-parameterized URL sorting exists in `core/router.py`
4. **Generated code quality (DX-02) is the critical path** — generated files must pass ruff lint without modification; templates use `typing.Optional` and `List` (must be updated to Python 3.12 syntax)
5. **1 pre-existing ruff lint error** in `django_matt/benchmarks/reporters.py` (unused `StringIO` import) — fix as Wave 0 cleanup
6. **AsyncAPITestClient is complete** (DX-09) — `acreate_access_token()` is already in use; this requirement is satisfied from Phase 1
7. **DX-10 testing module is complete** — 67 tests pass, all factories and assertions work
8. **`sync_types` needs `--from-openapi` flag** and `generate_ai_context` needs `--depth` flag — these are additive to working commands
9. **Example apps (DX-11) exist** but need lint verification — `uv run ruff check examples/` should be run as part of Plan 03-03
10. **`pyproject.toml` sets `asyncio_mode = "auto"`** — generated test files must NOT include `@pytest.mark.asyncio` decorators

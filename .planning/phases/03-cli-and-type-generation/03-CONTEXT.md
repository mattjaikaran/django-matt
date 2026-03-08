# Phase 3: CLI and Type Generation - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete scaffolding commands (generate_crud, startapi), TypeScript/Swift/Zod type generation from running app, AI context export for LLM coding tools, and Rich CLI commands to inspect the project. Also complete core framework modules: router, controller, CRUD ViewSet, OpenAPI, DI container, content negotiation, API versioning, and static-before-parameterized URL ordering. Fix async test client. Build django-ninja migration tool. The codebase has substantial scaffolding for all of these — the work is making them fully functional, passing linting, and producing correct output.

</domain>

<decisions>
## Implementation Decisions

### Generated code patterns (generate_crud)
- Service layer always — controller is thin, service handles all business logic and ORM
- Async-first — all generated handlers are `async def`, all ORM calls use async variants (`aget`, `asave`, `adelete`, etc.)
- Generated tests use pytest + AsyncAPITestClient with full CRUD coverage (list, create, read, update, patch, delete)
- `--full` generates: controller, schema, service, admin (Unfold), tests

### Project scaffolding (startapi)
- Template-driven: templates (basic, b2b, saas) determine how much is generated
- Basic template: settings.py with django-matt configured, a single API app, urls.py
- b2b/saas templates: include auth, multitenancy, billing scaffolding, docker-compose, Makefile, CI config, CLAUDE.md

### Type generation (sync_types)
- Default path: read directly from Pydantic schemas and Django models (fast, no OpenAPI dependency)
- `--from-openapi` flag: generate from OpenAPI spec for guaranteed no-drift verification
- Separate targets: `--target typescript` for interfaces, `--target zod` for Zod schemas, `--target swift` for Codable structs
- API client generator: fetch-based (native fetch with typed wrappers, no dependencies)
- Swift target: generates Codable structs AND typed URLSession/async-await API client (full SDK experience)

### AI context export (generate_ai_context)
- Layered depth: `--depth minimal` (routes only), `--depth standard` (routes + types), `--depth full` (everything: routes, types, model relationships, conventions, settings overview)
- Tailored per tool: CLAUDE.md optimized for Claude (detailed, structured), .cursorrules follows Cursor conventions (rules-based), .copilot-instructions follows GitHub Copilot format
- JSON format available via `--format json` or `--format all` (useful for MCP servers, custom tooling, agent pipelines)
- `--include-examples` flag pulls actual controller/schema/test snippets from the user's codebase

### CLI UX
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

</decisions>

<specifics>
## Specific Ideas

- CLI should feel like `gh` CLI — flags-first, non-interactive by default, wizard mode for discovery
- Swift type gen should be a full SDK experience (structs + API client), not just model definitions
- AI context should be comprehensive enough that an LLM can generate correct django-matt code from the exported context alone
- Migration tool should be safe and transparent — never silently produce incorrect code, always leave TODO markers for ambiguous rewrites

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Typer CLI app** (`django_matt/cli/main.py`): Full Typer app with Rich output, command groups already registered (serve, db, new, types, analyze, deploy, status)
- **TypeScriptGenerator** (`django_matt/typegen/typescript.py`): Existing TS generator with `pydantic_to_typescript`, `django_model_to_typescript`
- **ZodGenerator** (`django_matt/typegen/zod.py`): Existing Zod schema generator with `pydantic_to_zod`
- **SwiftGenerator** (`django_matt/typegen/swift.py`): Existing Swift generator with `pydantic_to_swift`
- **APIClientGenerator** (`django_matt/typegen/api_client.py`): Existing API client generator
- **GeneratorCommand** (`django_matt/cli/base.py`): Base class for generator management commands (provides --force, --dry-run)
- **generate_crud** (`django_matt/management/commands/generate_crud.py`): Existing CRUD generator with wizard mode, service layer support
- **startapi** (`django_matt/management/commands/startapi.py`): Existing project scaffolding command with templates
- **sync_types** (`django_matt/management/commands/sync_types.py`): Existing type sync with config file support and watch mode
- **generate_ai_context** (`django_matt/management/commands/generate_ai_context.py`): Existing AI context generator with format selection
- **Testing module** (`django_matt/testing/`): APITestClient, AsyncAPITestClient, factories, generators, assertions (including assert_query_count from Phase 2)
- **DI container** (`django_matt/di/`): container.py, decorators.py, depends.py, middleware.py
- **Content negotiation** (`django_matt/negotiation/`): config.py, decorators.py, middleware.py, negotiator.py, parsers.py, renderers.py
- **API versioning** (`django_matt/versioning/`): base.py, decorators.py, middleware.py, router.py, schemes.py
- **OpenAPI** (`django_matt/openapi/`): schema.py, docs.py

### Established Patterns
- Management commands extend `BaseCommand` or `GeneratorCommand`
- CLI commands use Typer with Rich console output
- Type generators follow Generator class pattern with `generate()` method
- Async-first: all handlers use async, ORM via aget/asave/adelete

### Integration Points
- CLI `matt` command wraps management commands via `run_manage_command()` utility
- Type generators read from Pydantic BaseModel subclasses and Django model `_meta`
- OpenAPI docs served at configurable endpoints (schema.py + docs.py)
- Example apps in `examples/` directory: todo_app, ecommerce-api, saas-starter, realtime-chat

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-cli-and-type-generation*
*Context gathered: 2026-03-08*

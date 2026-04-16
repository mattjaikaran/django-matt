# Django Matt — Active Tasks

## Up Next — Launch Readiness

### Distribution & Publishing
- [x] PyPI package distribution — `uv build`, twine check pass
- [x] Trusted publisher setup on PyPI — OIDC publishing in release.yml
- [x] Publish to TestPyPI for validation before real publish — TestPyPI → PyPI pipeline
- [x] `django-matt[rust]` optional extra with pre-built wheels — exposed in pyproject.toml as `rust = ["django-matt-rust>=0.1.0 ; platform_machine in ...]`, gracefully degrades to pure-Python via `django_matt/_accel.py` when the wheel isn't installed
- [ ] CI wheel building for Rust extensions (see Rust Extensions below)

### Documentation Site
- [x] MkDocs Material site builds successfully (`uv run mkdocs build`)
- [x] Deploy docs site (GitHub Pages) — `.github/workflows/docs.yml`
- [x] Fix broken links — 0 warnings in strict mode
- [x] Add version switcher for future releases — `mkdocs.yml` already declares `extra.version.provider: mike`; `.github/workflows/release.yml` now runs `mike deploy MAJOR.MINOR --update-aliases latest` on every tag push so each release adds a new entry to the mike-powered dropdown

### Example App Refresh
- [x] Update example apps with new modules (interceptors, events, streaming)
  - devplatform: SSE streaming analytics, interceptors+exception filters on gateway
  - ecommerce-v2: event bus on orders, domain event handlers
  - saas-starter: interceptors on projects, events on CRUD, SSE notifications
- [x] Add new example: AI chat app with SSE streaming + CQRS — `examples/ai-chat/`
- [x] Add new example: multi-tenant SaaS with events + feature flags — `examples/multitenant-saas/`
- [x] Ensure all examples run with `uv run python manage.py runserver` — all 8 examples (ai-chat, devplatform, ecommerce-api, ecommerce-v2, multitenant-saas, quicktodo, realtime-chat, saas-starter) pass `manage.py check` against the parent workspace. Install deps via `uv sync --group examples` then run from each example dir with `uv run --project ../.. python manage.py check`. saas-starter's `api/*.py` controllers still target an early API shape (`@api_controller`, `@APIController.post`) and need porting before they can be re-registered — main.py has a placeholder root route.

### Polish
- [x] Ruff lint pass — all source clean (0 errors)
- [x] Fix: AnalyticsDatabaseBackend.group() used non-existent field, now uses metadata
- [x] Fix: test_create_and_str assertion matched truncated session_id
- [x] Fix: test_get_session_metrics_with_data date range didn't include auto_now_add sessions
- [x] Full test suite confirmation — 6342 passed, 52 skipped, 0 failed
- [x] Type check pass (pyright) — 0 errors (pyrightconfig.json + code fixes)
- [x] Review all LLM migration prompts for accuracy — fixed @api.controller() → class attrs + register_controller()

### Community Prep
- [x] LICENSE file (Apache 2.0)
- [x] CONTRIBUTING.md — contribution guidelines, PR process, code style
- [x] Issue templates (bug report, feature request)
- [x] PR template
- [x] GitHub repo settings (topics, description, social preview) — declared in `.github/repo-settings.yml`; apply with `scripts/apply_repo_settings.sh` (requires `gh` + `yq`). Social preview image must still be uploaded manually to Settings → General → Social preview.

---

## Future Enhancements

Priority order: launch-critical → differentiators → ecosystem → nice-to-have.

### Open Source Launch
Get from v0.8.0 to a proper public release people can actually find and use.

- [ ] Launch blog post / announcement — what it is, why it exists, what's different (for dev.to, Reddit, HN)
- [ ] Social preview image for GitHub repo
- [ ] Short demo video — `startapi` → running API with auth, CRUD, admin in 2 minutes
- [ ] Discord or GitHub Discussions for community
- [ ] `django-matt` landing page (single page, could be the docs index)
- [ ] PyPI classifiers and metadata polish
- [ ] Security policy (SECURITY.md) — vulnerability reporting process

### Performance CI & Regression Gates
Benchmarks exist but aren't enforced — a regression should block merge.

- [x] Benchmark CI job — `.github/workflows/benchmark.yml` runs on every PR
- [x] Performance budget — `--fail-on-regression` flag + CI gate: PRs blocked if any benchmark regresses >5% vs last main baseline (fetched via `dawidd6/action-download-artifact`)
- [x] Memory profiling — RSS avg/peak sampled via psutil during bench_servers.py load; `--fail-on-memory-growth` gate wired into benchmark.yml
- [x] Publish benchmark results to GitHub Pages (charts over time) — `scripts/publish_bench_charts.py` generates Chart.js dashboard at `docs/benchmarks/live.html`; Docs workflow pulls benchmark artifacts and rebuilds on every benchmark run

### Starter Templates & Scaffolding
`startapi` works but more templates = faster adoption.

- [x] `--template api-only` — minimal REST API (no admin, no frontend)
- [x] `--template ai-saas` — AI chat app with SSE, CQRS, vector search, billing
- [x] `--template marketplace` — multi-vendor with Stripe Connect
- [x] `--template internal-tools` — admin-heavy, HTMX, audit logging
- [x] Template registry — `matt templates list` shows available, `matt new --template <name>`

### Code Review Agent (`django_matt/review/`)
Automated code audit agent — static analysis + optional LLM review for Django best practices, SOLID, complexity, security, modularity, and AI-friendliness.

#### Foundation
- [x] `review/__init__.py` — module exports
- [x] `review/findings.py` — Finding dataclass, Severity enum, Category enum
- [x] `review/config.py` — ReviewConfig: thresholds, ignore patterns, rulesets
- [x] `review/analyzers/base.py` — BaseAnalyzer protocol
- [x] `review/engine.py` — ReviewEngine orchestrates analyzers, collects/deduplicates findings

#### Analyzers (AST-based, zero external deps)
- [x] `review/analyzers/complexity.py`
- [x] `review/analyzers/solid.py`
- [x] `review/analyzers/django.py`
- [x] `review/analyzers/ai_friendly.py`
- [x] `review/analyzers/security.py`
- [x] `review/analyzers/modularity.py`
- [x] `review/analyzers/performance.py`
- [x] `review/analyzers/async_safety.py`, `n_plus_one.py`, `migration_safety.py`, `api_design.py` (added in enhance review PR)

#### Reporters
- [x] `review/reporters/console.py`
- [x] `review/reporters/markdown.py`
- [x] `review/reporters/json_reporter.py`
- [x] `review/reporters/github.py`

#### Management Command & AI
- [x] `matt_review` management command
- [x] `review/ai_reviewer.py` — optional LLM-powered review

#### Tests
- [x] `tests/test_review/` — 154 tests across analyzers, engine, reporters, config, command

### AI/LLM Context & Agent Support
Make django-matt projects first-class citizens for AI-assisted development and autonomous agents.

- [x] Enhanced `generate_ai_context` — full route map, schemas, auth, examples in JSON (`--format all`)
- [x] Agent-friendly API introspection endpoint — `/_matt/introspection` with section filtering
- [x] MCP server generator — `python manage.py generate_mcp_server` creates MCP server from introspection
- [x] Cursor rules / Claude instructions auto-generation — `generate_ai_context --format claude/cursor/copilot`
- [x] IDE context file watcher — `generate_ai_context --watch` with debounced auto-updates
- [x] LLM-optimized error messages — structured error responses with fix suggestions (commits e8dd538, cac010e)
- [x] `matt ai context` CLI — `python manage.py matt ai --format all`

**Why:** AI agents and IDE copilots are the primary consumers of framework documentation now. A framework that generates its own perfect context files gives developers (and their AI tools) an immediate productivity advantage. This is a differentiator — no other Django framework does this well.

### Production Server Backends (Robyn / Granian)
Replace gunicorn+uvicorn with Rust-native ASGI servers for lower latency and simpler deployment.

- [x] Abstract server backend interface — `django_matt/servers/` with registry
- [x] Robyn integration — `robyn_backend.py`
- [x] Granian integration — `granian_backend.py`
- [x] Auto-detect best server — registry picks installed backend
- [x] `matt serve` CLI command — `matt_serve.py`
- [x] Dockerfile templates per server backend (robyn, granian, gunicorn) — `DockerfileGenerator` installs the chosen backend wheel and renders backend-specific CMD; `--server` flag wired into `deploy docker` and `deploy config --platform docker`
- [x] Benchmark suite — compare request/s, p50/p95/p99 latency across uvicorn/gunicorn/granian (`benchmarks/bench_servers.py` + `make bench-servers`); robyn skipped (own framework, not generic ASGI host); memory profiling deferred to next item
- [ ] Docs: server backend selection guide with tradeoffs

**Why:** Gunicorn is a process manager written in Python wrapping uvicorn workers. Robyn and Granian are Rust-native servers that handle HTTP parsing, connection management, and worker orchestration in compiled code. This removes an entire Python layer from the hot path. Combined with django-matt's existing Rust extensions (router dispatch, JWT, serialization), the full request pipeline from TCP accept to response write can be predominantly Rust.

**Why not a full Rust rewrite:** Django's value is its ecosystem — ORM, migrations, admin, auth, middleware, 20 years of battle-tested packages. Rewriting that in Rust trades the framework's biggest strength for speed gains on code that isn't the bottleneck (DB queries and network I/O dominate latency). The right approach is Rust at the edges (server, hot paths) and Python where it matters (business logic, ORM, ecosystem).

### Automated Migration Tooling
LLM migration prompts exist — add codemods that actually do the rewrite.

- [x] `matt migrate-from drf` — `codemods/drf.py`
- [x] `matt migrate-from ninja` — `codemods/ninja.py`
- [x] `matt migrate-from fastapi` — `codemods/fastapi.py`
- [x] Dry-run mode with diff preview before applying changes
- [x] Migration report — what was converted, what needs manual review

### Published Client SDKs
The typegen and RPC modules generate code — ship pre-built SDK packages too.

- [x] TypeScript SDK generator — `sdkgen/typescript.py`
- [x] Swift SDK generator — `sdkgen/swift.py`
- [x] Python SDK generator — `sdkgen/python_sdk.py`
- [ ] SDK versioning tied to API schema hash (auto-bump on breaking changes)
- [x] SDK generation as part of CI — publish on tag — `scripts/generate_sdks.py` produces TS/Python/Swift packages from `sdk-reference/openapi.json`; release.yml runs generate→npm publish / PyPI publish / GitHub release asset attach on every `vX.Y.Z` tag

### Plugin Ecosystem
Module system exists — build the ecosystem around it.

- [x] `matt plugin init <name>` — `plugins/scaffold.py` + `matt_plugin` command
- [x] Plugin discovery / registry — `plugins/registry.py`, `plugins/loader.py`, `plugins/hooks.py`
- [ ] Example plugins: `django-matt-stripe-webhooks`, `django-matt-clerk-auth`, `django-matt-resend`
- [ ] Plugin compatibility matrix (django-matt version × plugin version)

### Rust Extensions (Deferred)
- [ ] CI wheel building — GitHub Actions manylinux/macOS/Windows (7.0.4)
- [ ] RSA/EC JWT signing in Rust (7.2.2 — deferred, `cryptography` pkg already Rust-based)
- [ ] Wire Rust query string parser into filtering/ordering/pagination middleware (7.4.3)

### Renderers & Frontend
- [ ] Vue renderer (Stage 12D.4)
- [ ] Svelte renderer (Stage 12D.5)
- [ ] Astro framework support
- [ ] Remix framework support

### Database
- [ ] PlanetScale support (Stage 9B.6)

### Infrastructure
- [ ] Kubernetes/Helm chart generation (Stage 9C.3)

### AI/ML Providers
- [ ] vLLM integration (Stage 10C.2)
- [ ] llama.cpp integration (Stage 10C.3)
- [ ] LocalAI integration (Stage 10C.4)

---

## DX Enhancement Roadmap

Priority: high-impact DX wins that address the most common Django pain points.

### Zero-Config Defaults & Convenience Commands
Things Django should ship with but doesn't. We fill the gap.

- [ ] **Default rate limiting preset** — `MATT_THROTTLE_DEFAULTS = "standard"` enables sensible per-IP/per-user/per-endpoint limits out of the box (100/min anon, 1000/min auth, 10/min login). Throttling module exists but requires manual config.
- [ ] **`cache_clear` management command** — `python manage.py cache_clear [--backend default] [--prefix ...]` to purge cache. Django's cache framework has no built-in clear command.
- [x] **`matt shell+` enhanced shell** — `matt_shell.py`
- [x] **`matt dbshell+`** — `matt_dbshell.py`
- [ ] **Login-by-email config toggle** — `MATT_AUTH = {"login_field": "email"}` switches the default User auth to email-based login without custom user model gymnastics. Wire into AuthController, JWT, admin login.
- [ ] **`matt check --strict`** — run system checks + config validation + import verification in one pass (combines `check`, `validate_api`, `check_settings`)

### Vite & Modern Asset Pipeline
The #1 cited gap vs Rails/Laravel. No Django answer exists that isn't a third-party hack.

- [ ] **`django_matt/vite/` module** — Vite integration for Django
  - [ ] `manifest.py` — parse Vite manifest.json, resolve asset URLs, cache busting
  - [ ] `config.py` — ViteConfig: dev server URL, build output dir, entry points, HMR settings
  - [ ] `templatetags/vite.py` — `{% vite_asset "main.js" %}`, `{% vite_hmr_client %}`, `{% vite_react_refresh %}`
  - [ ] `middleware.py` — ViteDevMiddleware: proxy to Vite dev server in development
  - [ ] `management/commands/vite_build.py` — `python manage.py vite_build` (wraps vite build with Django env)
  - [ ] `management/commands/vite_dev.py` — `python manage.py vite_dev` (starts Vite + Django dev server together)
- [ ] **CSS framework integration** — component form fields emit classes for Tailwind, Bootstrap, Shadcn/ui out of the box
- [ ] **Static file fingerprinting** — content-hash URLs for cache busting without Vite (simple mode)

### Inertia.js Adapter
Server-driven SPA without an API. Huge DX win for Django + React/Vue/Svelte.

- [ ] **`django_matt/inertia/` module** — first-class Inertia.js support
  - [ ] `middleware.py` — InertiaMiddleware: handle X-Inertia headers, version checking, partial reloads
  - [ ] `response.py` — `inertia(component, props)` response helper, lazy/deferred props
  - [ ] `share.py` — shared data (flash messages, auth user, CSRF) injected into every Inertia response
  - [ ] `ssr.py` — optional SSR support via Node.js subprocess
  - [ ] `views.py` — InertiaView mixin, @inertia decorator for function views
  - [ ] `templatetags/inertia.py` — `{% inertia %}` root div tag
  - [ ] `testing.py` — InertiaTestCase: assert_inertia_component, assert_inertia_props
- [ ] Integration with django-matt auth — auto-share authenticated user + permissions

### Unpoly Integration
Lightweight alternative to Inertia for server-rendered apps that want SPA-like UX.

- [ ] **`django_matt/unpoly/` module** — Unpoly server-side helpers
  - [ ] `middleware.py` — detect Unpoly requests (X-Up-* headers), set response headers (X-Up-Target, X-Up-Events)
  - [ ] `decorators.py` — `@up_target`, `@up_layer`, `@up_fail_target`
  - [ ] `response.py` — UnpolyResponse: layer control, event emission, cache eviction
  - [ ] `templatetags/unpoly.py` — `{% up_current %}` nav helpers, `{% up_config %}`

### Predicate-Based Permissions (django-rules Style)
RBAC is role-to-permission mapping. Predicates are composable boolean logic. Both are needed.

- [ ] **`django_matt/rules/` module** — predicate-based authorization
  - [ ] `predicates.py` — Predicate base, `@predicate` decorator, AND/OR/NOT composition (`&`, `|`, `~`)
  - [ ] `builtins.py` — `is_authenticated`, `is_superuser`, `is_staff`, `is_owner`, `is_group_member`, `is_active`
  - [ ] `permissions.py` — `add_perm`, `remove_perm`, `has_perm`, `perm_exists` — global permission registry
  - [ ] `mixins.py` — `PermissionRequiredMixin` for views, `ObjectPermissionMixin` for per-object checks
  - [ ] `decorators.py` — `@permission_required("app.change_post")` that uses predicate registry
  - [ ] `backends.py` — `RulesBackend` — Django auth backend that delegates to predicate registry
  - [ ] Integration with django-matt controllers — `permission_predicates = [is_owner | is_admin]` on APIController

### Hybrid Properties (SQLAlchemy-Style)
Computed properties that work in Python AND at the database level.

- [ ] **`django_matt/db/hybrid.py`** — hybrid property descriptor
  - [ ] `@hybrid_property` — property that works on instances AND in querysets
  - [ ] `@hybrid_property.expression` — define the SQL expression equivalent
  - [ ] `HybridManager` — queryset mixin that resolves hybrid properties in filter()/order_by()/annotate()
  - [ ] Support for comparisons: `Model.objects.filter(full_name="John Doe")` generates `Concat(F('first_name'), Value(' '), F('last_name'))`
- [ ] Docs with side-by-side SQLAlchemy comparison

### Model Refactoring Tools
Moving models between apps is one of Django's biggest pain points.

- [ ] **`matt refactor move-model`** — move a model from one app to another
  - [ ] Generate migration in source app (CreateModel + DeleteModel with db_table preservation)
  - [ ] Generate migration in target app with dependency on source migration
  - [ ] Update all ForeignKey/M2M references across the project
  - [ ] Update imports across the project
  - [ ] `--dry-run` mode showing what would change
- [ ] **`matt refactor rename-model`** — rename model + update all references + generate migration
- [ ] **`matt refactor split-app`** — extract models from a fat app into a new one
- [ ] **`matt refactor merge-apps`** — merge two apps into one with migration chain preservation

### Strict Template Mode
Django's silent variable failure is a debugging nightmare. Opt-in strictness.

- [ ] **`django_matt/templates/strict.py`** — strict template engine
  - [ ] `StrictEngine` — subclass of DjangoTemplates that raises on undefined variables
  - [ ] `MATT_TEMPLATES = {"strict": True}` config option
  - [ ] `StrictContext` — context class that raises `UndefinedVariableError` instead of returning `""`
  - [ ] Dev-mode integration: show which template, which line, which variable is undefined
  - [ ] Allowlist: `{% allow_undefined var1 var2 %}` for intentionally optional variables

### Enhanced CLI Scaffolding
Angular CLI-style generation for individual components, not just full CRUD.

- [ ] **`matt generate model`** — `python manage.py matt generate model myapp.Product --fields "name:str price:decimal category:fk:Category"` → model + migration
- [ ] **`matt generate controller`** — scaffold an APIController with typed endpoints
- [ ] **`matt generate service`** — service layer class with async methods
- [ ] **`matt generate schema`** — Pydantic schema from existing model or from scratch
- [ ] **`matt generate test`** — test file with fixtures and basic test cases for a given model/controller
- [ ] **`matt generate middleware`** — async middleware skeleton
- [ ] **`matt generate migration`** — data migration template with forwards/backwards
- [ ] **`matt generate factory`** — test factory for a model using factory_boy patterns
- [ ] All generators respect existing code — append to files, don't overwrite

### File Storage Redesign
Current storage works but lacks modern features. S3 presigned URLs, chunked uploads, resumable.

- [ ] **Chunked/resumable uploads** — `django_matt/files/chunked.py`: tus-protocol compatible upload handler
  - [ ] `TusUploadView` — handles PATCH/HEAD/POST per tus spec
  - [ ] `ChunkedUploadMiddleware` — chunk assembly, resume state
  - [ ] S3 multipart upload integration — use S3 native multipart for large files
- [ ] **Presigned URL generation** — `storage.presigned_url(key, expires=3600)` for direct client-to-S3 uploads
- [ ] **Image processing pipeline** — `@process_image(resize=(800, 600), format="webp", quality=85)` on upload fields
- [ ] **R2/MinIO/Backblaze B2 backends** — beyond S3, expand storage options
- [ ] **Storage events** — emit events on upload/delete/access for audit trail integration
- [ ] **File metadata** — auto-extract MIME type, dimensions, duration (for video/audio), store alongside

### DEP-0014 Background Workers Compatibility
Django is getting native background workers. Our tasks module should be the best way to use them.

- [ ] **`DjangoWorkersBackend`** — new backend in `django_matt/tasks/backends/` that uses Django's native `django.core.workers` when available (Django 6.0+)
- [ ] Auto-detection: if Django >= 6.0 and `django.core.workers` is available, use it as default backend (no Celery/Dramatiq needed)
- [ ] Graceful fallback: if workers not available, fall back to configured backend
- [ ] Same `@task` / `@periodic_task` decorator API regardless of backend — zero migration needed
- [ ] Docs: when to use native workers vs Celery vs Dramatiq (decision guide)

### Dev Server & HMR Enhancement
The dev experience should rival `rails server` or `php artisan serve`.

- [ ] **`matt dev`** — unified dev command that starts Django + Vite + file watcher + Tailwind JIT in one process
- [ ] **Browser error overlay** — dev middleware that injects error overlay HTML on 500s (like Next.js/Vite)
- [ ] **Request inspector panel** — dev toolbar showing request/response, SQL queries, cache hits, time breakdown
  - Integration with existing `django_matt/inspector/` module
- [ ] **Auto-reload on migration** — detect model changes, prompt to makemigrations + migrate
- [ ] **Port auto-detection** — if 8000 is taken, try 8001, 8002, etc.

### Modern Forms Integration
Django forms are stuck in 2010. Bridge the gap without replacing them entirely.

- [ ] **Form → Component bridge** — `form_to_components(MyDjangoForm)` converts Django Form to django-matt Component tree
  - [ ] Respects field types, validators, help_text, error messages
  - [ ] Outputs Tailwind/Shadcn classes by default (theme-configurable)
- [ ] **Client-side validation** — generate Zod/Yup schema from Django form validators for frontend validation
- [ ] **`@ajax_form`** — decorator that makes Django form views return JSON on HTMX/fetch requests
- [ ] **Form builder** — `FormBuilder("contact").text("name").email("email").textarea("message").submit("Send")` fluent API

### Content & Data Export
Common operations every Django project needs.

- [ ] **`matt export`** — `python manage.py matt export myapp.Model --format csv/json/xlsx --filter status=active`
- [ ] **`matt import`** — `python manage.py matt import myapp.Model data.csv --dry-run`
- [ ] **`matt fixtures`** — generate realistic test fixtures using Faker, respecting model relationships
- [ ] **`matt seed`** — populate dev database with realistic data from fixture definitions

---

## Completed (2026-04-06)

### Session 1 — 13 New Modules (555 tests)
- [x] Interceptors — composable request/response wrappers (32 tests)
- [x] SSE/Streaming — sse_response(), stream_json(), stream_text() (30 tests)
- [x] Config validation namespaces — Pydantic-validated settings at startup (45 tests)
- [x] Route-scoped middleware — per-controller/per-route (34 tests)
- [x] Layered exception filters — route/controller/global scope (28 tests)
- [x] Event bus / Pub/Sub — async typed events with wildcard matching (41 tests)
- [x] Serialization groups — role-based field visibility (34 tests)
- [x] Auto-instrumentation — zero-config tracing + metrics (51 tests)
- [x] Secrets-as-code — pluggable backends (env, vault, AWS, GCP, encrypted file) (80 tests)
- [x] Infrastructure introspection — health checks, K8s probes (33 tests)
- [x] RPC typed client — Python/TS client generation (60 tests)
- [x] Module system — plugin architecture with dependency resolution (51 tests)
- [x] CQRS — command/query buses with middleware (36 tests)

### Session 2 — Infrastructure & Test Coverage
- [x] Slim mode — MattAPI(mode="minimal/slim/full"), LazyModuleProxy, StartupProfiler (77 tests)
- [x] Framework comparison benchmarks — route, schema, request lifecycle (`make bench-compare`)
- [x] Python 3.14 CI matrix — Django 6.0 with continue-on-error
- [x] Test coverage: auth (118), billing (114), multitenancy (136), views (37), flags (68), analytics (68), experiments (96), graphql (56), management commands (57)

### Session 3 — Release Tooling & Bug Fixes
- [x] Automated versioning — `versioning_tool.py` bump major/minor/patch
- [x] Changelog generation — `changelog_gen.py` parses conventional commits
- [x] Makefile targets — `release-patch`, `release-minor`, `release-major`, `changelog`
- [x] README polish — badges, feature tables, examples, "What's New in 0.8"
- [x] Fix: AnalyticsSession.page_views FK conflict (13 skipped tests now pass)
- [x] Fix: auth/magic_link.py get() → filter().first() for duplicate emails
- [x] Fix: 5 test isolation issues (username collisions, hardcoded version)
- [x] Full test suite: 6141 passed, 133 skipped, 0 failed

### Session 4 — Documentation Blitz
- [x] CHANGELOG.md — [Unreleased] section with all new features
- [x] ROADMAP.md — all completed items checked off
- [x] Architecture & diagrams — 7 new mermaid diagrams, 6 new architecture sections
- [x] 17 new module docs (interceptors, streaming, events, exceptions, serialization, secrets, introspection, rpc, modules, cqrs, slim-mode, config validation, middleware, observability spans/collectors/exporters)
- [x] AI context docs — all 8 files updated with new modules
- [x] mkdocs.yml — 26 missing directories added to navigation (88 new nav entries)
- [x] 6 tutorials — REST API, SaaS, realtime, AI streaming, testing, service layer
- [x] 7 cookbook recipes — interceptors, streaming, events, CQRS, security, performance, deployment
- [x] 6 concept guides — request lifecycle, DI, async patterns, error handling, module architecture
- [x] 4 stub files expanded — schemas, models, mixins, templates
- [x] 5 migration/comparison docs — from DRF, Django Ninja, FastAPI, framework comparison
- [x] 7 advanced guides — production checklist, scaling, security, performance tuning, custom extensions, best practices
- [x] LLM migration scripts — 4 prompt files (DRF, Ninja, FastAPI, universal), analyze.py, convert.py
- [x] Service layer docs — enhanced patterns, migration guide, deep-dive tutorial
- [x] Version set to 0.8.0 (pre-launch)

---

## Enhancement Plan (All Complete)

### Phase 1: Error Handling & Correctness ✅
- [x] 1.1–1.5 all complete

### Phase 2: Schema & OpenAPI Improvements ✅
- [x] 2.1–2.8 all complete

### Phase 3: Controller & View Enhancements ✅
- [x] 3.1–3.5 all complete

### Phase 4: DX & Compatibility ✅
- [x] 4.1–4.6 all complete

### Phase 5: Testing Enhancements ✅
- [x] 5.1–5.5 all complete

### Phase 6: Architectural Verification ✅
- [x] 6.1–6.7 all complete

### Phase 7: Rust Native Extensions ✅ (1.9x E2E speedup)
- [x] 7.0–7.6 all complete (3 items deferred — CI wheels, RSA/EC JWT, query parser integration)

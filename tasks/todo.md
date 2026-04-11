# Django Matt — Active Tasks

## Up Next — Launch Readiness

### Distribution & Publishing
- [x] PyPI package distribution — `uv build`, twine check pass
- [x] Trusted publisher setup on PyPI — OIDC publishing in release.yml
- [x] Publish to TestPyPI for validation before real publish — TestPyPI → PyPI pipeline
- [ ] `django-matt[rust]` optional extra with pre-built wheels
- [ ] CI wheel building for Rust extensions (see Rust Extensions below)

### Documentation Site
- [x] MkDocs Material site builds successfully (`uv run mkdocs build`)
- [x] Deploy docs site (GitHub Pages) — `.github/workflows/docs.yml`
- [x] Fix broken links — 0 warnings in strict mode
- [ ] Add version switcher for future releases

### Example App Refresh
- [x] Update example apps with new modules (interceptors, events, streaming)
  - devplatform: SSE streaming analytics, interceptors+exception filters on gateway
  - ecommerce-v2: event bus on orders, domain event handlers
  - saas-starter: interceptors on projects, events on CRUD, SSE notifications
- [x] Add new example: AI chat app with SSE streaming + CQRS — `examples/ai-chat/`
- [x] Add new example: multi-tenant SaaS with events + feature flags — `examples/multitenant-saas/`
- [ ] Ensure all examples run with `uv run python manage.py runserver`

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
- [ ] GitHub repo settings (topics, description, social preview)

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

- [ ] Benchmark CI job — run `make bench-compare` on every PR
- [ ] Performance budget — fail PR if route dispatch, schema validation, or request lifecycle regresses >5%
- [ ] Memory profiling — track RSS per-worker across server backends
- [ ] Publish benchmark results to GitHub Pages (charts over time)

### Starter Templates & Scaffolding
`startapi` works but more templates = faster adoption.

- [ ] `--template api-only` — minimal REST API (no admin, no frontend)
- [ ] `--template ai-saas` — AI chat app with SSE, CQRS, vector search, billing
- [ ] `--template marketplace` — multi-vendor with Stripe Connect
- [ ] `--template internal-tools` — admin-heavy, HTMX, audit logging
- [ ] Template registry — `matt templates list` shows available, `matt new --template <name>`

### AI/LLM Context & Agent Support
Make django-matt projects first-class citizens for AI-assisted development and autonomous agents.

- [x] Enhanced `generate_ai_context` — full route map, schemas, auth, examples in JSON (`--format all`)
- [x] Agent-friendly API introspection endpoint — `/_matt/introspection` with section filtering
- [x] MCP server generator — `python manage.py generate_mcp_server` creates MCP server from introspection
- [x] Cursor rules / Claude instructions auto-generation — `generate_ai_context --format claude/cursor/copilot`
- [x] IDE context file watcher — `generate_ai_context --watch` with debounced auto-updates
- [ ] LLM-optimized error messages — structured error responses with fix suggestions that agents can parse and act on
- [x] `matt ai context` CLI — `python manage.py matt ai --format all`

**Why:** AI agents and IDE copilots are the primary consumers of framework documentation now. A framework that generates its own perfect context files gives developers (and their AI tools) an immediate productivity advantage. This is a differentiator — no other Django framework does this well.

### Production Server Backends (Robyn / Granian)
Replace gunicorn+uvicorn with Rust-native ASGI servers for lower latency and simpler deployment.

- [ ] Abstract server backend interface — `DeploymentConfig.server_backend` enum (`gunicorn`, `robyn`, `granian`)
- [ ] Robyn integration — Rust-native HTTP server, direct ASGI mounting, zero-copy response path
- [ ] Granian integration — Rust HTTP/2 server with RSGIHttpProtocol for ASGI apps
- [ ] Auto-detect best server — pick Robyn/Granian if installed, fall back to gunicorn+uvicorn
- [ ] `matt serve` CLI command — unified entry point: `python manage.py serve --server robyn --workers 4`
- [ ] Dockerfile templates per server backend (robyn, granian, gunicorn)
- [ ] Benchmark suite — compare request/s, p99 latency, memory across all three backends
- [ ] Docs: server backend selection guide with tradeoffs

**Why:** Gunicorn is a process manager written in Python wrapping uvicorn workers. Robyn and Granian are Rust-native servers that handle HTTP parsing, connection management, and worker orchestration in compiled code. This removes an entire Python layer from the hot path. Combined with django-matt's existing Rust extensions (router dispatch, JWT, serialization), the full request pipeline from TCP accept to response write can be predominantly Rust.

**Why not a full Rust rewrite:** Django's value is its ecosystem — ORM, migrations, admin, auth, middleware, 20 years of battle-tested packages. Rewriting that in Rust trades the framework's biggest strength for speed gains on code that isn't the bottleneck (DB queries and network I/O dominate latency). The right approach is Rust at the edges (server, hot paths) and Python where it matters (business logic, ORM, ecosystem).

### Automated Migration Tooling
LLM migration prompts exist — add codemods that actually do the rewrite.

- [ ] `matt migrate-from drf` — AST-based codemod: DRF serializers → Pydantic schemas, ViewSets → Controllers
- [ ] `matt migrate-from ninja` — lighter transform, mostly import rewriting
- [ ] `matt migrate-from fastapi` — route decorators + Depends → DI container
- [ ] Dry-run mode with diff preview before applying changes
- [ ] Migration report — what was converted, what needs manual review

### Published Client SDKs
The typegen and RPC modules generate code — ship pre-built SDK packages too.

- [ ] `django-matt-ts-client` — published bun/npm package generated from RPC module
- [ ] `django-matt-swift-client` — Swift Package Manager distribution
- [ ] SDK versioning tied to API schema hash (auto-bump on breaking changes)
- [ ] SDK generation as part of CI — publish on tag

### Plugin Ecosystem
Module system exists — build the ecosystem around it.

- [ ] `matt plugin init <name>` — scaffold a django-matt plugin package
- [ ] Plugin registry / directory (GitHub-based initially)
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

# Django Matt — Active Tasks

## Launch Readiness — Public Release

### Tier 1: Hard Blockers (must ship before announce)

#### Example Apps — Blog (Priority: Start Here)
- [x] `examples/blog-api/` — Django-matt backend ✅
  - [x] Models: Post, Tag, Category, Comment, AuthorProfile, PostView
  - [x] Draft/publish workflow with status field
  - [x] RSS feed endpoint (`/feed/rss/`)
  - [x] SEO metadata endpoint (`/api/posts/{slug}/seo`)
  - [x] Full-text search endpoint (`/api/posts/search?q=`)
  - [x] View count tracking (deduplicated per session)
  - [x] JWT auth — author vs reader permissions, staff gates
  - [x] Image upload for post cover (ImageField)
  - [x] Pagination + filtering (by tag, category, author, status, featured)
  - [x] `seed_blog` management command with realistic sample data
  - [x] Docker + docker-compose + Makefile + README
  - [x] `sync_types` output committed to repo (`generated.ts` + `generated.schemas.ts`)
- [x] `examples/blog-frontend/` — React+Vite frontend (from `react-vite-boilerplate`) ✅
  - [x] Post listing page with filters
  - [x] Single post page with comments
  - [x] Author dashboard (create/edit/delete own posts)
  - [x] Tag/category browse pages
  - [x] Search UI
  - [x] Auth: login/logout, JWT refresh
  - [x] Uses generated types from `sync_types`
  - [x] `.env.example` pointing at blog-api
  - [x] Boilerplate todos routes/hooks/store removed, builds clean

#### Known Issues — blog-app/api
- [ ] Controllers use `data:` param name but framework requires `body:` — renamed, but `@staticmethod` GET handlers cause `invalid method signature` after removal; needs careful audit against django-matt controller patterns
- [x] `tests/` directory created — 12 model tests pass, API integration tests blocked by controller dispatch issue above

#### Example Apps — Portfolio
- [x] `examples/portfolio-api/` — Django-matt backend ✅
  - [x] Models: Project, Skill, Experience, ContactMessage, SiteConfig
  - [x] File upload: resume PDF, project images
  - [x] Contact form endpoint with email notification (Resend)
  - [x] Admin-only endpoints to manage content
  - [x] JWT auth for admin write operations
  - [ ] `sync_types` output committed
- [ ] `examples/portfolio-frontend/` — React+Vite frontend (from `react-vite-boilerplate`)
  - [ ] Home, About, Projects, Experience, Contact pages
  - [ ] Project detail page
  - [ ] Contact form wired to API
  - [ ] Admin dashboard (hidden route, JWT-protected)
  - [ ] Dark mode (already in boilerplate via next-themes)
  - [ ] Uses generated types from `sync_types`

#### Example Apps — Ecommerce Frontend (backend exists in `ecommerce-api/`)
- [x] `examples/ecommerce-frontend/` — React+Vite frontend ✅
  - [x] Product listing + filtering + search
  - [x] Product detail page
  - [x] Cart (Zustand store with localStorage persistence)
  - [ ] Checkout flow with Stripe Elements
  - [x] Order history (authenticated placeholder)
  - [x] Auth: login/register/JWT

#### React+Vite Frontend Starter (standalone template)
- [ ] `examples/react-vite-starter/` — generic API-agnostic starter
  - [ ] Based on `~/dev/react-vite-boilerplate` (TanStack Router, React Query, Axios, shadcn, Zod, Zustand)
  - [ ] Auth slice: login/logout/refresh with JWT interceptor
  - [ ] Protected route wrapper
  - [ ] API client with base URL from `.env`
  - [ ] Sample CRUD page wired to a django-matt endpoint
  - [ ] `sync_types` integration doc in README
  - [ ] CORS setup guide in README
- [ ] `examples/react-rsbuild-starter/` — same but RSBuild bundler
  - [ ] Based on `~/dev/boilerplates/react-rsbuild-boilerplate`
  - [ ] Same features as Vite starter

#### Recipes / Cookbook — `docs/recipes/`
- [x] `auth-flows.md` — JWT login, refresh, logout, protected endpoints, magic links
- [x] `file-uploads.md` — S3/R2, validation, chunked, presigned URLs
- [x] `background-tasks.md` — native tasks vs Celery, retry patterns, scheduling
- [x] `pagination-filtering.md` — cursor, LimitOffset, search, ordering
- [x] `multi-tenancy.md` — org isolation, per-tenant queries, middleware
- [x] `webhooks.md` — inbound verification + outbound delivery
- [x] `rate-limiting.md` — per-user, per-endpoint, custom backends
- [x] `testing-patterns.md` — async tests, JWT fixtures, factories, live DB
- [x] `frontend-integration.md` — `sync_types`, React Query setup, Zod, CORS, dev proxy

### Tier 2: Should Fix Before Announce

#### Migration Guides
- [x] `docs/migrations/from-drf.md` — serializers→schemas, ViewSets→controllers, auth→JWT decorators, side-by-side
- [x] `docs/migrations/from-fastapi.md` — DI, Pydantic models, async patterns, routers
- [x] `docs/migrations/from-ninja.md` — already have codemods, need human-readable guide

#### Packaging / PyPI Polish
- [x] `pyproject.toml` — `[project.urls]` already has Homepage, Documentation, Issues, Changelog
- [x] Version: bumped to 0.10.0

#### Frontend Integration Docs
- [x] `docs/recipes/frontend-integration.md` covers this (CORS, sync_types, React Query, JWT, CORS, deploy)

#### `examples/` Root README
- [x] Rewrote with full table of all 14 examples + "Choose your starting point" guide

### Tier 3: Nice-to-Have for Launch Day

- [x] All mattstack-cli presets added: `matt-blog`, `matt-portfolio`, `matt-ecommerce`

### Boilerplate Notes (for reference during frontend work)

> react-vite-boilerplate: ~/dev/react-vite-boilerplate (GitHub: mattjaikaran/react-vite-boilerplate)
> Stack: TanStack Router, React Query, Axios, shadcn/ui, Tailwind, Zod, Zustand, Vitest

> react-rsbuild-boilerplate: ~/dev/boilerplates/react-rsbuild-boilerplate (GitHub: mattjaikaran/react-rsbuild-kibo-boilerplate)
> Stack: Same as above but RSBuild bundler (Rust-powered, faster builds)

> Existing: ~/dev/boilerplates/django-matt-starter — minimal django-matt API template (reference this for blog-api)

---

## Open Source Launch (existing items)

- [ ] `django-matt` landing page (single page, could be the docs index)

---

## Stage 17: Native Task Engine & AI Audits (Priority)

### Phase 17A: Native Task Engine ✅ (Complete)
- [x] Core Task API with Pydantic validation (`django_matt/tasks_native/`)
- [x] Auto-backend detection (Django 6.0 native → Celery fallback)
- [x] Database-driven scheduling (no celerybeat)
- [x] Retry policies with dead letter queue
- [x] **Unfold Admin Dashboard**:
  - [x] Real-time task status (WebSocket)
  - [x] Failure tracking with stack traces
  - [x] Retry/cancel controls
  - [x] Schedule management UI
  - [x] Queue metrics charts
- [x] Conditional loading (zero overhead if not enabled)
- [x] CLI commands (list, run, status, purge, retry)

### Phase 17B: AI-Assisted Codebase Audits ✅ (shipped in 0.10.0)
- [x] Multi-perspective audit framework (security, performance, scalability, bundle_size)
- [x] Strictness levels (RELAXED, STANDARD, STRICT, PARANOID)
- [x] Bundle size analyzer with tree-shaking suggestions
- [x] LLM prompt helpers with project context
- [x] `matt_audit` CLI with JSON/Markdown/SARIF output
- [x] Auto-fix suggestions and diff mode
- [x] MCP tools for AI agents
- [x] GitHub Actions integration

## Future Technical Work

### Database
- [ ] PlanetScale support (Stage 9B.6) — connection config, branch-based workflows, serverless MySQL migrations

### Infrastructure
- [ ] Kubernetes/Helm chart generation (Stage 9C.3) — Helm chart, K3s cluster support, Ingress config

### AI/ML Providers
- [ ] vLLM integration (Stage 10C.2) — vLLM server client, OpenAI-compatible API
- [ ] llama.cpp integration (Stage 10C.3) — direct llama-cpp-python bindings
- [ ] LocalAI integration (Stage 10C.4) — LocalAI client wrapper

### Migration (2026-08-15)
- [x] `matt_migrate_from --source ninja-extra` — ninja-extra as first-class migration source
  - [x] Detection: `ninja_extra` beats the `ninja` substring match in both the wizard and codemod engine
  - [x] Analyzer (`django_matt/migrate/ninja_extra.py`): ControllerBase classes, api_controller decorators, route.* endpoints, NinjaExtraAPI, register_controllers, Inject DI
  - [x] Codemods (`django_matt/codemods/ninja_extra.py`): imports, controller conversion, registration
  - [x] `--generate` emits APIController templates + MIGRATION_GUIDE.md
  - [x] 13 new tests (codemod + wizard)
- [ ] Live side-by-side DRF/ninja parity matrix (feature comparison, not just published-baseline benchmarks)

---

## Completed Archive

> Collapsed summaries. Full history in git log.

### Launch Readiness (all done)
- Distribution & publishing: PyPI, TestPyPI, OIDC, Rust wheels
- Documentation site: MkDocs Material, GitHub Pages, version switcher

---

## Stage 18: Performance — Beat FastAPI (v0.11.0)

**Goal**: django-matt faster than FastAPI+Starlette for 90th percentile use case.

### Phase 18A: Rust Router as Default ✅ (committed on main)
- [x] Enable Rust request router as default for `@api.get()` / `@api.post()` decorators
- [x] Profile route matching: Python vs Rust (target: 2.3x speedup)
- [x] Graceful fallback to Python router when Rust wheel unavailable
- [x] Update `pyproject.toml` to include Rust wheel as default dependency

### Phase 18B: Rust Schema Validation (opt-in, Pydantic stays) ✅ (committed on main)
- [x] Create `django_matt.core.schema.RustModelSchema` as Pydantic alternative
- [x] Batch validation at Rust layer using `serde` / `jsonschema-rs`
- [x] Keep Pydantic as first-class option: `from django_matt.core.schema import ModelSchema` still works
- [x] Design: `RustModelSchema` mirrors Pydantic API (`.model_validate()`, `.model_dump()`) for drop-in swap
- [ ] Benchmarks: Rust vs Pydantic validation latency (target: 3-5x faster for large payloads)

### Phase 18C: Benchmark Suite vs FastAPI ✅ (committed on main)
- [x] Create `benchmarks/bench_vs_fastapi.py` — identical payloads, both frameworks
- [x] Measure: route resolution, JSON serialization, schema validation, end-to-end
- [x] Auto-generate comparison charts (p50/p95/p99 latency, throughput)
- [ ] Target: 15,000 req/s single Granian worker (FastAPI ~12,000 on M2 Pro) — re-run on release hardware

### Phase 18D: Connection Pool Pre-Warming
- [ ] On startup, open N database connections and hold (active pooling)
- [ ] `django_matt.db.prewarm_connections(n=10)` called in AppConfig.ready()
- [ ] Configurable via `MATT_DB_POOL_WARMUP` setting
- [ ] Eliminates first-request latency spike (40-200ms savings)

### Phase 18E: Streaming Response Pool
- [ ] Pre-allocate response byte buffers at Rust layer
- [ ] Zero-copy `BytesStream` for large payloads
- [ ] Integrate with SSE streaming for token-by-token AI responses

### Phase 18F: matt doctor --ai
- [ ] Run gauntlet → feed failures + context to LLM → get fix diffs
- [ ] Uses existing fixer engine; falls back to LLM when rule-based fixer can't handle
- [ ] `matt doctor --ai --apply` for auto-fix workflow
- [ ] Integrates with `audits/prompts/` for structured LLM queries

---

## Stage 19: LLM/AI Deep Integration (v0.12.0)

### Phase 19A: AI-Native Context Generation ✅ (committed on main)
- [x] `matt ai context` auto-detects project patterns and emits rules
- [x] Scans git history for bug fixes → emits anti-pattern rules
- [x] Generates service-layer, soft-delete, error-handling conventions
- [x] Output: `.cursorrules` + `CLAUDE.md` tailored to this specific project

### Phase 19B: matt explain --ai ✅ (committed on main)
- [x] `matt explain --ai /api/orders/` traces full request lifecycle
- [x] Natural language output: middleware chain, controller, service, DB query, response
- [x] Dependencies shown: "Uses StripeProvider → requires STRIPE_API_KEY"

### Phase 19C: AI-Assisted Schema Design ✅ (committed on main)
- [x] Wire `schema_designer/` to LLM for conversational schema creation
- [x] "I need a User model with email auth" → Model + Schema + Controller + Service + Tests
- [x] Generates migrations, admin config, and OpenAPI docs

### Phase 19D: AI-Assisted Refactoring ✅ (committed on main)
- [x] `matt refactor --ai <file>` suggests architectural improvements
- [x] Detects fat controllers, missing service layer, mixed concerns
- [x] Generates split suggestions with before/after diffs

### Phase 19E: Agent SDKs
- [ ] Rust SDK: `matt_sdk::Client` for maximum performance
- [ ] Zig SDK: for embedded/WASM use cases
- [ ] Update existing TypeScript/Swift/Python SDKs

---

## Stage 20: Agent Guardrails (v0.12.0)

### Phase 20A: Architecture Contracts as Code ✅ (committed on main)
- [x] Declarative `.matt/architecture.toml` format
- [x] Layer dependency rules: foundation → domain → interface → tooling
- [x] Runtime enforcement via `check_architecture.py` extension
- [x] Violations block CI/deploy

### Phase 20B: Pre-Commit AI Audit ✅ (committed on main)
- [x] Hook `matt audit` into pre-commit flow
- [x] Block commits introducing CRITICAL/HIGH findings
- [x] Auto-generate fix diffs for review

### Phase 20C: Test Generation from Schemas
- [ ] Given Pydantic schema, auto-generate edge-case tests
- [ ] Empty strings, boundary values, type mismatches, missing required fields
- [ ] Integration with `testing/smart/` module

### Phase 20D: Convention Check
- [ ] `matt convention-check` compares project against django-matt best practices
- [ ] Detects: inconsistent error handling, mixed controller patterns, missing service layer
- [ ] Scoring: 0-100 with per-category breakdown

---

## Stage 21: Beyond FastAPI Performance (v0.13.0)

### Phase 21A: Zero-Copy Request Parsing
- [ ] Use Rust `serde_json` with borrowed strings for POST bodies
- [ ] Request body stays in memory as bytes, parsed struct references it directly
- [ ] Target: 2-3x faster JSON parsing for payloads > 1KB

### Phase 21B: SIMD JSON Validation
- [ ] Integrate `simd-json` crate for large payload validation
- [ ] Auto-select SIMD path for payloads > 1KB, fallback to serde for small

### Phase 21C: HTTP/3 (QUIC) Support
- [ ] Granian HTTP/3 backend (QUIC protocol)
- [ ] Eliminates TCP head-of-line blocking
- [ ] Measurable improvement for high-latency clients (mobile, global)

### Phase 21D: Rust-Layer Response Caching
- [ ] Cache serialized JSON at Rust router level
- [ ] Cache hit → skip Python entirely, return bytes directly
- [ ] Integrate with existing `CacheInvalidationMixin` signals
- [ ] Target: <100μs cache hit latency

### Phase 21E: Shared-Nothing Worker Architecture
- [ ] Profile GIL contention under high load
- [ ] Multi-process model with shared-nothing workers if GIL is bottleneck
- [ ] Each worker: own DB pool, cache, Rust router

---

## Stage 22: ML/AI Pipeline (v0.14.0)

### Phase 22A: ModelDeployment Framework
- [ ] `django_matt.ml.ModelDeployment` wraps vLLM/llama.cpp/LocalAI
- [ ] First-class Django resource: `classifier = ModelDeployment(model="llama-3.1-8b")`
- [ ] `classifier.predict(text)` → async, with concurrency limits
- [ ] Health checks, auto-restart, GPU memory monitoring

### Phase 22B: Embedding Cache with pgvector
- [ ] `CachedEmbedding` model stores computed embeddings
- [ ] <1ms latency for cached embeddings
- [ ] Auto-invalidation on source data changes

### Phase 22C: Streaming Token Optimization
- [ ] Rust-backed SSE frame encoder for token-by-token streaming
- [ ] Model → Python → Rust encoder → client with sub-ms overhead
- [ ] Backpressure handling for slow clients

### Phase 22D: Batch Inference Queue
- [ ] Accumulate requests over 50ms window
- [ ] Send batch to vLLM/llama.cpp for parallel processing
- [ ] Configurable window size and max batch size

---

## Stage 23: CLI & DevX (v0.14.0)

### Phase 23A: matt new Wizard
- [ ] Interactive TUI for scaffolding: pick stack, features, auth, billing, AI
- [ ] `matt new` → selects API-only/fullstack/B2B → auth/JWT/OAuth → billing/Stripe → AI/vLLM
- [ ] Generates fully wired project in one command

### Phase 23B: matt doctor --fix
- [ ] Auto-fix common issues: missing `__init__.py`, wrong imports, outdated configs
- [ ] `matt doctor --fix --dry-run` to preview

### Phase 23C: matt benchmark
- [ ] Built-in load testing: `matt benchmark --endpoint /api/users --concurrency 100`
- [ ] Shows p50/p95/p99 latency, throughput, error rate
- [ ] Compares against baseline from previous run

### Phase 23D: matt deploy --preview
- [ ] Cost estimate, region selection, resource sizing before deploying
- [ ] Integrates with Fly.io, Railway, Render, AWS providers

### Phase 23E: mattstack-cli Version Sync
- [ ] Mattstack-cli pins django-matt version in scaffolded projects
- [ ] Auto-updates templates on django-matt release
- [ ] `mattstack sync` command to update existing projects

---

## Stage 24: Horizontal & Vertical Scalability (v0.15.0)

### Phase 24A: Read Replica Routing
- [ ] `django_matt.db.Router` auto-routes reads → replicas, writes → primary
- [ ] Inspects query type (SELECT vs INSERT/UPDATE/DELETE)
- [ ] Configurable via `DATABASE_ROUTERS` with zero code changes

### Phase 24B: Redis Cluster Native Support
- [ ] `RedisClusterCache` backend for caching + sessions
- [ ] Auto-sharding across cluster nodes
- [ ] Failover handling with retry logic

### Phase 24C: Database Sharding Hints
- [ ] `django_matt.db.shard_key(User, "organization_id")` annotation
- [ ] Auto-adds `WHERE organization_id = ?` to all queries
- [ ] Enables horizontal sharding without application changes

### Phase 24D: Async Task Result Streaming
- [ ] WebSocket streaming of partial task results
- [ ] Progress bars, intermediate CSV rows, log lines
- [ ] Client subscribes: `ws://api/tasks/{task_id}/stream`

---

## Design Decisions

- **Schema validation**: Rust `RustModelSchema` becomes default for performance. Pydantic `ModelSchema` remains first-class option. Both expose identical API (`model_validate`, `model_dump`, `model_json_schema`). Users choose via import path.
- **Rust extensions**: Always optional. Graceful fallback to pure Python when Rust wheel unavailable (e.g., PyPy, exotic architectures).
- **Agent guardrails**: Architecture contracts are declarative (TOML) and enforced at CI/deploy time, not at import time (zero runtime overhead).
- **Performance targets**: Benchmarked against FastAPI on identical hardware with identical payloads. All claims backed by reproducible benchmarks in `benchmarks/`.


---

## Stage 25: Agent-Native Design Patterns (v0.15.0)

Inspired by Matt Pocock's Skills and Superpowers methodology.

### Phase 25A: Shared Language / CONTEXT.md
- [ ] Auto-generate `CONTEXT.md` from project models, routes, and conventions
- [ ] Project-specific glossary: "materialization cascade" not "lesson file system update"
- [ ] Agents use glossary to reduce verbosity and navigate codebase faster
- [ ] `matt context generate --format glossary` command
- [ ] Integrates with existing `generate_ai_context` management command

### Phase 25B: Architecture Decision Records (ADR)
- [ ] `matt adr "Use Redis for session storage"` generates structured ADR
- [ ] Template: Title, Status, Context, Decision, Consequences
- [ ] Stored in `docs/adr/` with sequential numbering
- [ ] Linked to code via `@adr("0001-redis-sessions")` decorator references

### Phase 25C: matt build --plan (Subagent-Driven Development)
- [ ] `matt build --plan plan.md` dispatches `tasks_native` workers per plan item
- [ ] Inspired by Superpowers SDD: spec → plan → parallel subagents → review
- [ ] Each subagent gets scoped workspace, explicit acceptance criteria
- [ ] Review gate between plan items: agent B can't start until agent A's output passes
- [ ] Zero handoff — agents communicate via IRC-style message bus

### Phase 25D: Codebase Design Check
- [ ] `matt design-check` validates Ousterhout's "deep module" principle
- [ ] Measures module interface complexity vs implementation depth
- [ ] Detects shallow modules (many public methods, little implementation)
- [ ] Cohesion/coupling scores per module
- [ ] Suggests module splits or merges

### Phase 25E: TDD Watch Mode
- [ ] `matt test --tdd` runs tests in watch mode with coverage gap display
- [ ] Red-green-refactor loop enforced: fail → pass → refactor
- [ ] Auto-generates test stubs for uncovered code paths
- [ ] Integrates with existing `testing/smart/` module

### Phase 25F: Agent Alignment (Grilling)
- [ ] `matt new` / `matt generate` incorporate grilling questions
- [ ] "What problem does this endpoint solve? Who calls it? Expected load?"
- [ ] Answers become docstrings, ADRs, and context for future agents
- [ ] Stored in `.matt/decisions/` for persistent agent memory

### Phase 25G: Autonomous Execution Loop
- [ ] `matt execute --goal "Add user auth with JWT and OAuth"` runs autonomously
- [ ] Spec → plan → execute → review → commit cycle without human intervention
- [ ] Built on `tasks_native/` for scheduling and `audits/` for review gates
- [ ] Progress dashboard via WebSocket (existing Unfold admin)
- [ ] Inspired by Superpowers: agents run for hours without deviating from plan

---

## Future Technical Work (existing)

- [ ] PlanetScale support — connection config, branch-based workflows
- [ ] Kubernetes/Helm chart generation
- [ ] vLLM/llama.cpp/LocalAI deeper integration
- Example apps: 8 examples refreshed + 2 new (ai-chat, multitenant-saas)
- Polish: ruff clean, 6342 tests passing, pyright 0 errors
- Community prep: LICENSE, CONTRIBUTING, issue/PR templates, repo settings, SECURITY.md

### Feature Enhancements (all done)
- Performance CI: benchmark job, regression gate (>5%), memory profiling, benchmark charts
- Starter templates: api-only, ai-saas, marketplace, internal-tools + registry
- Code review agent: 11 AST analyzers, 4 reporters, LLM review, 154 tests
- AI/LLM context: introspection endpoint, MCP server gen, IDE watcher, LLM error messages
- Server backends: Robyn, Granian, auto-detect, benchmark suite, Dockerfile templates
- Migration codemods: DRF, Ninja, FastAPI with dry-run and reports
- Client SDKs: TypeScript, Swift, Python generators with schema-hash versioning + CI publish
- Plugin ecosystem: scaffold, discovery, 3 example plugins, compatibility matrix
- Rust extensions: CI wheels, RSA/EC JWT (7.2.2), query parser middleware (7.4.3)
- Renderers: Vue, Svelte, Astro, Remix

### DX Enhancements (all done)
- Zero-config defaults: rate limiting presets, cache_clear, shell+, dbshell+, login-by-email, matt check --strict
- Vite integration: manifest, HMR, template tags, middleware, fingerprinting
- Inertia.js adapter: middleware, SSR, shared data, testing helpers (89 tests)
- Unpoly integration: middleware, decorators, response, template tags (57 tests)
- Predicate permissions: composable AND/OR/NOT, 6 builtins, auth backend (88 tests)
- Hybrid properties: @hybrid_property with SQL expressions (36 tests)
- Model refactoring: move-model, rename-model, split-app, merge-apps
- Strict templates: StrictEngine, UndefinedVariableError, allowlist
- CLI scaffolding: generate model/controller/service/schema/test/middleware/migration/factory
- File storage: chunked/tus uploads, presigned URLs, image processing, B2 backend, events, metadata
- DEP-0014 workers: DjangoWorkersBackend with auto-detection and fallback
- Dev server: matt dev, error overlay, inspector panel, auto-migrate, port detection
- Forms: bridge to components, Zod/Yup validation, @ajax_form, builder API
- Data export/import: CSV/JSON/JSONL with filters, fixtures, seed

### Enhancement Plan Phases 1–7 (all done)
- Error handling, schema/OpenAPI, controller/view, DX/compat, testing, architecture, Rust extensions

### Session History
- Session 1: 13 new modules (555 tests)
- Session 2: slim mode, benchmarks, Python 3.14, test coverage expansion
- Session 3: release tooling, bug fixes, 6141 tests
- Session 4: documentation blitz — 17 module docs, 6 tutorials, 7 cookbooks, 6 concept guides, migration docs

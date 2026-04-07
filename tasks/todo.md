# Django Matt — Active Tasks

## Up Next — Launch Readiness

### Distribution & Publishing
- [x] PyPI package distribution — `uv build`, twine check pass
- [ ] Trusted publisher setup on PyPI
- [ ] CI wheel building for Rust extensions (GitHub Actions, manylinux/macOS/Windows)
- [ ] Publish to TestPyPI for validation before real publish
- [ ] `django-matt[rust]` optional extra with pre-built wheels

### Documentation Site
- [x] MkDocs Material site builds successfully (`uv run mkdocs build`)
- [ ] Deploy docs site (GitHub Pages or Vercel)
- [ ] Fix broken links (27 warnings in strict mode — forward refs to planned pages)
- [ ] Add version switcher for future releases

### Example App Refresh
- [x] Update example apps with new modules (interceptors, events, streaming)
  - devplatform: SSE streaming analytics, interceptors+exception filters on gateway
  - ecommerce-v2: event bus on orders, domain event handlers
  - saas-starter: interceptors on projects, events on CRUD, SSE notifications
- [ ] Add new example: AI chat app with SSE streaming + CQRS
- [ ] Add new example: multi-tenant SaaS with events + feature flags
- [ ] Ensure all examples run with `uv run python manage.py runserver`

### Polish
- [x] Ruff lint pass — all source clean (0 errors)
- [x] Fix: AnalyticsDatabaseBackend.group() used non-existent field, now uses metadata
- [x] Fix: test_create_and_str assertion matched truncated session_id
- [x] Fix: test_get_session_metrics_with_data date range didn't include auto_now_add sessions
- [ ] Full test suite confirmation (running)
- [ ] Type check pass (pyright) on new modules
- [ ] Review all LLM migration prompts for accuracy

### Community Prep
- [x] LICENSE file (Apache 2.0)
- [x] CONTRIBUTING.md — contribution guidelines, PR process, code style
- [x] Issue templates (bug report, feature request)
- [x] PR template
- [ ] GitHub repo settings (topics, description, social preview)

---

## Future Enhancements

### Renderers & Frontend
- [ ] Vue renderer (Stage 12D.4)
- [ ] Svelte renderer (Stage 12D.5)
- [ ] Astro framework support
- [ ] Remix framework support

### Database
- [ ] PlanetScale support (Stage 9B.6)

### Infrastructure
- [ ] Kubernetes/Helm chart generation (Stage 9C.3)

### AI/ML
- [ ] vLLM integration (Stage 10C.2)
- [ ] llama.cpp integration (Stage 10C.3)
- [ ] LocalAI integration (Stage 10C.4)

### Rust Extensions (Deferred)
- [ ] CI wheel building — GitHub Actions manylinux/macOS/Windows (7.0.4)
- [ ] RSA/EC JWT signing in Rust (7.2.2 — deferred, `cryptography` pkg already Rust-based)
- [ ] Wire Rust query string parser into filtering/ordering/pagination middleware (7.4.3)

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

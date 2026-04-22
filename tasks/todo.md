# Django Matt — Active Tasks

## Open Source Launch

- [ ] Launch blog post / announcement — what it is, why it exists, what's different (for dev.to, Reddit, HN)
- [ ] Social preview image for GitHub repo
- [ ] Short demo video — `startapi` → running API with auth, CRUD, admin in 2 minutes
- [ ] Discord or GitHub Discussions for community
- [ ] `django-matt` landing page (single page, could be the docs index)
- [ ] PyPI classifiers and metadata polish

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

### Phase 17B: AI-Assisted Codebase Audits
- [ ] Multi-perspective audit framework (security, performance, scalability, bundle_size)
- [ ] Strictness levels (RELAXED, STANDARD, STRICT, PARANOID)
- [ ] Bundle size analyzer with tree-shaking suggestions
- [ ] LLM prompt helpers with project context
- [ ] `matt_audit` CLI with JSON/Markdown/SARIF output
- [ ] Auto-fix suggestions and diff mode
- [ ] MCP tools for AI agents
- [ ] GitHub Actions integration

## Future Technical Work

### Database
- [ ] PlanetScale support (Stage 9B.6) — connection config, branch-based workflows, serverless MySQL migrations

### Infrastructure
- [ ] Kubernetes/Helm chart generation (Stage 9C.3) — Helm chart, K3s cluster support, Ingress config

### AI/ML Providers
- [ ] vLLM integration (Stage 10C.2) — vLLM server client, OpenAI-compatible API
- [ ] llama.cpp integration (Stage 10C.3) — direct llama-cpp-python bindings
- [ ] LocalAI integration (Stage 10C.4) — LocalAI client wrapper

---

## Completed Archive

> Collapsed summaries. Full history in git log.

### Launch Readiness (all done)
- Distribution & publishing: PyPI, TestPyPI, OIDC, Rust wheels
- Documentation site: MkDocs Material, GitHub Pages, version switcher
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

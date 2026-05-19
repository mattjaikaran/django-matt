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
  - [ ] `sync_types` output committed to repo (run after confirming API boots)
- [ ] `examples/blog-frontend/` — React+Vite frontend (from `react-vite-boilerplate`)
  - [ ] Post listing page with filters
  - [ ] Single post page with comments
  - [ ] Author dashboard (create/edit/delete own posts)
  - [ ] Tag/category browse pages
  - [ ] Search UI
  - [ ] Auth: login/logout, JWT refresh
  - [ ] Uses generated types from `sync_types`
  - [ ] `.env.example` pointing at blog-api

#### Example Apps — Portfolio
- [ ] `examples/portfolio-api/` — Django-matt backend
  - [ ] Models: Project, Skill, WorkExperience, ContactSubmission, SiteConfig
  - [ ] File upload: resume PDF, project images
  - [ ] Contact form endpoint with email notification
  - [ ] Visitor analytics (basic page view counts)
  - [ ] Admin-only endpoints to manage content
  - [ ] JWT auth for admin write operations
  - [ ] `sync_types` output committed
- [ ] `examples/portfolio-frontend/` — React+Vite frontend (from `react-vite-boilerplate`)
  - [ ] Home, About, Projects, Experience, Contact pages
  - [ ] Project detail page
  - [ ] Contact form wired to API
  - [ ] Admin dashboard (hidden route, JWT-protected)
  - [ ] Dark mode (already in boilerplate via next-themes)
  - [ ] Uses generated types from `sync_types`

#### Example Apps — Ecommerce Frontend (backend exists in `ecommerce-api/`)
- [ ] `examples/ecommerce-frontend/` — React+Vite or React+RSBuild frontend
  - [ ] Product listing + filtering + search
  - [ ] Product detail page
  - [ ] Cart (Zustand store)
  - [ ] Checkout flow with Stripe Elements
  - [ ] Order history (authenticated)
  - [ ] Auth: login/register/JWT
  - [ ] Uses generated types from `sync_types`

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
- [ ] `auth-flows.md` — JWT login, refresh, logout, protected endpoints, magic links
- [ ] `file-uploads.md` — S3/R2, validation, chunked, presigned URLs
- [ ] `background-tasks.md` — native tasks vs Celery, retry patterns, scheduling
- [ ] `pagination-filtering.md` — cursor, LimitOffset, search, ordering
- [ ] `multi-tenancy.md` — org isolation, per-tenant queries, middleware
- [ ] `webhooks.md` — inbound verification + outbound delivery
- [ ] `rate-limiting.md` — per-user, per-endpoint, custom backends
- [ ] `testing-patterns.md` — async tests, JWT fixtures, factories, live DB
- [ ] `frontend-integration.md` — `sync_types`, React Query setup, Zod, CORS, dev proxy

### Tier 2: Should Fix Before Announce

#### Migration Guides
- [ ] `docs/migrations/from-drf.md` — serializers→schemas, ViewSets→controllers, auth→JWT decorators, side-by-side
- [ ] `docs/migrations/from-fastapi.md` — DI, Pydantic models, async patterns, routers
- [ ] `docs/migrations/from-ninja.md` — already have codemods, need human-readable guide

#### Packaging / PyPI Polish
- [ ] `pyproject.toml` — add `[project.urls]`: Homepage, Documentation, Repository, Changelog
- [ ] Confirm PyPI page renders correctly (long_description, classifiers, links)
- [ ] Version decision: stay `0.9.0 Beta` or bump to `1.0.0 Stable`

#### Frontend Integration Docs
- [ ] `docs/frontend-integration.md` — single comprehensive guide
  - [ ] Dev setup: CORS config, Vite proxy to django-matt backend
  - [ ] `sync_types` walkthrough (generate → use in React)
  - [ ] React Query + generated hooks example
  - [ ] Auth flow: JWT storage, Axios interceptor, refresh
  - [ ] Production: separate domains vs monorepo deploy

#### `examples/` Root README
- [ ] Table of all examples: name, stack, what it demonstrates, link
- [ ] "Choose your stack" guide (API-only vs fullstack, Vite vs RSBuild)

### Tier 3: Nice-to-Have for Launch Day

- [ ] `matt startproject --template blog` — make blog template available via CLI
- [ ] `matt startproject --template portfolio` — portfolio template via CLI
- [ ] `docs/why.md` — "DRF + Ninja + simplejwt + dj-stripe + channels = django-matt" scannable comparison
- [ ] `Deploy to Fly.io` badge on README pointing at blog-api or ecommerce-api
- [ ] Short demo video — `startapi` → running API with auth, CRUD, admin in 2 minutes
- [ ] Social preview image for GitHub repo
- [ ] Launch blog post / announcement (dev.to, Reddit r/django, HN, ProductHunt)
- [ ] Discord or GitHub Discussions for community

### mattstack-cli Integration (after examples are complete)

> Repo: https://github.com/mattjaikaran/mattstack-cli | Local: ~/dev/mattstack-cli
> All new example apps should eventually be scaffoldable via `mattstack init`

- [ ] Add `blog` preset to mattstack-cli (`django-matt` backend + `react-vite` frontend)
- [ ] Add `portfolio` preset to mattstack-cli
- [ ] Add `ecommerce` preset to mattstack-cli (wire to `ecommerce-api` + new frontend)
- [ ] Confirm `django-matt` backend option in `mattstack init` interactive flow
- [ ] Update mattstack-cli README with new presets
- [ ] Sync boilerplates in `~/dev/boilerplates/` with any changes made during example app work

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

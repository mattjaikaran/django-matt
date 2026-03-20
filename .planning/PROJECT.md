# django-matt

## What This Is

A Django meta-framework that replaces Django REST Framework, django-ninja, and django-ninja-extra with a single cohesive library. Built on Django as the sole dependency — no external packages beyond Django itself (plus orjson for performance). Async-first, type-driven, with 126 shipped requirements across auth, billing, real-time, AI/ML, and more.

## Core Value

The fastest, most developer-friendly way to build Django APIs — if you can't ship faster with django-matt than with DRF or django-ninja, it hasn't shipped yet.

## Requirements

### Validated

- ✓ Full codebase audit — security, performance, DX, correctness — v1.0
- ✓ Async-first: zero sync ORM in async handlers — v1.0
- ✓ Performance benchmarks (django-matt vs DRF vs django-ninja vs FastAPI) — v1.0
- ✓ Zero external dependencies beyond Django + orjson — v1.0
- ✓ CLI-guided migration from django-ninja projects — v1.0
- ✓ AI-native: context generation for LLMs (`generate_ai_context`) — v1.0
- ✓ 126 requirements shipped (CORE, AUTH, DX, PERF, TENANT, BILL, FLAG, ANLYT, EXP, RT, MSG, NOTIF, EMAIL, AI, ML, FILE, TASK, AUDIT, HTMX, COMP, GQL, ADMIN, DEPLOY, OBS) — v1.0

### Active

- [ ] matt-stack 2.0 integration — CLI scaffolds django-matt backends + React frontends
- [ ] BillingController auth guards — framework-level controller needs APIController base or explicit auth
- [ ] startapi middleware auto-wiring — TenantMiddlewareAsync and ObservabilityMiddleware in generated templates
- [ ] Experiments → Analytics bridge — ExperimentManager.get_assignment() should emit analytics events
- [ ] Pydantic v2 migration — passkeys/schemas.py uses deprecated `class Config`

### Out of Scope

- React meta-framework / JS frontend framework — matt-stack v3, not now
- Mobile SDKs — web-first
- GraphQL-first approach — REST-first, GraphQL as optional module
- Supporting Python < 3.12 — modern Python only

## Context

**Origins:** Evolution of [matt-stack](https://github.com/mattjaikaran/matt-stack), [django-ninja-boilerplate](https://github.com/mattjaikaran/django-ninja-boilerplate), and [react-vite-boilerplate](https://github.com/mattjaikaran/react-vite-boilerplate). V1 was a CLI that wired up django-ninja + React with opinionated conventions. django-matt is the framework those conventions deserve.

**Current state (v1.0 shipped):** 193K LOC library, 62K LOC tests, 35K LOC examples. 4770 tests passing (46 skipped). 126 v1 requirements satisfied across 7 phases, 24 plans. 5 working example apps (quicktodo, ecommerce-v2, devplatform, saas-starter, ecommerce-api) plus 2 legacy examples.

**Tech stack:** Python 3.12+ / Django 5.2+ / Pydantic v2 / orjson / async-first

**Dependency philosophy:** Django is the only hard dependency. Build own implementations of everything else. No waiting on third-party patches or abandoned packages. orjson is a base dependency for JSON performance.

**Performance approach:** orjson everywhere, async-first, cached introspection at init time (not per-request), `model_construct()` for list serialization, singleton patterns for hot paths, API-mode middleware stripping.

## Constraints

- **Dependency**: Django + orjson only — no other external packages in core
- **Python**: 3.12+ only — leverage modern features
- **Django**: 5.2+ — no legacy compatibility
- **Performance**: Must match or beat FastAPI on equivalent benchmarks
- **Async**: Async-first design — sync fallbacks use `sync_to_async()`
- **DX bar**: Must be simpler than DRF, as clean as django-ninja, more powerful than both

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Django-only dependency | Control upgrade cycle, no third-party blockers | ✓ Good — zero dep issues in v1.0 |
| orjson as base dep | 3-10x faster JSON, worth the single exception | ✓ Good — used everywhere |
| Async-first | Modern Django supports ASGI, match FastAPI model | ✓ Good — Phase 1 eliminated all sync violations |
| Convention bridge over drop-in compat | Improve on ninja patterns, not just copy them | ✓ Good — migration CLI with TODO markers |
| Internal-first, OSS later | Get DX right without community pressure | ✓ Good — 5 example apps validate DX |
| Pydantic v2 for schemas | Best-in-class validation + serialization | ✓ Good — `model_construct()` for perf |
| CONN_MAX_AGE=0 for ASGI | Persistent connections leak under ASGI (Django #33497) | ✓ Good — enforced in all deploy configs |
| Cache-based JWT blacklist | Production-secure out of box, no migration needed | ✓ Good — per-user bulk revocation works |
| Router body injection | Framework parses JSON once, injects typed `body` param | ✓ Good — all examples aligned |

---
*Last updated: 2026-03-20 after v1.0 milestone*

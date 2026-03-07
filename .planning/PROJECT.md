# django-matt

## What This Is

A Django meta-framework that replaces Django REST Framework, django-ninja, and django-ninja-extra with a single cohesive library. Built on Django as the sole dependency — no external packages beyond Django itself (plus orjson for performance). Designed for internal team use first, open source when the DX makes people freak out.

## Core Value

The fastest, most developer-friendly way to build Django APIs — if you can't ship faster with django-matt than with DRF or django-ninja, it hasn't shipped yet.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

- [ ] Full codebase audit — security, performance, DX, correctness
- [ ] Fix all issues found during audit
- [ ] Establish performance benchmarks (baseline vs DRF vs django-ninja vs FastAPI)
- [ ] Zero external dependencies beyond Django + orjson
- [ ] Peak async-first performance (FastAPI-level or faster)
- [ ] Convention bridge from django-ninja (similar patterns, intentionally different where django-matt improves)
- [ ] CLI-guided migration from django-ninja projects
- [ ] AI-native: context generation for LLMs to understand codebase
- [ ] AI-native: code generation — LLMs produce correct django-matt code from examples
- [ ] AI-native: agent tooling — AI agents interact with django-matt APIs
- [ ] Agentic coding DX — works beautifully with AI coding tools
- [ ] Advanced manual DX — power users have full control when needed
- [ ] matt-stack 2.0 integration — CLI scaffolds django-matt backends + React frontends

### Out of Scope

- React meta-framework / JS frontend framework — matt-stack v3, not now
- Mobile SDKs — web-first
- GraphQL-first approach — REST-first, GraphQL as optional module
- Supporting Python < 3.12 — modern Python only

## Context

**Origins:** Evolution of [matt-stack](https://github.com/mattjaikaran/matt-stack), [django-ninja-boilerplate](https://github.com/mattjaikaran/django-ninja-boilerplate), and [react-vite-boilerplate](https://github.com/mattjaikaran/react-vite-boilerplate). V1 was a CLI that wired up django-ninja + React with opinionated conventions. django-matt is the framework those conventions deserve.

**Current state:** Substantial codebase exists with 4143 tests, 32 skipped. Covers auth (JWT, magic links, RBAC, OAuth, SSO, passkeys, API keys), CRUD views, permissions, OpenAPI gen, multitenancy, billing, websockets, feature flags, analytics, experiments, GraphQL, notifications, email, AI/ML, file uploads, background tasks, audit logging, HTMX, CLI, deployment, observability, and more.

**Dependency philosophy:** Django is the only hard dependency. Build own implementations of everything else. No waiting on third-party patches or abandoned packages. orjson is a base dependency for JSON performance.

**Inspiration:** django-ninja's clean API, django-ninja-extra's controller pattern, FastAPI's speed and type-driven design. Take what's good, fix what's broken, own it all.

**Performance approach:** orjson everywhere, async-first, cached introspection at init time (not per-request), `model_construct()` for list serialization, singleton patterns for hot paths.

**AI compatibility vision:** Framework should be self-documenting enough that LLMs can generate correct code from examples, agents can interact with APIs, and CLI can export full project context for AI consumption. Agentic coding is a first-class use case.

## Constraints

- **Dependency**: Django + orjson only — no other external packages in core
- **Python**: 3.12+ only — leverage modern features
- **Django**: 5.2+ — no legacy compatibility
- **Performance**: Must match or beat FastAPI on equivalent benchmarks
- **Async**: Async-first design — sync fallbacks use `sync_to_async()`
- **DX bar**: Must be simpler than DRF, as clean as django-ninja, more powerful than both
- **Portability**: django-ninja projects should be portable with CLI migration + TODO markers

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Django-only dependency | Control upgrade cycle, no third-party blockers | — Pending |
| orjson as base dep | 3-10x faster JSON, worth the single exception | — Pending |
| Async-first | Modern Django supports ASGI, match FastAPI model | — Pending |
| Convention bridge over drop-in compat | Improve on ninja patterns, not just copy them | — Pending |
| Internal-first, OSS later | Get DX right without community pressure | — Pending |
| Pydantic v2 for schemas | Best-in-class validation + serialization | — Pending |

---
*Last updated: 2026-03-07 after initialization*

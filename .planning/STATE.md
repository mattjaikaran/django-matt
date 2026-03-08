---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: Completed 04-02-PLAN.md
last_updated: "2026-03-08T03:24:43.445Z"
last_activity: 2026-03-07 — Roadmap created; 101 requirements mapped to 7 phases
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 13
  completed_plans: 11
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-07)

**Core value:** The fastest, most developer-friendly way to build Django APIs — if you can't ship faster with django-matt than with DRF or django-ninja, it hasn't shipped yet.
**Current focus:** Phase 1 — Correctness Audit

## Current Position

Phase: 1 of 7 (Correctness Audit)
Plan: 0 of 3 in current phase
Status: Ready to plan
Last activity: 2026-03-07 — Roadmap created; 101 requirements mapped to 7 phases

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*
| Phase 01-correctness-audit P02 | 6 | 2 tasks | 5 files |
| Phase 01-correctness-audit P01 | 9 | 2 tasks | 13 files |
| Phase 01-correctness-audit P03 | 8 | 2 tasks | 2 files |
| Phase 02-performance-baseline P02 | 2 | 2 tasks | 3 files |
| Phase 02-performance-baseline P01 | 5 | 2 tasks | 8 files |
| Phase 02-performance-baseline P03 | 15 | 2 tasks | 6 files |
| Phase 03-cli-and-type-generation P03 | 2 | 2 tasks | 1 files |
| Phase 03-cli-and-type-generation P02 | 436 | 2 tasks | 6 files |
| Phase 03-cli-and-type-generation P01 | 15 | 2 tasks | 4 files |
| Phase 03-cli-and-type-generation P04 | 25 | 2 tasks | 22 files |
| Phase 04-auth-hardening-and-multi-tenancy P02 | 45 | 2 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Brownfield audit-first approach — correctness before performance before features
- [Roadmap]: Phase 1 prerequisite for all others; Phases 3, 4, 7 unblock after Phase 1; Phases 5, 6 require Phase 4
- [Roadmap]: DJANGO_ALLOW_ASYNC_UNSAFE=true removal is Phase 1's primary gate condition
- [Roadmap]: All 101 v1 requirements mapped; 0 orphans; 0 deferred to v2
- [Phase 01-correctness-audit]: model_fields_set over exclude_none for PATCH partial updates — distinguishes not-sent from sent-as-null
- [Phase 01-correctness-audit]: Hard delete utils/errors.py with no deprecation period — internal library, single test consumer
- [Phase 01-correctness-audit]: Canonical error import is django_matt.core.errors — zero utils.errors references remain
- [Phase 01-correctness-audit]: Custom model classmethods (OAuthConnection.get_or_none, SSOConnection.get_for_*, SSOUserLink.get_user, user_is_org_admin) retain sync_to_async wrapping — they contain internal sync ORM and cannot be converted without touching model layer
- [Phase 01-correctness-audit]: request.user.is_authenticated is a boolean property not a lazy DB attribute — safe to access directly in async context without sync_to_async
- [Phase 01-correctness-audit]: DJANGO_ALLOW_ASYNC_UNSAFE=true was already absent from all project files — Plans 01-01 and 01-02 had already eliminated all sync/async ORM boundary violations
- [Phase 01-correctness-audit]: CLAUDE.md Known Issues section cleared — all 3 stale items resolved by Phase 1 plans; section rewritten with resolution references
- [Phase 02-performance-baseline]: apply_api_mode() strips by dotted path match, always guards MIDDLEWARE_KEEP_LIST; mutation only in AppConfig.ready() to avoid side effects during management commands
- [Phase 02-performance-baseline]: cProfile test pattern: 10 warmup calls to populate _hints_cache, then profile 100 calls — absence of get_type_hints in pstats proves zero per-request introspection (CORE-09)
- [Phase 02-performance-baseline]: Skipped framework rows use metadata skipped=True rather than silent omission — rich table shows [NOT INSTALLED]
- [Phase 02-performance-baseline]: run_all.py always saves timestamped JSON to .matt/benchmarks/ unconditionally — not only when --save is passed
- [Phase 02-performance-baseline]: assert_query_count wraps CaptureQueriesContext — context manager + decorator; cache key md5(prefix:path:querystring)
- [Phase 02-performance-baseline]: TestCacheResponseDecorator uses content equality not object identity — Django cache pickles responses across locmem cache
- [Phase 03-cli-and-type-generation]: CORE-11 implementation was already correct; only missing test coverage — 9 dedicated tests added to lock in static-before-parameterized URL ordering
- [Phase 03-cli-and-type-generation]: sync_types --from-openapi triggers live OpenAPISchema.build(); --openapi-file reads pre-built spec for CI use case
- [Phase 03-cli-and-type-generation]: generate_ai_context --depth (minimal/standard/full) drives max_endpoints/max_models/max_schemas via depth_config dict; minimal routes-only sets model/schema counts to 0
- [Phase 03-cli-and-type-generation]: isort section ordering for generated code: stdlib -> django -> third-party -> first-party -> local-folder (matches project ruff config)
- [Phase 03-cli-and-type-generation]: Generated tests omit @pytest.mark.asyncio — project uses asyncio_mode=auto globally
- [Phase 03-cli-and-type-generation]: startapi CLAUDE.md and CI config generation scoped to b2b/saas templates only
- [Phase 03-cli-and-type-generation]: CheckResult dataclass for doctor tiers: typed structure enables pattern matching and easier testing than dict
- [Phase 03-cli-and-type-generation]: collect_routes_data() extracted as module-level helper: separates data collection from Rich rendering for testability
- [Phase 03-cli-and-type-generation]: getattr(settings, 'BASE_DIR', Path.cwd()) in matt_migrate_from: safe fallback when test settings don't define BASE_DIR
- [Phase 04-auth-hardening-and-multi-tenancy]: IsOrgMember/IsOrgAdmin/IsOrgOwner use sync Membership.objects.filter() — permission checks called from sync pipeline; TENANT_SUPERUSER_BYPASS defaults True for B2B convenience
- [Phase 04-auth-hardening-and-multi-tenancy]: SSOConfig.from_settings() fixed to use _defaults=cls() instance instead of cls.field_name to read dataclass field(default_factory=...) values safely
- [Phase 04-auth-hardening-and-multi-tenancy]: Integration tests patch get_sso_config at consuming module namespace (controllers.get_sso_config), not definition site (config.get_sso_config)

### Pending Todos

None yet.

### Blockers/Concerns

- [Pre-Phase 1]: DJANGO_ALLOW_ASYNC_UNSAFE=true in conftest.py masks async/sync ORM violations — entire async correctness story is unverified until this is removed
- [Pre-Phase 1]: Duplicate error classes in utils/errors.py and core/errors.py must be consolidated before Phase 1 completes
- [Pre-Phase 2]: CONN_MAX_AGE misconfiguration is a production deploy blocker — must be verified correct in all deployment templates (Phase 7)
- [Pre-Phase 4]: JWT blacklist purge command must exist and be tested post-logout before multi-tenancy builds on auth

## Session Continuity

Last session: 2026-03-08T03:24:43.441Z
Stopped at: Completed 04-02-PLAN.md
Resume file: None

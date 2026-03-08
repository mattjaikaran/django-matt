---
phase: 02-performance-baseline
plan: 02
subsystem: api
tags: [middleware, performance, cprofile, type-hints, api-mode]

# Dependency graph
requires:
  - phase: 01-correctness-audit
    provides: clean async/ORM baseline, canonical error imports, no DJANGO_ALLOW_ASYNC_UNSAFE

provides:
  - MATT_API_MODE=True setting that strips CSRF/Sessions/Messages/Clickjacking on startup
  - apply_api_mode() function in django_matt/config/components/performance.py
  - AppConfig.ready() hook that applies middleware stripping at server start only
  - cProfile-verified proof that get_type_hints() is never called per-request after warmup
  - 5 new tests covering CORE-12 and CORE-09 requirements

affects:
  - 02-03 (performance benchmarks will build on clean middleware profile)
  - deployment (MATT_API_MODE is a production setting, should be in deployment templates)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AppConfig.ready() as the only place to mutate settings at startup"
    - "MIDDLEWARE_STRIP_LIST / MIDDLEWARE_KEEP_LIST constants for declarative middleware profiling"
    - "Module-level _hints_cache dict[int, dict] keyed by id(endpoint) for zero per-request introspection"
    - "cProfile + pstats for CI-verifiable hot-path regression tests"

key-files:
  created: []
  modified:
    - django_matt/config/components/performance.py
    - django_matt/apps.py
    - tests/test_performance.py

key-decisions:
  - "apply_api_mode() strips by dotted path match against MIDDLEWARE_STRIP_LIST, always guarding MIDDLEWARE_KEEP_LIST"
  - "Middleware mutation lives in AppConfig.ready() only — never at module import time (avoids running during migrations/collectstatic)"
  - "MIDDLEWARE_KEEP_LIST prevents accidental removal of SecurityMiddleware and CommonMiddleware even if a future author adds them to the strip list"
  - "cProfile test primes the cache with 10 warmup calls, then profiles 100 more — absence of get_type_hints in pstats proves zero per-request introspection"

patterns-established:
  - "API-mode middleware profile: strip browser-oriented middleware declaratively via MATT_API_MODE setting"
  - "Hot-path caching verification: use cProfile + pstats.print_stats() to assert zero calls of expensive introspection functions in CI"

requirements-completed: [CORE-12, CORE-09]

# Metrics
duration: 2min
completed: 2026-03-08
---

# Phase 02 Plan 02: API-Mode Middleware Profile and Hot-Path Introspection Caching Summary

**Single MATT_API_MODE=True setting strips 4 browser middleware at startup via AppConfig.ready(), with cProfile CI test confirming zero get_type_hints() calls per-request after warmup**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-08T00:18:28Z
- **Completed:** 2026-03-08T00:20:11Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- Added `MATT_API_MODE` setting, `MIDDLEWARE_STRIP_LIST`, `MIDDLEWARE_KEEP_LIST`, and `apply_api_mode()` to `django_matt/config/components/performance.py`
- Wired `AppConfig.ready()` in `apps.py` to call `apply_api_mode()` when `MATT_API_MODE=True`, with a guard to prevent execution during migrations and collectstatic
- Added 5 new tests to `tests/test_performance.py`: 4 covering CORE-12 middleware stripping and 1 covering CORE-09 zero-introspection via cProfile

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement MATT_API_MODE middleware stripping** - `4463d15` (feat)
2. **Task 2: Write middleware stripping test and cProfile hot-path test** - `c33de7f` (test)

**Plan metadata:** (docs commit — created below)

## Files Created/Modified

- `django_matt/config/components/performance.py` — Added `MATT_API_MODE`, `MIDDLEWARE_STRIP_LIST`, `MIDDLEWARE_KEEP_LIST` constants and `apply_api_mode()` function with INFO/WARNING logging
- `django_matt/apps.py` — Updated `DjangoMattConfig.ready()` to call `apply_api_mode()` when `MATT_API_MODE=True`
- `tests/test_performance.py` — Appended `TestApiModeMiddlewareStripping` (4 tests) and `TestNoGetTypeHintsPerRequest` (1 test) classes

## Decisions Made

- `apply_api_mode()` guards against accidental `MIDDLEWARE_KEEP_LIST` removal even if someone adds Security or Common middleware to the strip list
- Middleware mutation happens exclusively in `AppConfig.ready()` to avoid side effects during Django management commands (migrations, collectstatic)
- The cProfile test deliberately uses 10 warmup iterations before profiling 100 calls, matching the research finding that the first call populates the cache

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- CORE-12 and CORE-09 verified and passing in CI
- `MATT_API_MODE` is a production-ready setting; deployment templates (Phase 7) should document it
- Phase 02 Plan 03 (performance benchmarks) can proceed — clean middleware profile is now in place

---
*Phase: 02-performance-baseline*
*Completed: 2026-03-08*

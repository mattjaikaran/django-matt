---
phase: 07-deployment-observability-and-completion
plan: 01
subsystem: infra
tags: [django, asgi, conn_max_age, deployment, docker, uvicorn]

# Dependency graph
requires:
  - phase: 01-correctness-audit
    provides: async-first correctness foundation
provides:
  - CONN_MAX_AGE=0 enforced across all deploy/config files
  - ASGI-default Docker templates
  - CONN_MAX_AGE enforcement test suite (13 tests)
affects: [deployment, config, docker]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CONN_MAX_AGE=0 default for ASGI safety (Django #33497)"
    - "DockerfileConfig defaults to ASGI (use_asgi=True)"

key-files:
  created: []
  modified:
    - django_matt/deploy/environments.py
    - django_matt/deploy/docker.py
    - django_matt/config/components/database.py
    - django_matt/config/environments/production.py
    - django_matt/config/environments/staging.py
    - django_matt/config/settings/prod.py
    - django_matt/config/settings/staging.py
    - django_matt/config/settings/dev.py
    - tests/test_deploy.py

key-decisions:
  - "CONN_MAX_AGE=0 everywhere -- persistent connections leak under ASGI (Django #33497)"
  - "DockerfileConfig.use_asgi defaults True -- ASGI is the framework standard, WSGI is legacy"
  - "User can still override CONN_MAX_AGE via DB_CONN_MAX_AGE env var -- safe escape hatch"

patterns-established:
  - "All new deploy/config defaults must use CONN_MAX_AGE=0 with ASGI comment"

requirements-completed: [DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-06]

# Metrics
duration: 3min
completed: 2026-03-09
---

# Phase 7 Plan 01: CONN_MAX_AGE=0 Enforcement Summary

**CONN_MAX_AGE=0 enforced across all 7 deploy/config files with 13 enforcement tests and ASGI-default Docker templates**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-09T03:39:49Z
- **Completed:** 2026-03-09T03:42:59Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Every hardcoded CONN_MAX_AGE default changed to 0 with Django #33497 comment
- DockerfileConfig now defaults to ASGI (use_asgi=True) so production Dockerfiles use uvicorn
- 13 new enforcement tests verify all presets, providers, and config paths emit CONN_MAX_AGE=0

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix CONN_MAX_AGE=0 enforcement in all deploy and config files** - `c1544b8` (fix)
2. **Task 2: Add CONN_MAX_AGE enforcement tests for all providers** - `caa1a3b` (test, committed by prior agent)

## Files Created/Modified
- `django_matt/deploy/environments.py` - Production preset conn_max_age 600->0
- `django_matt/deploy/docker.py` - DockerfileConfig.use_asgi default False->True
- `django_matt/config/components/database.py` - Default fallback None/600->0
- `django_matt/config/environments/production.py` - DB_CONN_MAX_AGE default 600->0
- `django_matt/config/environments/staging.py` - DB_CONN_MAX_AGE default 600->0
- `django_matt/config/settings/prod.py` - CONN_MAX_AGE None->0
- `django_matt/config/settings/staging.py` - CONN_MAX_AGE 300->0
- `django_matt/config/settings/dev.py` - CONN_MAX_AGE 60->0
- `tests/test_deploy.py` - TestConnMaxAgeEnforcement class (13 tests)

## Decisions Made
- CONN_MAX_AGE=0 everywhere: persistent connections leak under ASGI (Django #33497); connection pooling should be handled at the pool layer (psycopg3 pool), not by Django's CONN_MAX_AGE
- DockerfileConfig.use_asgi=True by default: django-matt is async-first, WSGI is legacy
- User override via DB_CONN_MAX_AGE env var preserved: escape hatch for users who know what they're doing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing test for DockerfileConfig default**
- **Found during:** Task 2
- **Issue:** Existing test_default_values asserted use_asgi=False, broke after changing default to True
- **Fix:** Updated assertion to assertTrue(config.use_asgi)
- **Files modified:** tests/test_deploy.py
- **Verification:** All 92 tests pass, 1 skipped (dj_database_url not installed)
- **Committed in:** caa1a3b

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for test consistency. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CONN_MAX_AGE production blocker resolved (STATE.md blocker cleared)
- Ready for remaining Phase 7 plans (observability, completion)

---
*Phase: 07-deployment-observability-and-completion*
*Completed: 2026-03-09*

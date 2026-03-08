---
phase: 04-auth-hardening-and-multi-tenancy
plan: "01"
subsystem: auth
tags: [jwt, blacklist, csrf, revocation, cache, security]

# Dependency graph
requires:
  - phase: 01-correctness-audit
    provides: async-safe ORM calls, canonical error imports
  - phase: 03-cli-and-type-generation
    provides: doctor CheckResult dataclass, collect_routes_data pattern
provides:
  - "JWT blacklist default changed to 'cache' (secure by default)"
  - "Per-user bulk token revocation with cache sentinel"
  - "averify_access_token checks per-user revocation sentinel"
  - "change_password bulk-revokes before issuing new tokens"
  - "CSRF exemption wired for all MattAPI(csrf=False) endpoints"
  - "Startup warning when DEBUG=False and blacklist is null"
  - "matt_status doctor check for JWT blacklist configuration"
affects: [05-billing, 06-graphql, 07-deployment, multitenancy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-user revocation sentinel: cache key {prefix}user_revoked:{user_id} stores Unix timestamp"
    - "Token revocation check: both JTI blacklist AND per-user sentinel in verify_access_token"
    - "CSRF exemption: view_func._csrf_exempt = True set in get_urls() when csrf=False"
    - "Bulk revoke on password change: abulk_revoke_tokens_for_user before acreate_token_pair"

key-files:
  created: []
  modified:
    - django_matt/auth/blacklist/config.py
    - django_matt/auth/blacklist/core.py
    - django_matt/auth/jwt.py
    - django_matt/auth/controllers.py
    - django_matt/apps.py
    - django_matt/core/router.py
    - django_matt/api.py
    - django_matt/management/commands/matt_status.py
    - tests/test_blacklist.py
    - tests/test_auth.py

key-decisions:
  - "Default blacklist backend changed to 'cache' — production secure out of box, null requires explicit opt-out"
  - "Per-user revocation sentinel stored in cache (not DB) — avoids migration, uses existing cache infra, TTL auto-expiry"
  - "iat timestamp comparison for sentinel: token.iat.timestamp() < sentinel_ts rejects pre-revocation tokens"
  - "CSRF exemption via view_func._csrf_exempt = True in get_urls() — cleanest integration point, visible in URL patterns"
  - "change_password calls abulk_revoke_tokens_for_user before acreate_token_pair — ensures old tokens invalid before new ones issued"

patterns-established:
  - "Bulk revocation pattern: store timestamp sentinel in cache, check iat < sentinel in verify"
  - "get_urls(csrf_exempt=bool) parameter propagates CSRF flag from MattAPI to APIRouter"
  - "Tests use __wrapped__ to bypass jwt_required decorator when testing controller methods directly"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-06, AUTH-07, AUTH-11, AUTH-12, AUTH-13]

# Metrics
duration: 90min
completed: 2026-03-08
---

# Phase 4 Plan 01: JWT Blacklist Hardening and CSRF Exemption Summary

**JWT blacklist default changed to 'cache', bulk per-user token revocation wired to password change, and CSRF exemption propagated to all MattAPI-registered endpoints**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-03-08T04:00:00Z
- **Completed:** 2026-03-08T05:30:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 10

## Accomplishments

- Changed JWT blacklist default backend from "null" to "cache" — production-secure without explicit configuration
- Implemented `bulk_revoke_tokens_for_user` / `abulk_revoke_tokens_for_user` using a per-user cache sentinel with TTL=refresh_token_lifetime
- Wired per-user sentinel check into both `verify_access_token` (sync) and `averify_access_token` (async) — after JTI blacklist check
- Wired `abulk_revoke_tokens_for_user` into `AuthController.change_password` before issuing new tokens
- Added startup warning in `DjangoMattConfig.ready()` when `DEBUG=False` and blacklist is "null"
- Added JWT Blacklist check to `matt_status` doctor command (Warning tier)
- Added `csrf_exempt` parameter to `APIRouter.get_urls()` and wired it through `MattAPI.get_urls()`
- All 4357 tests pass (32 skipped for optional deps)

## Task Commits

Each task was committed atomically:

1. **Task 1: JWT blacklist hardening, bulk revocation, startup warning, doctor check** - `90b07bc` (feat)
2. **Task 2: CSRF exemption for all JWT-protected API endpoints** - `f9fbc5d` (feat)

## Files Created/Modified

- `django_matt/auth/blacklist/config.py` - Default backend changed from "null" to "cache"
- `django_matt/auth/blacklist/core.py` - Added bulk_revoke_tokens_for_user, abulk_revoke_tokens_for_user, is_user_tokens_revoked, ais_user_tokens_revoked
- `django_matt/auth/jwt.py` - verify_access_token and averify_access_token now check per-user revocation sentinel
- `django_matt/auth/controllers.py` - change_password calls abulk_revoke_tokens_for_user before issuing new tokens
- `django_matt/apps.py` - Startup warning when DEBUG=False and blacklist is "null"
- `django_matt/core/router.py` - get_urls() accepts csrf_exempt parameter, sets _csrf_exempt=True on view functions
- `django_matt/api.py` - get_urls() passes csrf_exempt=not self.csrf to super().get_urls()
- `django_matt/management/commands/matt_status.py` - JWT Blacklist warning check added to _check_security()
- `tests/test_blacklist.py` - Updated default assertions, added TestBulkRevocation and TestAverifyAccessTokenBulkRevocation
- `tests/test_auth.py` - Added TestLogoutBlacklistsToken, TestChangePasswordRevokesOldTokens, TestCSRFExemption

## Decisions Made

- Default blacklist backend changed to "cache" — production secure out of box, existing tests that relied on null default updated to explicitly set `BLACKLIST_BACKEND: "null"`
- Per-user revocation sentinel stored in cache (not DB) — no migration needed, uses existing Django cache infrastructure, auto-expires via TTL
- `iat` timestamp comparison: `token.iat.timestamp() < sentinel_ts` rejects pre-revocation tokens; new tokens issued after `abulk_revoke_tokens_for_user` have iat > sentinel so they are accepted
- CSRF exemption wired via `view_func._csrf_exempt = True` in `get_urls()` — cleanest integration that's visible in URL patterns and doesn't require decorator changes
- `change_password` calls `abulk_revoke_tokens_for_user` before `acreate_token_pair` — strict ordering ensures old tokens are invalid before new ones exist

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MagicMock sub in existing blacklist integration tests causing cache key warnings**
- **Found during:** Task 1 (running existing tests after adding per-user sentinel check)
- **Issue:** Existing tests set `fake_payload.jti` but not `fake_payload.sub`, leaving sub as a MagicMock. The new sentinel check tries to create a cache key with the MagicMock string representation, triggering CacheKeyWarning
- **Fix:** Added `fake_payload.sub = None` to tests that don't need to test per-user sentinel, causing the sentinel check to be skipped
- **Files modified:** tests/test_blacklist.py
- **Verification:** No more CacheKeyWarning in test output
- **Committed in:** 90b07bc (Task 1 commit)

**2. [Rule 1 - Bug] Fixed test calling controller.change_password(request) as if it were a bound method**
- **Found during:** Task 1 (writing change_password revocation test)
- **Issue:** When accessed via `controller.change_password`, the @jwt_required wrapped function doesn't bind as a descriptor, so calling `controller.change_password(request)` passes request as `self_or_request` (not request), causing `get_request()` to return None and producing a 500 "Request not found"
- **Fix:** Used `AuthController.change_password.__wrapped__(controller, request)` to bypass @jwt_required decorator and call the underlying method with explicit self — consistent with existing tests that use `.__wrapped__` or unbound method calls
- **Files modified:** tests/test_auth.py
- **Verification:** Test passes, response.status_code == 200
- **Committed in:** 90b07bc (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug in test setup, 1 bug in test calling pattern)
**Impact on plan:** Both auto-fixes were test-side only. No changes to production code were needed beyond what was planned.

## Issues Encountered

- SQLite table-locking issue when mixing sync user fixture with async test — resolved by using `@pytest.mark.django_db(transaction=True)` and creating users inside the async test via `sync_to_async(User.objects.create_user)(...)`
- The `abulk_revoke_tokens_for_user` import in the test needed to patch at `django_matt.auth.controllers.abulk_revoke_tokens_for_user` (the module where it's imported), not at the source module

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- JWT revocation is now production-ready; both single-token (JTI) and bulk (per-user) revocation work
- CSRF exemption is automatic for all `MattAPI`-registered endpoints
- Multi-tenancy phase (04-02+) can build on hardened auth knowing tokens are properly revocable
- Pre-Phase 4 blocker resolved: "JWT blacklist purge command must exist and be tested post-logout before multi-tenancy builds on auth"

## Self-Check: PASSED

All created/modified files verified to exist. Both task commits (90b07bc, f9fbc5d) verified in git log.

---
*Phase: 04-auth-hardening-and-multi-tenancy*
*Completed: 2026-03-08*

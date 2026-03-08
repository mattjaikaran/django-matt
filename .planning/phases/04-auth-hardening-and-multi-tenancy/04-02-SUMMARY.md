---
phase: 04-auth-hardening-and-multi-tenancy
plan: "02"
subsystem: auth
tags: [permissions, multitenancy, oauth, sso, oidc, integration-tests, pytest]

# Dependency graph
requires:
  - phase: 04-auth-hardening-and-multi-tenancy
    provides: Phase context with auth subsystem architecture and multitenancy models

provides:
  - IsOrgMember, IsOrgAdmin, IsOrgOwner org-aware permission classes in permissions/common.py
  - OAuth Google + GitHub end-to-end integration tests (controller-level, mocked HTTP)
  - OIDC SSO end-to-end integration tests (controller-level, mocked token exchange)
  - SSOConfig.from_settings() bug fix for dataclass field default access
  - 536+ tests passing across all auth subsystems

affects:
  - phase: 04-03 (multitenancy controllers use IsOrgMember/IsOrgAdmin/IsOrgOwner)
  - phase: 05 (billing builds on auth permission model)
  - phase: 06 (feature flags may gate by org membership)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Org-aware permission classes extend BasePermission and read request.organization
    - TENANT_SUPERUSER_BYPASS setting controls superuser bypass (default True)
    - Membership.objects.filter() is the canonical org membership check pattern
    - SSOConfig.from_settings() uses a default instance to safely read field(default_factory=...) values
    - Integration tests patch at the import site (e.g., controllers.get_sso_config) not the definition site

key-files:
  created:
    - django_matt/permissions/common.py (IsOrgMember, IsOrgAdmin, IsOrgOwner added)
  modified:
    - django_matt/permissions/__init__.py (exports new classes)
    - django_matt/auth/sso/config.py (from_settings bug fix)
    - tests/test_auth.py (TestOrgPermissionClasses: 14 tests)
    - tests/test_auth_oauth.py (TestOAuthGoogleIntegration: 5 tests, TestOAuthGitHubIntegration: 3 tests)
    - tests/test_auth_sso.py (TestOIDCIntegration: 5 tests)

key-decisions:
  - "IsOrgMember/IsOrgAdmin/IsOrgOwner use sync Membership.objects.filter() — permission check pipeline is called from sync context"
  - "TENANT_SUPERUSER_BYPASS defaults True to match common B2B platform behavior — explicitly opt-out for stricter tenancy"
  - "SSOConfig.from_settings() fix: construct _defaults = cls() to read field(default_factory=...) values; class-level access to these raises AttributeError"
  - "Integration tests patch at controllers.get_sso_config not config.get_sso_config — the controller imports it at module level so the reference lives in controllers namespace"

patterns-established:
  - "Org permission pattern: check user.is_authenticated, then org = getattr(request, 'organization', None), then superuser bypass, then Membership query"
  - "Integration test pattern: create real DB objects, mock HTTP with AsyncMock, patch get_sso_config at the consuming module's namespace"
  - "TDD pattern enforced: RED (ImportError) -> GREEN (14/13 tests passing) -> REFACTOR (lint clean)"

requirements-completed:
  - AUTH-04
  - AUTH-05
  - AUTH-08
  - AUTH-09
  - AUTH-10

# Metrics
duration: 45min
completed: 2026-03-08
---

# Phase 4 Plan 02: OAuth/SSO/Passkeys Integration Testing and Org-Aware Permissions Summary

**Org-aware permission classes (IsOrgMember/IsOrgAdmin/IsOrgOwner) with superuser bypass, plus controller-level integration tests for OAuth (Google/GitHub) and OIDC SSO flows with mocked HTTP**

## Performance

- **Duration:** 45 min
- **Started:** 2026-03-08T02:35:00Z
- **Completed:** 2026-03-08T03:20:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `IsOrgMember`, `IsOrgAdmin`, `IsOrgOwner` permission classes to `permissions/common.py` — bridge between multitenancy and controller `permission_classes` pattern
- Added 14 tests for org permission classes covering all role scenarios, superuser bypass on/off, and unauthenticated users
- Added `TestOAuthGoogleIntegration` (5 tests) and `TestOAuthGitHubIntegration` (3 tests) covering the full controller-level flow with mocked HTTP: URL generation, user creation, email linking, error cases
- Added `TestOIDCIntegration` (5 tests) covering OIDC login URL generation, callback with userinfo fallback, email linking, domain check
- Fixed pre-existing bug in `SSOConfig.from_settings()` where `cls.allowed_providers` raised `AttributeError` on dataclass field with `default_factory`

## Task Commits

Each task was committed atomically:

1. **Task 1: Org-aware permission classes and RBAC integration** - `602c983` (feat)
2. **Task 2: OAuth/SSO/Passkeys integration tests** - `fbd48c3` (feat + Rule 1 bug fix)

## Files Created/Modified

- `django_matt/permissions/common.py` - Added `IsOrgMember`, `IsOrgAdmin`, `IsOrgOwner` classes (100+ lines)
- `django_matt/permissions/__init__.py` - Exported 3 new permission classes in `__all__`
- `django_matt/auth/sso/config.py` - Fixed `from_settings()` dataclass bug
- `tests/test_auth.py` - Added `TestOrgPermissionClasses` (14 tests, ~170 lines)
- `tests/test_auth_oauth.py` - Added `TestOAuthGoogleIntegration` (5 tests) and `TestOAuthGitHubIntegration` (3 tests) (~200 lines)
- `tests/test_auth_sso.py` - Added `TestOIDCIntegration` (5 tests) (~150 lines)

## Decisions Made

- `IsOrgMember` and sibling classes use synchronous `Membership.objects.filter()` — permission checks are called from the sync permission-check pipeline, not async view handlers
- `TENANT_SUPERUSER_BYPASS` defaults to `True` matching common B2B platform behavior where admins need org-level access; opt-out explicitly by setting to `False`
- Integration tests patch `get_sso_config` at the consuming module namespace (`controllers.get_sso_config`) not the definition site — this is the correct Python mock pattern for module-level imports
- Passkey tests already had `webauthn = pytest.importorskip("webauthn")` at module level and skip cleanly when webauthn is not installed (no changes needed)
- API key test coverage was already comprehensive (creation, hashing, auth via header, scoped permissions, revocation, rate limiting, async variants) — no additions needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SSOConfig.from_settings() AttributeError on dataclass field**
- **Found during:** Task 2 (TestOIDCIntegration — test_callback_creates_user_and_links_sso)
- **Issue:** `SSOConfig.from_settings()` used `cls.allowed_providers` (and `cls.enabled`, etc.) as fallbacks, but `allowed_providers` is defined with `field(default_factory=...)` which is not accessible as a class attribute on a dataclass — raises `AttributeError: type object 'SSOConfig' has no attribute 'allowed_providers'`
- **Fix:** Construct `_defaults = cls()` before building the config instance, then use `_defaults.allowed_providers` etc. for all field defaults
- **Files modified:** `django_matt/auth/sso/config.py`
- **Verification:** `TestOIDCIntegration` tests pass; `uv run ruff check django_matt/auth/sso/config.py` clean
- **Committed in:** `fbd48c3` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug fix)
**Impact on plan:** Bug fix was necessary for OIDC integration tests to run. No scope creep.

## Issues Encountered

- OAuth integration tests passed immediately without needing the TDD RED phase (the controller code was already correct; only test coverage was missing) — this is expected for integration tests that validate working code
- SAML tests skip gracefully when `onelogin` is not installed (12 skipped) — expected behavior, not a failure

## Next Phase Readiness

- `IsOrgMember`, `IsOrgAdmin`, `IsOrgOwner` are ready for use in Plan 03 (multitenancy controllers)
- All auth subsystem integration tests pass — auth hardening phase foundation is solid
- No blockers for Phase 4 Plan 03

## Self-Check: PASSED

- FOUND: `django_matt/permissions/common.py`
- FOUND: `tests/test_auth.py` (with TestOrgPermissionClasses)
- FOUND: `tests/test_auth_oauth.py` (with TestOAuthGoogleIntegration, TestOAuthGitHubIntegration)
- FOUND: `tests/test_auth_sso.py` (with TestOIDCIntegration)
- FOUND: `.planning/phases/04-auth-hardening-and-multi-tenancy/04-02-SUMMARY.md`
- FOUND commit: `602c983` (Task 1)
- FOUND commit: `fbd48c3` (Task 2)
- Verified: All 14 org permission tests pass
- Verified: All 536 auth tests pass, 12 skip (SAML without onelogin)

---
*Phase: 04-auth-hardening-and-multi-tenancy*
*Completed: 2026-03-08*

---
phase: 04-auth-hardening-and-multi-tenancy
plan: "03"
subsystem: multitenancy
tags: [django, async, orm, multitenancy, organization, team, membership, invitation, decorators, middleware, tdd]

# Dependency graph
requires:
  - phase: 04-auth-hardening-and-multi-tenancy
    plan: "02"
    provides: "IsOrgMember, IsOrgAdmin, IsOrgOwner permission classes in permissions/common.py"
provides:
  - "Fully async OrganizationController, TeamController, MembershipController, InvitationController (19 async methods)"
  - "Async-aware decorators: requires_organization, requires_org_membership, requires_org_role, requires_org_admin, requires_org_owner, requires_min_org_role, requires_team_membership"
  - "Async utility functions: auser_is_org_admin, auser_is_org_owner, auser_can_manage_team, acreate_organization_with_owner"
  - "TenantMiddlewareAsync tests for all 4 resolution strategies (header, URL, session, user fallback)"
  - "Cross-org isolation tests proving 403 Forbidden for out-of-scope resources"
  - "Async decorator integration tests"
affects:
  - "Phase 05 — billing, features built on multitenancy"
  - "Phase 06 — requires correct async org isolation"

# Tech tracking
tech-stack:
  added: [asgiref.sync.sync_to_async (for model methods)]
  patterns:
    - "Org-scoped filter-before-lookup: .filter(organization=request.organization, id=id).afirst() — never global lookup then org check"
    - "Cross-org returns 403 not 404 (explicit denial, timing-leak prevention)"
    - "inspect.iscoroutinefunction() for async/sync decorator branching (matches auth/decorators/jwt.py pattern)"
    - "sync_to_async wrapping for model methods with internal sync ORM (accept, revoke, resend)"
    - "transaction=True on async test classes with DB access"

key-files:
  created:
    - ".planning/phases/04-auth-hardening-and-multi-tenancy/04-03-SUMMARY.md"
  modified:
    - "django_matt/multitenancy/controllers.py"
    - "django_matt/multitenancy/decorators.py"
    - "django_matt/multitenancy/utils.py"
    - "django_matt/multitenancy/middleware.py"
    - "tests/test_multitenancy.py"

key-decisions:
  - "Cross-org access returns 403 Forbidden (not 404) — explicit denial per user decision, avoids timing-leak attacks"
  - "Org-scoped filter-before-lookup pattern: .filter(organization=request.organization, id=id).afirst() never global .aget(id=id) then membership check"
  - "sync model methods (Invitation.accept, .revoke, .resend, send_invitation_email) wrapped with sync_to_async in async controllers — model layer stays sync"
  - "Async utility functions (auser_is_org_admin etc.) added alongside sync variants — sync kept for management commands/fixtures"
  - "pytest.mark.django_db(transaction=True) required for async test classes — needed for async ORM in tests"

patterns-established:
  - "Async-aware decorator: inspect.iscoroutinefunction checks, then dual async/sync wrapper branches"
  - "Sync model method wrapping: await sync_to_async(model.method)(args)"
  - "Async controller test class: async def test_*, @pytest.mark.django_db(transaction=True), await controller.method()"

requirements-completed: [AUTH-06, TENANT-01, TENANT-02, TENANT-03, TENANT-04, TENANT-05]

# Metrics
duration: 45min
completed: 2026-03-08
---

# Phase 04 Plan 03: Async Multitenancy Controllers Summary

**All 4 multitenancy controllers fully async with org-scoped queryset isolation, async-aware decorators with inspect.iscoroutinefunction detection, and comprehensive TenantMiddlewareAsync + cross-org isolation tests**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-03-08T04:00:00Z
- **Completed:** 2026-03-08T04:45:00Z
- **Tasks:** 2 (Task 1: async controllers/decorators/utils; Task 2: TDD tests)
- **Files modified:** 5

## Accomplishments

- Converted all 19 controller methods to `async def` with full async ORM (`.aget`, `.afirst`, `.aexists`, `.acreate`, `.asave`, `.adelete`, `.acount`)
- All 7 decorators now detect async vs sync views via `inspect.iscoroutinefunction` and wrap correctly
- Added async utility functions (`auser_is_org_admin`, `auser_is_org_owner`, `auser_can_manage_team`, `acreate_organization_with_owner`) alongside sync variants
- TenantMiddlewareAsync tested for all 4 resolution strategies (header, URL kwarg, session, user membership fallback)
- Cross-org isolation proven: resource outside user's org returns 403 Forbidden (not 404, per user decision)
- 214 total multitenancy tests pass (191 existing + 23 new)

## Task Commits

1. **Task 1: Async controllers, decorators, utils** - (feat(04-03))
2. **Task 2: TDD tests — TenantMiddlewareAsync + cross-org isolation** - (included in single combined commit)

## Files Created/Modified

- `django_matt/multitenancy/controllers.py` — All 19 methods async; org-scoped .filter() before .aget(); sync_to_async for model methods
- `django_matt/multitenancy/decorators.py` — 7 decorators with inspect.iscoroutinefunction async/sync branching
- `django_matt/multitenancy/utils.py` — 4 new async utility functions alongside sync variants
- `django_matt/multitenancy/middleware.py` — ValidationError added to exception catch in _resolve_from_header (Rule 1 auto-fix)
- `tests/test_multitenancy.py` — 23 new tests; existing controller tests converted to async def + transaction=True

## Decisions Made

- Cross-org access returns 403 Forbidden (not 404) — explicit denial chosen over resource-not-found, avoids timing-leak information disclosure
- Org-scoped filter-before-lookup: `.filter(organization=request.organization, id=id).afirst()` — never global `.aget(id=id)` then membership check after
- sync model methods (Invitation.accept, .revoke, .resend, send_invitation_email) wrapped with `sync_to_async` — model layer deliberately kept sync for non-async callers
- Async utility functions added alongside sync variants — sync needed for management commands and test fixtures

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Django 6 raises ValidationError for invalid UUIDs in .filter(), not ValueError**
- **Found during:** Task 2 (TenantMiddlewareAsync tests)
- **Issue:** Middleware's `_resolve_from_header` caught `(ValueError, Organization.DoesNotExist)` but Django 6.0 raises `ValidationError` when an invalid UUID string is passed to a UUID field filter, causing the test `test_invalid_org_id_in_header_sets_none` to fail with unhandled exception
- **Fix:** Added `ValidationError` to the exception tuple in both sync and async `_resolve_from_header` methods in middleware.py
- **Files modified:** `django_matt/multitenancy/middleware.py`
- **Verification:** `TestTenantMiddlewareAsync::test_invalid_org_id_in_header_sets_none` passes
- **Committed in:** Combined Task 1+2 commit

**2. [Rule 1 - Bug] Membership.user FK access triggers sync ORM in async controller delete method**
- **Found during:** Task 1 (TestMembershipController::test_delete_member)
- **Issue:** `membership.user == request.user` in delete() triggered a deferred FK load using sync ORM since `select_related("organization")` didn't include "user"
- **Fix:** Changed to `select_related("organization", "user")` and compared `membership.user_id == request.user.pk` (avoids FK traversal entirely)
- **Files modified:** `django_matt/multitenancy/controllers.py`
- **Verification:** All MembershipController tests pass
- **Committed in:** Combined Task 1+2 commit

**3. [Rule 1 - Bug] Existing controller tests called async methods synchronously**
- **Found during:** Task 1 execution
- **Issue:** TestOrganizationController, TestMembershipController, TestTeamController, TestInvitationController all used `def test_*` calling `controller.method()` directly — got coroutine objects instead of responses
- **Fix:** Converted all 4 controller test classes to `async def test_*` with `await controller.method()`, changed `@pytest.mark.django_db` to `@pytest.mark.django_db(transaction=True)`, replaced sync ORM in test setup with async equivalents
- **Files modified:** `tests/test_multitenancy.py`
- **Verification:** All 191 original tests still pass + 23 new pass = 214 total
- **Committed in:** Combined Task 1+2 commit

**4. [Rule 1 - Bug] sync model methods (accept, revoke, resend, send_invitation_email) called from async controller**
- **Found during:** Task 1 (TestInvitationController::test_accept_invitation)
- **Issue:** `invitation.accept(user)`, `invitation.revoke()`, `invitation.resend()`, and `send_invitation_email()` are sync functions with internal sync ORM, cannot be called directly from async context
- **Fix:** Wrapped each with `await sync_to_async(method)(args)` in InvitationController methods
- **Files modified:** `django_matt/multitenancy/controllers.py`
- **Verification:** All InvitationController tests pass
- **Committed in:** Combined Task 1+2 commit

---

**Total deviations:** 4 auto-fixed (4 Rule 1 bugs)
**Impact on plan:** All auto-fixes necessary for async correctness. No scope creep. Pre-existing middleware E501 warnings in docstrings are out-of-scope and untouched.

## Issues Encountered

- `AsyncRequestFactory` creates ASGIRequest objects that normalize headers differently than sync `RequestFactory` — switched middleware tests to use sync `RequestFactory` which correctly places `HTTP_X_ORGANIZATION_ID` in META and is read by `request.headers` dict correctly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Multitenancy layer is fully async-safe for ASGI deployment
- All org-scoped controllers enforce cross-org isolation with 403 returns
- Async-aware decorators ready for use in any future async views
- Phase 05 (billing) and Phase 06 (features) can build on this async multitenancy foundation

## Self-Check: PASSED

Files exist:
- django_matt/multitenancy/controllers.py: FOUND
- django_matt/multitenancy/decorators.py: FOUND
- django_matt/multitenancy/utils.py: FOUND
- django_matt/multitenancy/middleware.py: FOUND
- tests/test_multitenancy.py: FOUND
- .planning/phases/04-auth-hardening-and-multi-tenancy/04-03-SUMMARY.md: FOUND

Tests: 214 passed (uv run pytest tests/test_multitenancy.py -q)

---
*Phase: 04-auth-hardening-and-multi-tenancy*
*Completed: 2026-03-08*

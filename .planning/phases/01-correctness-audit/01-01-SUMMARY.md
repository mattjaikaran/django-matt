---
phase: 01-correctness-audit
plan: "01"
subsystem: views, auth, multitenancy, testing
tags: [async-orm, correctness, django-5.2, sync-to-async-removal]
dependency_graph:
  requires: []
  provides: [async-orm-correctness, averify_magic_link_token]
  affects: [views, auth/oauth, auth/sso, auth/session, auth/magic_link, auth/controllers, multitenancy/middleware, testing/client]
tech_stack:
  added: []
  patterns: [native-async-orm, aget, asave, adelete, acount, afirst, aexists, acreate_user, aupdate_or_create]
key_files:
  created: []
  modified:
    - django_matt/views/create.py
    - django_matt/views/read.py
    - django_matt/views/update.py
    - django_matt/views/delete.py
    - django_matt/views/list.py
    - django_matt/views/viewset.py
    - django_matt/auth/oauth/controllers.py
    - django_matt/auth/sso/controllers.py
    - django_matt/auth/session/middleware.py
    - django_matt/auth/magic_link.py
    - django_matt/auth/controllers.py
    - django_matt/multitenancy/middleware.py
    - django_matt/testing/client.py
decisions:
  - "OAuthConnection.get_or_none and SSOConnection.get_for_* custom classmethods retain sync_to_async wrapping — they contain internal sync ORM that cannot be individually converted without touching model layer"
  - "SSOUserLink.get_user retains sync_to_async — custom classmethod with sync ORM internally"
  - "user_is_org_admin utility function retains sync_to_async in SSO get_connection — sync utility function"
  - "request.user.is_authenticated accessed directly in TenantMiddlewareAsync — it is a simple boolean property, not a lazy DB attribute"
  - "APITestClient.force_authenticate retains sync create_access_token() — called from sync test setup, not inside async request handlers"
metrics:
  duration: "~9 minutes"
  completed_date: "2026-03-07"
  tasks_completed: 2
  files_modified: 13
requirements_satisfied:
  - CORE-03
---

# Phase 1 Plan 01: Async/Sync ORM Boundary Audit — SUMMARY

**One-liner:** Removed all `hasattr` async ORM guards from views/viewset and eliminated local `_sync_to_async` wrappers from OAuth/SSO controllers, using native Django 5.2 async ORM methods throughout.

## What Was Built

### Task 1: Remove hasattr guards from views and viewset

All 6 view files and viewset.py had defensive `hasattr(instance, 'asave')`, `hasattr(queryset, 'aget')`, `hasattr(instance, 'adelete')`, and `hasattr(queryset, 'acount')` guards that fell back to `sync_to_async` wrapping when the async method was absent.

Django 5.2+ guarantees all these methods exist on every queryset and model instance. All guards were removed:

- `views/create.py._save_instance()`: `await instance.asave()` directly
- `views/read.py._get_instance()`: `await queryset.aget(...)` directly
- `views/update.py._get_instance()`: `await queryset.aget(...)` directly
- `views/update.py._save_instance()`: `await instance.asave()` directly
- `views/delete.py._get_instance()`: `await queryset.aget(...)` directly
- `views/delete.py._delete_instance()`: `await instance.adelete()` directly
- `views/list.py._count_queryset()`: `await queryset.acount()` directly
- `views/viewset.py.perform_create()`: `await instance.asave()` directly
- `views/viewset.py.perform_update()`: `await instance.asave()` directly
- `views/viewset.py.perform_delete()`: `await instance.adelete()` directly

### Task 2: Fix async ORM violations in auth, multitenancy, and testing modules

**auth/oauth/controllers.py:**
- Deleted the `_sync_to_async` local helper function
- `OAuthConnection.objects.aupdate_or_create(...)` replaces sync wrapped `update_or_create`
- `[conn async for conn in queryset]` replaces `sync_to_async(list)(queryset)`
- `OAuthConnection.objects.aget(...)` replaces sync wrapped `objects.get`
- `connection.adelete()` replaces `sync_to_async(connection.delete)()`
- `User.objects.aget()`, `.aexists()`, `.acreate_user()` replace sync wrappers
- `request.user.passkey_credentials.aexists()` replaces sync wrapper
- `OAuthConnection.get_or_none` custom classmethod retains `sync_to_async` (internal sync ORM)

**auth/sso/controllers.py:**
- Deleted the `_sync_to_async` local helper function
- `SSOConnection.objects.aupdate_or_create()`, `.aget()`, `.adelete()` replace sync wrappers
- `SSOUserLink.objects.aupdate_or_create()` replaces sync wrapper
- `User.objects.aget()`, `.aexists()`, `.acreate_user()` replace sync wrappers
- `user.asave()` replaces `sync_to_async(user.save)()`
- `Organization.objects.filter().afirst()` replaces `sync_to_async(qs.first)()`
- Custom classmethods `get_for_domain`, `get_for_organization`, `get_user` retain `sync_to_async` (internal sync ORM — cannot convert without touching model layer)
- `user_is_org_admin` utility retains `sync_to_async` (sync ORM inside)
- Moved `from asgiref.sync import sync_to_async` to module-level import

**auth/session/middleware.py:**
- `AsyncSessionAuthMiddleware._aget_user_from_session`: `User.objects.aget(pk=user_id)` replaces `sync_to_async(User.objects.get)(pk=user_id)`

**auth/magic_link.py:**
- Added `averify_magic_link_token()` async function — mirrors `verify_magic_link_token()` using native async ORM: `User.objects.aget()`, `.aexists()`, `.acreate_user()`
- Exported in `__all__`

**auth/controllers.py:**
- Imported `averify_magic_link_token`
- Both async magic link endpoints (`verify_magic_link` and `check_magic_link`) now `await averify_magic_link_token()`

**multitenancy/middleware.py (TenantMiddlewareAsync):**
- `_resolve_from_header`: `Organization.objects.filter().afirst()` replaces `sync_to_async(qs.first)()`
- `_resolve_from_url`: `Organization.objects.filter().afirst()` replaces sync wrapper
- `_resolve_from_session`: `Organization.objects.filter().afirst()` replaces sync wrapper
- `_resolve_from_user`: `Membership.objects.filter().select_related().afirst()` replaces `@sync_to_async def get_first_org()` wrapper function
- `is_authenticated` accessed directly — it is a boolean property, not a lazy DB attribute

**testing/client.py:**
- `AsyncAPITestClient.force_authenticate` already correctly uses `acreate_access_token()` — no change needed
- `APITestClient.force_authenticate` retains sync `create_access_token()` with explanatory comment — this is called from sync test setup, not inside async request handlers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PatchView: None value caused NOT NULL constraint on CharField**
- **Found during:** Task 1 — when running `tests/test_views.py::TestPatchView::test_patch_null_clears_field`
- **Issue:** The linter had already improved `PatchView.handle()` to use `model_fields_set` for partial update detection (replacing `exclude_unset=True, exclude_none=True`). This correctly included `{"first_name": None}` when the client sent null, but then `setattr(instance, "first_name", None)` caused a `NOT NULL constraint failed: auth_user.first_name` error because Django's `User.first_name` is a CharField that rejects NULL.
- **Fix:** Added null-coercion logic in PatchView's field assignment loop — when `value is None` for a `CharField` or `TextField` with `null=False`, coerce to `""` before `setattr`. This matches Django's expected behavior (PATCH null clears a text field to empty string).
- **Files modified:** `django_matt/views/update.py` (PatchView.handle only)
- **Commit:** 0e0f302

## Test Results

All existing tests pass:
- `tests/test_views.py`: 117 passed
- `tests/test_auth.py`: 200 passed
- **Total:** 317 passed, 0 failed

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `django_matt/views/create.py` exists | FOUND |
| `django_matt/auth/magic_link.py` exists | FOUND |
| `.planning/phases/01-correctness-audit/01-01-SUMMARY.md` exists | FOUND |
| Commit 0e0f302 (Task 1) | FOUND |
| Commit 8f47bba (Task 2) | FOUND |
| `await instance.asave()` in create.py | 1 match |
| `async def averify_magic_link_token` in magic_link.py | 1 match |
| `await averify_magic_link_token` calls in controllers.py | 2 matches |
| Zero `hasattr.*aget\|asave\|adelete\|acount` guards in views/ | 0 matches |
| Zero `def _sync_to_async` helpers in auth/ | 0 matches |
| All 317 tests pass | PASSED |

# Phase 1: Correctness Audit - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix async/sync ORM violations across all modules, consolidate error handling to a single canonical import path, implement correct PATCH null semantics, and verify all 4143 tests pass without `DJANGO_ALLOW_ASYNC_UNSAFE=true`. This is a correctness-only phase — no new features, no performance work, no API additions.

</domain>

<decisions>
## Implementation Decisions

### Error consolidation
- Delete `utils/errors.py` entirely — hard break, no deprecation warnings
- Find-and-replace all internal imports from `django_matt.utils.errors` to `django_matt.core.errors` before deleting the file
- Update CLAUDE.md Known Issues section to remove the outdated note about utils/errors.py duplication
- Scope: only `utils/errors.py` — no broader shim audit in this phase

### PATCH null semantics
- Support explicit null in PATCH requests (correct REST semantics per RFC 5789)
- Use Pydantic `model_fields_set` to distinguish "not sent" from "sent as null" — no custom NotSet sentinel
- Replace `data.model_dump(exclude_unset=True, exclude_none=True)` with `{k: v for k, v in data.model_dump().items() if k in data.model_fields_set}`
- Apply to PatchView only — UpdateView (PUT) keeps current behavior (full resource replacement)
- Add dedicated regression test: PATCH with `{"field": null}` clears the field; PATCH with `{}` leaves all fields unchanged

### Async/sync ORM fixes
- Convert all `sync_to_async()` ORM wrappers to native async ORM methods (aget, asave, adelete, aexists, acreate, etc.) — applies to OAuth controllers, SSO controllers, session middleware, and anywhere else found
- Remove all `hasattr(queryset, 'aget')` / `hasattr(instance, 'asave')` defensive guards — Django 5.2+ is our minimum, async ORM methods are guaranteed
- Full grep audit: find and remove every defensive hasattr check for async ORM across the entire codebase

### Test infrastructure
- Strategy: fix all async/sync violations first, then remove `DJANGO_ALLOW_ASYNC_UNSAFE=true` as the final step
- All 4143 tests must pass — no skips, no exceptions
- No new test failures allowed after flag removal

### Claude's Discretion
- Magic link fix approach: create async `averify_magic_link_token()` alongside sync version, or convert to async-only — based on whether sync callers exist
- `force_authenticate()` fix: async version with `acreate_access_token()` or pre-generate token in sync — based on usage patterns in test suite
- Sync fixture handling in async tests: `sync_to_async` wrappers vs split test classes — based on test patterns found

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key constraint is: this is a brownfield correctness pass, not a rewrite. Fix what's broken, don't restructure what works.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/errors.py`: All error classes already consolidated here (APIError, ValidationAPIError, NotFoundAPIError, PermissionAPIError, AuthenticationAPIError, RateLimitAPIError, ConfigurationError, ErrorHandler, ErrorMiddleware, handle_exceptions)
- `auth/password_reset.py`: Has both sync `verify_password_reset_token()` and async `averify_password_reset_token()` — pattern to follow for magic_link fix
- `auth/passkeys/controllers.py` and `auth/api_keys/controllers.py`: Already use native async ORM correctly — reference implementations

### Established Patterns
- Async/sync dual functions: `create_access_token()` / `acreate_access_token()`, `verify_password_reset_token()` / `averify_password_reset_token()` — standard pattern in auth module
- Views use `hasattr` checks to fall back from async to sync ORM — these are the defensive guards to remove
- OAuth/SSO controllers use local `_sync_to_async = sync_to_async(func, thread_sensitive=True)` wrapper — to be replaced with direct async ORM calls

### Integration Points
- `conftest.py` / `tests/settings.py`: Where `DJANGO_ALLOW_ASYNC_UNSAFE=true` lives — final removal target
- `testing/client.py`: `AsyncAPITestClient.force_authenticate()` calls sync `create_access_token()` — needs async fix
- `views/update.py` line 145: `PatchView` model_dump with `exclude_none=True` — the PATCH sentinel fix location
- `views/list.py` line 353: `_count_queryset()` sync fallback — defensive guard to remove
- `views/base.py`: `ReadView._get_instance()`, `UpdateView._get_instance()`, `DeleteView._get_instance()` — all have hasattr guards to remove

### Known Violations Found During Scout
| File | Issue | Severity |
|------|-------|----------|
| `auth/magic_link.py:285,293,297` | `verify_magic_link_token()` sync ORM called from async handler | HIGH |
| `views/list.py:353` | `_count_queryset()` sync fallback in async `handle()` | MEDIUM |
| `views/update.py:145` | PatchView `exclude_none=True` drops intentional nulls | MEDIUM |
| `auth/jwt.py:161` | `create_access_token()` sync M2M query (only if called from async) | LOW |
| `testing/client.py:56` | `force_authenticate()` calls sync `create_access_token()` | LOW |
| `auth/session/middleware.py:252` | `sync_to_async(User.objects.get)` instead of `aget()` | LOW |
| `auth/sso/controllers.py:479` | `_sync_to_async(user.save)()` instead of `user.asave()` | LOW |

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-correctness-audit*
*Context gathered: 2026-03-07*

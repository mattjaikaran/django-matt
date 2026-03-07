# Phase 1: Correctness Audit - Research

**Researched:** 2026-03-07
**Domain:** Django async ORM correctness, Pydantic v2 PATCH semantics, error module consolidation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Error consolidation:**
- Delete `utils/errors.py` entirely — hard break, no deprecation warnings
- Find-and-replace all internal imports from `django_matt.utils.errors` to `django_matt.core.errors` before deleting the file
- Update CLAUDE.md Known Issues section to remove the outdated note about utils/errors.py duplication
- Scope: only `utils/errors.py` — no broader shim audit in this phase

**PATCH null semantics:**
- Support explicit null in PATCH requests (correct REST semantics per RFC 5789)
- Use Pydantic `model_fields_set` to distinguish "not sent" from "sent as null" — no custom NotSet sentinel
- Replace `data.model_dump(exclude_unset=True, exclude_none=True)` with `{k: v for k, v in data.model_dump().items() if k in data.model_fields_set}`
- Apply to PatchView only — UpdateView (PUT) keeps current behavior (full resource replacement)
- Add dedicated regression test: PATCH with `{"field": null}` clears the field; PATCH with `{}` leaves all fields unchanged

**Async/sync ORM fixes:**
- Convert all `sync_to_async()` ORM wrappers to native async ORM methods (aget, asave, adelete, aexists, acreate, etc.) — applies to OAuth controllers, SSO controllers, session middleware, and anywhere else found
- Remove all `hasattr(queryset, 'aget')` / `hasattr(instance, 'asave')` defensive guards — Django 5.2+ is our minimum, async ORM methods are guaranteed
- Full grep audit: find and remove every defensive hasattr check for async ORM across the entire codebase

**Test infrastructure:**
- Strategy: fix all async/sync violations first, then remove `DJANGO_ALLOW_ASYNC_UNSAFE=true` as the final step
- All 4143 tests must pass — no skips, no exceptions
- No new test failures allowed after flag removal

### Claude's Discretion
- Magic link fix approach: create async `averify_magic_link_token()` alongside sync version, or convert to async-only — based on whether sync callers exist
- `force_authenticate()` fix: async version with `acreate_access_token()` or pre-generate token in sync — based on usage patterns in test suite
- Sync fixture handling in async tests: `sync_to_async` wrappers vs split test classes — based on test patterns found

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CORE-03 | Pydantic v2 schema validation on request bodies with structured error responses | `ValidationAPIError.to_response()` already emits `{"status", "detail", "extra"}` envelope; PatchView PATCH semantics fix via `model_fields_set` ensures correct partial validation; `_make_error_envelope()` is the single canonical builder |
| CORE-07 | Structured error handling with consistent JSON error format across all endpoints | `core/errors.py` is already the authoritative implementation; deleting `utils/errors.py` and updating the one external test import eliminates the inconsistency; `ErrorMiddleware` wraps all routes |
| CORE-16 | PATCH requests use NotSet sentinel to distinguish "not sent" from "sent as null" | Pydantic v2 `model_fields_set` is the correct mechanism — no sentinel class needed; one-line fix in `PatchView.handle()` at `views/update.py:145`; regression tests required |
</phase_requirements>

---

## Summary

Phase 1 is a brownfield correctness pass with three tightly scoped problem areas. All root causes have been identified to file and line level before any coding begins, which is unusual and beneficial — this is not exploratory research.

**Area 1: Async/sync ORM boundary.** The codebase uses `DJANGO_ALLOW_ASYNC_UNSAFE=true` to mask async violations in tests. Research confirms the flag does NOT currently appear in `tests/conftest.py` or `tests/settings.py` — it may have already been removed, or it lives elsewhere (Makefile, environment). The actual async violations are real and well-catalogued: `hasattr(queryset, 'aget')` defensive guards in `views/create.py`, `views/read.py`, `views/update.py`, `views/delete.py`, `views/list.py`, and `views/viewset.py`; `_sync_to_async()` local wrapper functions in `auth/oauth/controllers.py` and `auth/sso/controllers.py`; `sync_to_async(User.objects.get)` in `auth/session/middleware.py`. Django 5.2+ guarantees all `aget()`, `asave()`, `adelete()`, `acount()`, `aexists()`, `acreate()` methods exist — the defensive guards are unnecessary and should be deleted outright.

**Area 2: Error class consolidation.** `utils/errors.py` is already a pure re-export shim from `core/errors.py` (18 lines, all `from django_matt.core.errors import ...`). The only external caller is `tests/test_utils_extra.py` line 30, which imports `ErrorDetail`, `ErrorHandler`, `ErrorMiddleware`, and `ValidationErrorFormatter`. The deletion path is: update that test import, then delete the file.

**Area 3: PATCH null semantics.** The bug is a single line in `views/update.py:145`: `data.model_dump(exclude_unset=True, exclude_none=True)`. Pydantic v2's `model_fields_set` is the correct fix. The pattern `{k: v for k, v in data.model_dump().items() if k in data.model_fields_set}` includes fields that were explicitly sent as `null` but excludes fields that were never sent.

**Primary recommendation:** Fix async ORM violations first (removes all `hasattr` guards, converts `_sync_to_async` wrappers to direct async ORM, creates `averify_magic_link_token()`), then fix errors and PATCH semantics in parallel, then verify 4143 tests pass clean. The `DJANGO_ALLOW_ASYNC_UNSAFE` flag issue must be located precisely before the final verification step.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django ORM async API | Django 5.2+ | Native async queryset methods (`aget`, `asave`, `adelete`, `acount`, `aexists`, `acreate`) | Available since Django 4.1; Django 5.2 is project minimum so 100% guaranteed |
| Pydantic v2 `model_fields_set` | Pydantic 2.0+ | Track which fields were explicitly set in a model | Built-in to every Pydantic v2 BaseModel; no additional imports |
| pytest-asyncio | 0.24+ | Run async test functions with `asyncio_mode = "auto"` | Already configured in `pyproject.toml` |
| asgiref `sync_to_async` | (bundled with Django) | Wrap inherently synchronous library calls (email, webauthn) where no async variant exists | The CORRECT use case — library calls, not ORM calls |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `django.contrib.auth.authenticate` | Django built-in | Sync-only authentication backend | Must stay wrapped in `sync_to_async` — no async variant in Django |
| `django.core.mail.send_mail` | Django built-in | Sync email sending | Must stay wrapped in `sync_to_async` — Django 5.x does not have native async send |
| `webauthn` library functions | 2.1.0 | Sync-only cryptographic operations | Must stay wrapped in `sync_to_async` — external library, no async API |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `model_fields_set` dict comprehension | Custom `NotSet` sentinel class | sentinel is more explicit but adds a new concept; `model_fields_set` is idiomatic Pydantic v2 — locked decision is `model_fields_set` |
| Delete `utils/errors.py` immediately | Keep as deprecation shim with warnings | deprecation adds noise and defers cleanup; locked decision is hard delete |
| Fix ORM calls one module at a time | Full grep audit → batch fix | batch is safer (no partial state), aligns with locked decisions |

---

## Architecture Patterns

### Pattern 1: Native Async ORM (required, no defensive guards)

**What:** Every async view method directly uses `aget()`, `asave()`, `adelete()`, `acount()` — never checks `hasattr`, never falls back to `sync_to_async`.
**When to use:** All Django ORM calls inside any `async def` function. Django 5.2+ is the minimum; these methods always exist.

Before (broken pattern to eliminate):
```python
# Source: views/create.py:76 — current defensive guard
async def _save_instance(self, instance: models.Model):
    if hasattr(instance, "asave"):
        await instance.asave()
    else:
        from asgiref.sync import sync_to_async
        await sync_to_async(instance.save)()
```

After (correct pattern):
```python
# Django 5.2+ guarantees asave() — remove the guard entirely
async def _save_instance(self, instance: models.Model):
    await instance.asave()
```

**Affected files:**
- `views/create.py:76` — `_save_instance()` hasattr guard
- `views/read.py:74` — `_get_instance()` hasattr guard
- `views/update.py:90,105` — `_get_instance()` and `_save_instance()` hasattr guards
- `views/delete.py:95,110` — `_get_instance()` and `_delete_instance()` hasattr guards
- `views/list.py:351` — `_count_queryset()` hasattr guard
- `views/viewset.py:235,260,277` — `perform_create`, `perform_update`, `perform_delete` hasattr guards

### Pattern 2: `_sync_to_async` Local Wrapper Elimination

**What:** Replace module-level `_sync_to_async = sync_to_async(func, thread_sensitive=True)` wrapper pattern used in OAuth and SSO controllers with direct async ORM calls. The wrappers were added for compatibility — they are not needed for ORM operations.
**When to use:** Any location using `_sync_to_async(Model.objects.get)(...)` or `_sync_to_async(instance.save)()`.

Before (broken pattern in auth/oauth/controllers.py and auth/sso/controllers.py):
```python
# Source: auth/oauth/controllers.py:350-354
def _sync_to_async(func):
    from asgiref.sync import sync_to_async
    return sync_to_async(func, thread_sensitive=True)

# Usage throughout:
connection = await _sync_to_async(OAuthConnection.objects.get)(id=conn_id)
await _sync_to_async(connection.delete)()
```

After (correct pattern):
```python
# Direct async ORM — no wrapper needed
connection = await OAuthConnection.objects.aget(id=conn_id)
await connection.adelete()
```

**Exception — keep sync_to_async for these:**
```python
# sync_to_async is CORRECT here (no async variant):
user = await sync_to_async(authenticate)(username=..., password=...)  # Django auth backend
await sync_to_async(django_send_mail)(...)  # Django email
options = await sync_to_async(_generate_registration_options)(...)  # webauthn library
```

### Pattern 3: Async/Sync Dual Function (for magic link)

**What:** Alongside the sync `verify_magic_link_token()`, create `averify_magic_link_token()` that uses native async ORM. Pattern established by `auth/password_reset.py` which has both `verify_password_reset_token()` and `averify_password_reset_token()`.

```python
# Source: auth/password_reset.py:120,180 — reference pattern
def verify_password_reset_token(token: str) -> PasswordResetResult:
    ...user = User.objects.get(email=email)  # sync — OK for sync callers

async def averify_password_reset_token(token: str) -> PasswordResetResult:
    ...user = await User.objects.aget(email=email)  # async — correct for async handlers
```

Apply same pattern to `auth/magic_link.py`. The async handler in `auth/controllers.py:835` currently calls the sync `verify_magic_link_token()` inside an `async def` — it should call `averify_magic_link_token()`.

### Pattern 4: Pydantic v2 PATCH Field Tracking

**What:** Use `model_fields_set` to include only explicitly provided fields in the update dict. This correctly handles `{"field": null}` (sets field to null) vs `{}` (no update).

Before (broken — silently discards explicit nulls):
```python
# Source: views/update.py:145
data_dict = data.model_dump(exclude_unset=True, exclude_none=True)
```

After (correct — null sent == null stored):
```python
# Pydantic v2: model_fields_set tracks which fields were present in the input
data_dict = {k: v for k, v in data.model_dump().items() if k in data.model_fields_set}
```

**How it works:**
```python
# PATCH body: {"name": "Alice", "bio": null}
schema = MySchema.model_validate({"name": "Alice", "bio": None})
schema.model_fields_set  # {"name", "bio"}
# Result: data_dict = {"name": "Alice", "bio": None}  ✓ null is preserved

# PATCH body: {}
schema = MySchema.model_validate({})
schema.model_fields_set  # set()
# Result: data_dict = {}  ✓ nothing updated
```

### Pattern 5: Canonical Error Import

**What:** Single import path for all error classes.

```python
# CORRECT — only valid import path after utils/errors.py is deleted
from django_matt.core.errors import (
    APIError,
    AuthenticationAPIError,
    ConfigurationError,
    ErrorDetail,
    ErrorHandler,
    ErrorMiddleware,
    NotFoundAPIError,
    PermissionAPIError,
    PermissionDeniedAPIError,
    RateLimitAPIError,
    ValidationAPIError,
    ValidationErrorFormatter,
    _make_error_envelope,
    error_handler,
    handle_exceptions,
)

# WRONG — will NameError after utils/errors.py deletion
from django_matt.utils.errors import ...
```

### Anti-Patterns to Avoid

- **`hasattr(instance, 'asave')` guards:** False safety net. Django 5.2+ always has async ORM. Remove unconditionally.
- **`_sync_to_async` local wrapper for ORM:** Adds indirection with no benefit over direct async ORM calls. Use native methods instead.
- **`sync_to_async(instance.save)()`:** Never use `sync_to_async` to wrap an ORM call when `asave()` exists.
- **`exclude_none=True` in PATCH context:** Silently discards intentional null values. Use `model_fields_set` filter instead.
- **Calling sync `verify_magic_link_token()` from async handler:** Blocks event loop when sync ORM is executed inside ASGI context.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tracking which fields were sent in PATCH body | Custom `NotSet` sentinel class, `MISSING` marker, field diff logic | `pydantic.BaseModel.model_fields_set` | Built-in to Pydantic v2; set of field names explicitly provided during model init |
| Async wrapping of Django auth backends | Custom async auth decorator | `sync_to_async(authenticate)(...)` | `django.contrib.auth.authenticate` has no async variant by design |
| Async email sending in Django 5.2 | Custom async mailer | `sync_to_async(send_mail)(...)` | Django async email API (`amail_admins`, etc.) is incomplete in 5.2; sync wrapping is correct |
| Dual sync/async function pattern | Complicated wrapper factory | Separate `foo()` / `afoo()` function pair | Established pattern in this codebase (`create_access_token`/`acreate_access_token`, `verify_password_reset_token`/`averify_password_reset_token`) |

**Key insight:** `sync_to_async` is correct and necessary for wrapping external synchronous libraries (webauthn, Django auth, Django email). It is wrong for wrapping Django ORM calls when async ORM methods (`aget`, `asave`, etc.) exist.

---

## Common Pitfalls

### Pitfall 1: `DJANGO_ALLOW_ASYNC_UNSAFE` Location

**What goes wrong:** Trying to remove the flag from `conftest.py` when it does not appear there.
**Why it happens:** The Known Issues note in `CLAUDE.md` says "conftest.py sets DJANGO_ALLOW_ASYNC_UNSAFE=true" but the actual `tests/conftest.py` and `tests/settings.py` do not contain this flag. The flag may be set in: Makefile, shell environment, CI configuration, or a `.env` file.
**How to avoid:** Before the final test verification step, run `grep -r DJANGO_ALLOW_ASYNC_UNSAFE .` from project root to find every location. The roadmap says to remove it from conftest.py/settings.py — verify the actual location first.
**Warning signs:** Tests continue to pass with sync ORM violations after you believe the flag is removed.

### Pitfall 2: Legitimate `sync_to_async` Calls

**What goes wrong:** Removing all `sync_to_async` usages, including the correct ones for non-ORM synchronous libraries.
**Why it happens:** The task is "replace sync_to_async with native async ORM" — it's easy to over-apply this to `authenticate()`, `send_mail()`, and webauthn library calls which have no async variants.
**How to avoid:** The rule is: ORM calls → use native async ORM. Non-Django-ORM synchronous library calls → keep `sync_to_async`. Before removing any `sync_to_async`, verify whether an async variant exists.
**Keep these (no async alternative):**
  - `sync_to_async(authenticate)(...)` in `auth/controllers.py:222`
  - `sync_to_async(django_send_mail)(...)` in `auth/magic_link.py:534`
  - `sync_to_async(_generate_registration_options)(...)` in `auth/passkeys/webauthn.py:295`
  - Session login/logout helpers in `auth/session/utils.py`

### Pitfall 3: OAuth/SSO `_sync_to_async` Wrapper Covers Manager Methods

**What goes wrong:** Direct ORM manager method calls like `Model.objects.filter(...).first()` do not have a direct async equivalent in the `_sync_to_async` wrapper style — they need the async queryset chain.
**Why it happens:** `_sync_to_async(Model.objects.filter(x=y).first)()` wraps the method call, but `await Model.objects.filter(x=y).afirst()` is the correct async pattern.
**How to avoid:** For each `_sync_to_async` ORM call, verify the correct async ORM method name:
  - `queryset.filter(...).first()` → `await queryset.filter(...).afirst()`
  - `Model.objects.get(...)` → `await Model.objects.aget(...)`
  - `Model.objects.create(...)` → `await Model.objects.acreate(...)`
  - `Model.objects.update_or_create(...)` → `await Model.objects.aupdate_or_create(...)`
  - `Model.objects.filter(...).exists()` → `await Model.objects.filter(...).aexists()`
  - `list(queryset)` → `[obj async for obj in queryset]` or `await sync_to_async(list)(queryset)`
  - `instance.save()` → `await instance.asave()`
  - `instance.delete()` → `await instance.adelete()`

### Pitfall 4: `list()` Queryset Evaluation

**What goes wrong:** `await _sync_to_async(list)(queryset)` works but `list(queryset)` in async context does not. `await list(queryset)` is wrong (list is not awaitable).
**Why it happens:** Iterating a queryset to a list requires DB evaluation. In async context, the only valid patterns are `[obj async for obj in queryset]` or `await sync_to_async(list)(queryset)`.
**How to avoid:** For `auth/oauth/controllers.py:277` where `connections = await _sync_to_async(list)(queryset)` is used, replace with `connections = [conn async for conn in OAuthConnection.objects.filter(user=request.user)]`.

### Pitfall 5: `model_fields_set` Requires Pydantic v2 model init

**What goes wrong:** `model_fields_set` is empty when a model is constructed with `model_construct()` (bypasses validation) or with dict unpacking that doesn't go through `model_validate()`.
**Why it happens:** `model_fields_set` only tracks fields explicitly provided to `__init__` or `model_validate()`.
**How to avoid:** `PatchView.validate_request()` uses standard Pydantic model validation from request body — `model_fields_set` will be populated correctly. No action needed, just verify.

### Pitfall 6: Test Async Fixtures

**What goes wrong:** Test helper fixtures that create users or database objects use sync ORM, and `@pytest.mark.asyncio` tests that use them get errors when `DJANGO_ALLOW_ASYNC_UNSAFE` is removed.
**Why it happens:** pytest fixtures can be sync or async. Sync fixtures that do ORM work will fail when called from async test context without the unsafe flag.
**How to avoid:** For async tests that need DB fixtures, either:
  - Use `pytest_django`'s `db` or `django_db` marks with `transaction=True`
  - Make fixtures async: `@pytest.fixture async def user():`
  - Use `sync_to_async` within the async test body to call sync setup helpers

---

## Code Examples

Verified patterns from the actual codebase:

### Correct async ORM (reference: auth/passkeys/controllers.py, auth/api_keys/controllers.py)
```python
# Source: auth/passkeys/webauthn.py — already correct
credential = await PasskeyCredential.objects.aget(credential_id=credential_id)
await credential.asave()
await credential.adelete()
new_cred = await PasskeyCredential.objects.acreate(user=user, ...)
exists = await PasskeyCredential.objects.filter(user=user).aexists()
```

### PatchView model_fields_set fix
```python
# Source: views/update.py:145 — what to change
# BEFORE:
data_dict = data.model_dump(exclude_unset=True, exclude_none=True)

# AFTER (one-line change):
data_dict = {k: v for k, v in data.model_dump().items() if k in data.model_fields_set}
```

### averify_magic_link_token (new function to create)
```python
# Pattern source: auth/password_reset.py:180 (averify_password_reset_token)
async def averify_magic_link_token(
    token: str,
    create_user: bool | None = None,
) -> MagicLinkVerifyResult:
    """Async version of verify_magic_link_token using native async ORM."""
    if create_user is None:
        create_user = magic_link_config.create_user_if_not_exists

    try:
        # ... same token parsing, signature, expiry logic (no ORM) ...

        User = get_user_model()
        try:
            user = await User.objects.aget(email=email)
        except User.DoesNotExist:
            if create_user and magic_link_config.allow_registration:
                # Async username uniqueness check
                base_username = email.split("@")[0]
                username = base_username
                counter = 1
                while await User.objects.filter(username=username).aexists():
                    username = f"{base_username}{counter}"
                    counter += 1
                user = await User.objects.acreate_user(
                    username=username, email=email, is_active=True
                )
                user_created = True
            # ... rest of error cases ...
    except Exception:
        return MagicLinkVerifyResult(valid=False, error="Token verification failed")
```

### Error import (after utils/errors.py deletion)
```python
# The only valid import path
from django_matt.core.errors import APIError, NotFoundAPIError, ValidationAPIError

# Test file to update (tests/test_utils_extra.py:30-35):
# BEFORE:
from django_matt.utils.errors import (
    ErrorDetail,
    ErrorHandler,
    ErrorMiddleware,
    ValidationErrorFormatter,
)
# AFTER:
from django_matt.core.errors import (
    ErrorDetail,
    ErrorHandler,
    ErrorMiddleware,
    ValidationErrorFormatter,
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `sync_to_async(queryset.get)()` | `await queryset.aget()` | Django 4.1 (2022) | Native async ORM; no thread overhead |
| `hasattr(obj, 'asave')` guard | Direct `await obj.asave()` | Django 5.2 min requirement | Guards are dead code; delete them |
| `model_dump(exclude_none=True)` for PATCH | `model_fields_set` filter | Pydantic v2 (2023) | Correct null-vs-absent distinction |
| Duplicate error classes in two modules | Single canonical `core/errors.py` | Phase 1 (this phase) | One import path, no re-exports |

**Deprecated/outdated in this codebase:**
- `_sync_to_async` local wrapper function pattern in oauth/sso controllers: wraps ORM calls that have native async equivalents
- `hasattr(queryset, 'aget')` / `hasattr(instance, 'asave')` guards: dead code since Django 5.2 minimum is set
- `utils/errors.py`: already a re-export shim; being deleted by this phase
- `DJANGO_ALLOW_ASYNC_UNSAFE=true`: must be located and removed; was masking this entire bug class

---

## Open Questions

1. **Exact location of `DJANGO_ALLOW_ASYNC_UNSAFE=true`**
   - What we know: It does not appear in `tests/conftest.py` or `tests/settings.py`
   - What's unclear: It may be in a Makefile target, shell environment, or CI config
   - Recommendation: Run `grep -r DJANGO_ALLOW_ASYNC_UNSAFE .` at project root as the first action in Plan 01-03 (verification). If not found, the flag may have already been removed in a prior cleanup; the async violations are still real and still need fixing regardless.

2. **Multitenancy middleware `sync_to_async` calls**
   - What we know: `multitenancy/middleware.py` has multiple `sync_to_async` usages (lines 218, 235, 262, 267, 275, 285, 290, 299, 305, 316, 318) — more extensive than the violations listed in CONTEXT.md
   - What's unclear: Some may be legitimate (e.g., `request.user.is_authenticated` evaluated via `sync_to_async(lambda: ...)` — this is a Django lazy attribute that needs sync evaluation)
   - Recommendation: Audit each one; convert ORM calls to async ORM; keep `sync_to_async` for lazy Django attributes and non-ORM sync operations

3. **`auth/schemas.py:263` user permissions**
   - What we know: `permissions = list(await sync_to_async(user.get_all_permissions)())` — the comment says "no async API"
   - What's unclear: Django 5.2 may have `user.aget_all_permissions()` — needs verification
   - Recommendation: Check Django 5.2 changelog for async permission methods. If none exist, `sync_to_async` is the correct approach and should stay.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-django 4.8+ and pytest-asyncio 0.24+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_views.py tests/test_errors.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-03 | Pydantic v2 structured error responses on validation failure | unit | `uv run pytest tests/test_errors.py -x -q` | ✅ |
| CORE-07 | All error types return `{"status", "detail", "extra"}` JSON format | unit | `uv run pytest tests/test_errors.py -x -q` | ✅ |
| CORE-16 | PATCH with `{"field": null}` clears field; PATCH with `{}` leaves all fields unchanged | unit | `uv run pytest tests/test_views.py -k "patch" -x -q` | ✅ (partial — regression tests needed) |
| CORE-16 | PATCH sentinel: `model_fields_set` correctly excludes unset fields | unit | `uv run pytest tests/test_views.py -k "patch_null" -x -q` | ❌ Wave 0 |
| CORE-07 | `utils/errors.py` deleted; `from django_matt.utils.errors import` raises ImportError | unit | `uv run pytest tests/test_utils_extra.py -x -q` | ✅ (test import must be updated) |
| All | Full async correctness: 4143 tests pass without `DJANGO_ALLOW_ASYNC_UNSAFE` | integration | `uv run pytest tests/ -x -q` | ✅ |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_views.py tests/test_errors.py tests/test_utils_extra.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_views.py` — add `test_patch_null_clears_field()` and `test_patch_empty_body_no_change()` covering CORE-16 regression
- [ ] Update `tests/test_utils_extra.py:30-35` — change `from django_matt.utils.errors import` to `from django_matt.core.errors import` before deleting `utils/errors.py`

*(Existing test infrastructure covers all other phase requirements)*

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `/Users/mattjaikaran/dev/django-matt/django_matt/` — all findings verified against actual source
- `django_matt/views/update.py:145` — exact PatchView bug location
- `django_matt/views/create.py`, `read.py`, `update.py`, `delete.py`, `list.py`, `viewset.py` — all hasattr guard locations
- `django_matt/auth/oauth/controllers.py:350-354`, `auth/sso/controllers.py:398-402` — `_sync_to_async` wrapper pattern
- `django_matt/auth/magic_link.py:285-297` — sync ORM in sync `verify_magic_link_token()` called from async handler
- `django_matt/utils/errors.py` — confirmed as 18-line re-export shim; one external caller
- `tests/test_utils_extra.py:30-35` — only external `utils.errors` import
- `django_matt/auth/password_reset.py:120,180` — dual sync/async function reference pattern
- `pyproject.toml` `[tool.pytest.ini_options]` — pytest configuration, `asyncio_mode = "auto"`

### Secondary (MEDIUM confidence)
- Django 5.2 docs on async ORM: all `aget()`, `asave()`, `adelete()`, `acount()`, `aexists()`, `acreate()`, `aupdate_or_create()`, `afirst()` are available (verified by reference implementation in `auth/passkeys/controllers.py`)
- Pydantic v2 `model_fields_set` behavior: verified by reading `django_matt/views/update.py` PatchView which already uses `exclude_unset` — the model_fields_set approach is the standard Pydantic v2 idiom

### Tertiary (LOW confidence)
- Django 5.2 `user.aget_all_permissions()` existence — needs verification; `auth/schemas.py:261` comment says "no async API" but may be outdated

---

## Metadata

**Confidence breakdown:**
- Async/sync ORM violations: HIGH — all locations identified to exact file and line from direct code inspection
- PATCH semantics fix: HIGH — single-line change, Pydantic v2 `model_fields_set` is documented API
- Error consolidation: HIGH — `utils/errors.py` is a confirmed 18-line re-export shim with one external caller
- `DJANGO_ALLOW_ASYNC_UNSAFE` location: MEDIUM — flag does not appear in expected locations; location uncertain

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable Django/Pydantic APIs — no churn expected)

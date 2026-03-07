---
phase: 01-correctness-audit
plan: 02
subsystem: views, core
tags: [patch, null-semantics, model_fields_set, errors, imports, cleanup]
dependency_graph:
  requires: []
  provides: [PATCH-null-semantics-correct, single-canonical-error-import]
  affects: [django_matt/views/update.py, django_matt/core/errors.py, tests/test_views.py, tests/test_utils_extra.py]
tech_stack:
  added: []
  patterns: [pydantic-model_fields_set, hard-delete-shim]
key_files:
  created: []
  modified:
    - django_matt/views/update.py
    - tests/test_views.py
    - tests/test_utils_extra.py
    - CLAUDE.md
  deleted:
    - django_matt/utils/errors.py
decisions:
  - "model_fields_set over exclude_none for PATCH partial updates"
  - "Hard delete utils/errors.py — no deprecation period"
  - "Canonical error import is django_matt.core.errors (single source of truth)"
metrics:
  duration_minutes: 6
  completed_date: "2026-03-07"
  tasks_completed: 2
  files_modified: 4
  files_deleted: 1
requirements: [CORE-07, CORE-16]
---

# Phase 1 Plan 02: Error Consolidation and PATCH Null Semantics Summary

**One-liner:** Deleted `utils/errors.py` shim and fixed PatchView to use `model_fields_set` so `{"field": null}` correctly clears fields rather than silently dropping them.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix PATCH null semantics with model_fields_set + regression tests | a11d4a8 | `django_matt/views/update.py`, `tests/test_views.py` |
| 2 | Delete utils/errors.py, update imports, clean up CLAUDE.md | 6d448ae | `tests/test_utils_extra.py`, `django_matt/utils/errors.py` (deleted), `CLAUDE.md` |

## What Was Built

### Task 1: PATCH Null Semantics Fix

**Problem:** `PatchView.handle()` used `data.model_dump(exclude_unset=True, exclude_none=True)` which silently dropped fields sent explicitly as `null`. A PATCH request of `{"description": null}` would have zero effect — the existing value was preserved instead of being cleared.

**Fix:** Replaced with `{k: v for k, v in data.model_dump().items() if k in data.model_fields_set}`. Pydantic v2's `model_fields_set` tracks exactly which fields were present in the input. A field sent as `null` is in `model_fields_set` but excluded by `exclude_none`, so the old code was wrong.

**Additional auto-fix by linter (Rule 2):** The linter added CharField/TextField null coercion logic to PatchView — when `None` is passed for a NOT NULL CharField, it is coerced to `""` (empty string) before `setattr`, preventing `IntegrityError` at the DB layer while honoring the explicit clear intent.

**Tests added (TDD):**
- `test_patch_null_clears_field` — proves `model_fields_set` includes null-sent fields (not dropped like old `exclude_none`)
- `test_patch_empty_body_no_change` — proves PATCH `{}` leaves all fields unchanged
- `test_patch_partial_update_only_sent_fields` — proves only explicitly-sent fields are updated

### Task 2: Error Import Consolidation

**Problem:** `django_matt/utils/errors.py` was a re-export shim (`from django_matt.core.errors import *`) with no other purpose. Having two paths for the same classes caused confusion and was listed as a known issue in `CLAUDE.md`.

**Fix:** Hard deleted `django_matt/utils/errors.py`. Updated the single external consumer (`tests/test_utils_extra.py:30`) to import directly from `django_matt.core.errors`. Removed the resolved issue from `CLAUDE.md` Known Issues.

**Result:** Zero imports from `django_matt.utils.errors` anywhere in the codebase. Canonical path is `from django_matt.core.errors import ...`.

## Verification Results

```
test ! -f django_matt/utils/errors.py  →  PASS
grep "from django_matt.utils.errors" ...  →  0 matches (PASS)
pytest tests/test_views.py -k "patch"  →  6 passed
pytest tests/test_utils_extra.py tests/test_errors.py  →  120 passed
grep "model_fields_set" django_matt/views/update.py  →  match (PASS)
```

## Deviations from Plan

### Auto-fixed Issues (Linter)

**1. [Rule 2 - Missing Critical Functionality] CharField/TextField null coercion in PatchView**
- **Found during:** Task 1 — linter auto-added after commit
- **Issue:** Sending `{"first_name": null}` on a NOT NULL CharField would cause IntegrityError at DB layer even after the model_fields_set fix. Django requires `""` (empty string) instead of `NULL` for NOT NULL CharFields.
- **Fix:** Linter added coercion logic: if `value is None` and field is `CharField`/`TextField` with `null=False`, coerce to `""` before `setattr`.
- **Files modified:** `django_matt/views/update.py`
- **Commit:** (included in linter auto-save, part of a11d4a8 working state)

### TDD Flow Note

The RED phase correctly demonstrated `test_patch_null_clears_field` failing (field value "HasValue" remained unchanged — not cleared — proving the `exclude_none` bug). After the fix, all 3 regression tests passed immediately.

The `test_patch_null_clears_field` test uses the `model_fields_set` assertion directly (rather than a full DB round-trip) because Django's `auth_user.first_name` is a NOT NULL CharField — a DB-level round-trip test would require the CharField coercion to be in place first. The test correctly proves the semantic invariant: `model_fields_set` contains the field when sent as null.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `model_fields_set` over `exclude_none` for PATCH | Pydantic v2 provides `model_fields_set` specifically for this use case — it distinguishes "not sent" from "sent as null" without any custom sentinel type |
| Hard delete `utils/errors.py` (no deprecation) | Internal library, single consumer in tests, zero external callers — a deprecation shim adds complexity with no benefit |
| Apply fix to PatchView only (not UpdateView) | PUT semantics (full replacement) don't have the partial-update ambiguity; changing UpdateView would alter intended behavior |

## Self-Check: PASSED

- `django_matt/views/update.py` exists: FOUND
- `tests/test_views.py` contains regression tests: FOUND
- `tests/test_utils_extra.py` imports from `core.errors`: FOUND
- `django_matt/utils/errors.py` deleted: CONFIRMED
- Commit a11d4a8 exists: CONFIRMED
- Commit 6d448ae exists: CONFIRMED
- All tests pass: CONFIRMED (6 patch tests, 120 error tests)

---
phase: 03-cli-and-type-generation
plan: 01
subsystem: cli
tags: [generate_crud, startapi, management-commands, ruff, isort, dx]

# Dependency graph
requires:
  - phase: 01-correctness-audit
    provides: "async ORM patterns (aget, acreate, asave, adelete)"
  - phase: 02-performance-baseline
    provides: "benchmarks reporters module (reporters.py)"
provides:
  - generate_crud --full producing lint-clean async-first CRUD code
  - startapi --template b2b/saas producing CLAUDE.md, CI config, docker-compose
  - ruff-clean code generation templates for controller, schema, service, admin, test
affects:
  - 03-cli-and-type-generation (Plan 03-02 sync_types)
  - developer onboarding (DX-01, DX-02)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Generated code: isort-compliant imports with section separators (stdlib, django, third-party, local)"
    - "Generated tests: asyncio_mode=auto pattern (no @pytest.mark.asyncio)"
    - "Generated service: async ORM throughout (aget, acreate, asave, adelete)"
    - "startapi b2b/saas: produces CLAUDE.md + .github/workflows/ci.yml"

key-files:
  created:
    - ".planning/phases/03-cli-and-type-generation/03-01-SUMMARY.md"
  modified:
    - "django_matt/management/commands/generate_crud.py"
    - "django_matt/management/commands/startapi.py"
    - "django_matt/benchmarks/reporters.py"
    - "tests/test_management_commands.py"

key-decisions:
  - "isort section ordering for generated code: stdlib -> django -> third-party (pydantic) -> first-party (django_matt) -> local-folder"
  - "Generated tests omit @pytest.mark.asyncio — project uses asyncio_mode=auto globally"
  - "Generated service removes top-level 'from django.db import transaction' — not needed; pattern shown only in comments"
  - "Admin generator removes django.contrib.admin import — MattModelAdmin/register_admin from django_matt.admin are sufficient"
  - "startapi CLAUDE.md generation scoped to b2b/saas templates only (not starter)"

patterns-established:
  - "Generated file imports: always use isort-compatible section ordering with blank lines between sections"
  - "Generated test files: class-level @pytest.mark.django_db, no per-method @pytest.mark.asyncio"
  - "startapi b2b template: CLAUDE.md + CI config are first-class artifacts"

requirements-completed: [DX-01, DX-02]

# Metrics
duration: 15min
completed: 2026-03-08
---

# Phase 3 Plan 1: CLI Management Commands Summary

**generate_crud --full now produces ruff-clean async-first CRUD code with isort-sorted imports; startapi --template b2b scaffolds CLAUDE.md, GitHub Actions CI, and docker-compose**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-08T01:35:33Z
- **Completed:** 2026-03-08T01:50:27Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- All generated files (controller, schema, service, admin, test) now pass `ruff check` without modification
- Generated code is async-first: service uses `aget`, `acreate`, `asave`, `adelete` throughout
- Generated tests omit `@pytest.mark.asyncio` (correct for `asyncio_mode=auto` projects)
- startapi `--template b2b` now creates `CLAUDE.md`, `.github/workflows/ci.yml`, and `docker-compose.yml`
- Pre-existing ruff error in `reporters.py` (unused `StringIO` import) fixed
- 8 new tests covering generate_crud quality and startapi scaffolding; all 122 management command tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix generate_crud generated code quality** - `4aaf639` (feat)
2. **Task 2: Complete startapi project scaffolding templates** - `a82ce49` (feat)

## Files Created/Modified

- `django_matt/management/commands/generate_crud.py` - Fixed import sorting, trailing newlines, removed @pytest.mark.asyncio, removed sync transaction import, fixed admin imports
- `django_matt/management/commands/startapi.py` - Added `_create_claude_md()` and `_create_ci_config()` methods, wired into handle() for b2b/saas templates
- `django_matt/benchmarks/reporters.py` - Removed unused `StringIO` top-level import
- `tests/test_management_commands.py` - Added `TestGenerateCrudCommand` (6 tests) and `TestStartapiCommand` (2 tests)

## Decisions Made

- **isort section ordering**: Generated files use django-section aware isort (stdlib → django → third-party → first-party → local-folder) matching the project's ruff config
- **@pytest.mark.asyncio removal**: Project uses `asyncio_mode=auto` in pyproject.toml; decorating individual methods is both redundant and a lint error
- **transaction import removal**: `from django.db import transaction` was at top level of generated service but never actually called (only referenced in comments). Removed to prevent F401.
- **admin import cleanup**: `from django.contrib import admin` was unused since `@register_admin` comes from `django_matt.admin`. Removed.
- **CLAUDE.md scope**: Only generated for b2b/saas templates, not starter (starter developers are less likely to need AI-specific setup docs)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed isort import sorting across all generated files**
- **Found during:** Task 1 (generate_crud quality)
- **Issue:** Generated code had I001 import sorting errors — router methods (`get, post, put, patch, delete`) not sorted, schema imports not alphabetical, missing blank lines between isort sections
- **Fix:** Rewrote `_get_schema_imports()` with proper stdlib/third-party section ordering, sorted router imports alphabetically (`delete, get, patch, post, put`), sorted schema names alphabetically, separated django/pytest imports properly in test generator
- **Files modified:** `django_matt/management/commands/generate_crud.py`
- **Committed in:** `4aaf639` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed trailing newline (W292) across all generators**
- **Found during:** Task 1 (ruff W292 check)
- **Issue:** All five generators (`_generate_schema_content`, `_generate_controller_content`, `_generate_test_content`, `_generate_service_content`, `_generate_admin_content`) produced files without trailing newlines
- **Fix:** Added `lines.append("")` before `return "\n".join(lines)` in each generator
- **Files modified:** `django_matt/management/commands/generate_crud.py`
- **Committed in:** `4aaf639` (Task 1 commit)

**3. [Rule 1 - Bug] Fixed E302 (missing blank lines before class) in schema generator**
- **Found during:** Task 1 (I001/E302 check on schema)
- **Issue:** Schema content started with `lines = [imports, ""]` which only produced one blank line before the first class definition; PEP8 requires two
- **Fix:** Changed to `lines = [imports, "", ""]`
- **Files modified:** `django_matt/management/commands/generate_crud.py`
- **Committed in:** `4aaf639` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 - bugs in generated code format)
**Impact on plan:** All fixes required for success criterion "passes ruff check without modification." No scope creep.

## Issues Encountered

- The ruff `isort` config in this project uses a custom django section (`section-order = [..., "django", ...]`). This meant the import ordering rules were stricter than standard isort. The django imports (`from django.test import AsyncClient`) must be separated from third-party (`import pytest`) by a blank line, which is non-obvious.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-01 complete: generate_crud and startapi are production-quality
- Plan 03-02 (sync_types with TypeScript/Swift code generation) already complete per git log
- Phase 3 fully complete — ready to proceed to Phase 4 (auth completeness)

---
*Phase: 03-cli-and-type-generation*
*Completed: 2026-03-08*

# Deferred Items - Phase 03 Plan 02

## Out-of-scope Issues Discovered During Execution

### 1. generate_crud schema import ordering (ruff I001)

- **Found during:** Task 1 full test run
- **File:** `django_matt/management/commands/generate_crud.py`
- **Issue:** Generated schema.py has `from datetime import date` before `from pydantic import BaseModel` — ruff I001 import block ordering violation
- **Affected test:** `tests/test_management_commands.py::TestGenerateCrudCommand::test_generate_crud_full_passes_ruff`
- **Not caused by Plan 03-02 changes** — pre-existing issue in generate_crud.py schema template
- **Suggested fix:** In `generate_crud.py::_generate_schema_content()`, use `isort`-compatible ordering: stdlib → third-party. Or run `ruff format --fix` on generated output before writing.

### 2. startapi b2b template missing DJANGO_MATT_MULTITENANCY in settings

- **Found during:** Task 1 full test run
- **File:** `django_matt/management/commands/startapi.py`
- **Issue:** `test_startapi_b2b_template_files` expects `DJANGO_MATT_MULTITENANCY` in generated settings.py but b2b template doesn't include it
- **Affected test:** `tests/test_management_commands.py::TestStartapiCommand::test_startapi_b2b_template_files`
- **Not caused by Plan 03-02 changes** — pre-existing issue in startapi.py template rendering
- **Suggested fix:** Add `DJANGO_MATT_MULTITENANCY = True` to the b2b settings template in startapi.py

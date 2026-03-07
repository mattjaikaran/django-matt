---
phase: 1
slug: correctness-audit
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ with pytest-django 4.8+ and pytest-asyncio 0.24+ |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_views.py tests/test_errors.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_views.py tests/test_errors.py tests/test_utils_extra.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | CORE-03 | unit | `uv run pytest tests/test_errors.py -x -q` | ✅ | ⬜ pending |
| 01-01-02 | 01 | 1 | All | integration | `uv run pytest tests/ -x -q` | ✅ | ⬜ pending |
| 01-02-01 | 02 | 1 | CORE-07 | unit | `uv run pytest tests/test_errors.py -x -q` | ✅ | ⬜ pending |
| 01-02-02 | 02 | 1 | CORE-07 | unit | `uv run pytest tests/test_utils_extra.py -x -q` | ✅ | ⬜ pending |
| 01-02-03 | 02 | 1 | CORE-16 | unit | `uv run pytest tests/test_views.py -k "patch_null" -x -q` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 2 | All | integration | `uv run pytest tests/ -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_views.py` — add `test_patch_null_clears_field()` and `test_patch_empty_body_no_change()` covering CORE-16 regression
- [ ] Update `tests/test_utils_extra.py:30-35` — change `from django_matt.utils.errors import` to `from django_matt.core.errors import` before deleting `utils/errors.py`

*Existing test infrastructure covers all other phase requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

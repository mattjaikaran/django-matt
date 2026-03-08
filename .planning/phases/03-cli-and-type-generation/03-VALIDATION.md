---
phase: 3
slug: cli-and-type-generation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-django 4.11.1 + pytest-asyncio |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_typegen.py tests/test_management_commands.py tests/test_cli_module.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_typegen.py tests/test_management_commands.py tests/test_cli_module.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | DX-02 | integration+lint | `pytest tests/test_management_commands.py -k "generate_crud" -x` | Partial | ⬜ pending |
| 03-01-02 | 01 | 1 | DX-01 | integration | `pytest tests/test_management_commands.py -k "startapi" -x` | Partial | ⬜ pending |
| 03-01-03 | 01 | 1 | CORE-11 | unit | `pytest tests/test_core_controller.py -k "static" -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | DX-03 | unit+integration | `pytest tests/test_typegen.py -k "typescript" -x` | ✅ | ⬜ pending |
| 03-02-02 | 02 | 1 | DX-04 | unit | `pytest tests/test_typegen.py -k "swift" -x` | ✅ | ⬜ pending |
| 03-02-03 | 02 | 1 | DX-05 | unit | `pytest tests/test_typegen.py -k "zod" -x` | ✅ | ⬜ pending |
| 03-02-04 | 02 | 1 | DX-06 | integration | `pytest tests/test_ai_context.py tests/test_ai_context_enhanced.py -x` | ✅ | ⬜ pending |
| 03-03-01 | 03 | 2 | DX-07 | integration | `pytest tests/test_management_commands.py -k "doctor or routes" -x` | Partial | ⬜ pending |
| 03-03-02 | 03 | 2 | DX-08 | unit | `pytest tests/test_management_commands.py -k "migrate" -x` | Partial | ⬜ pending |
| 03-03-03 | 03 | 2 | DX-11 | lint | `uv run ruff check examples/` | Needs check | ⬜ pending |
| 03-03-04 | 03 | 2 | DX-09 | unit | `pytest tests/test_testing_module.py -k "authenticate" -x` | ✅ | ⬜ pending |
| 03-03-05 | 03 | 2 | DX-10 | unit | `pytest tests/test_testing_module.py -x` | ✅ | ⬜ pending |
| 03-03-06 | 03 | 2 | CORE-01 | unit | `pytest tests/test_core_controller.py -x` | ✅ | ⬜ pending |
| 03-03-07 | 03 | 2 | CORE-02 | unit | `pytest tests/test_di_autowire.py -x` | ✅ | ⬜ pending |
| 03-03-08 | 03 | 2 | CORE-04 | unit | `pytest tests/test_views.py -x` | ✅ | ⬜ pending |
| 03-03-09 | 03 | 2 | CORE-05, CORE-06 | unit | `pytest tests/test_openapi.py -x` | ✅ | ⬜ pending |
| 03-03-10 | 03 | 2 | CORE-13 | unit | `pytest tests/test_di.py -x` | ✅ | ⬜ pending |
| 03-03-11 | 03 | 2 | CORE-14 | unit | `pytest tests/test_negotiation.py -x` | ✅ | ⬜ pending |
| 03-03-12 | 03 | 2 | CORE-15 | unit | `pytest tests/test_versioning.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_core_controller.py` — add `test_static_before_parameterized_url_order` — covers CORE-11
- [ ] `tests/test_management_commands.py` — add `test_generate_crud_full_passes_ruff` — covers DX-02 lint verification
- [ ] `tests/test_management_commands.py` — add `test_startapi_b2b_template_files` — covers DX-01 b2b/saas templates
- [ ] Fix pre-existing lint: `uv run ruff check --fix django_matt/benchmarks/reporters.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Swift SDK compiles in Xcode | DX-04 | Requires Xcode/Swift toolchain | Generate Swift output, paste into Xcode project, verify it compiles |
| AI context useful for LLM | DX-06 | Subjective quality check | Feed generated CLAUDE.md to Claude, ask it to generate django-matt code |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 2
slug: performance-baseline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-django |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_performance.py tests/test_benchmarks.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~350 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_performance.py tests/test_benchmarks.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | PERF-07 | unit | `uv run pytest tests/test_benchmarks.py -k test_benchmark_runner -x` | ✅ | ⬜ pending |
| 02-01-02 | 01 | 1 | PERF-07 | manual | `make benchmark` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | CORE-12 | unit | `uv run pytest tests/test_performance.py -k test_api_mode_strips_middleware -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | CORE-09 | unit | `uv run pytest tests/test_performance.py -k test_no_get_type_hints_per_request -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | CORE-10 | unit | `uv run pytest tests/test_performance.py -k test_orjson_used_everywhere -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | CORE-08 | unit | `uv run pytest tests/test_views.py -k test_list_uses_model_construct -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | PERF-04 | unit | `uv run pytest tests/test_views.py -k test_optimize_queryset_prevents_n_plus_1 -x` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 2 | PERF-08 | unit | `uv run pytest tests/test_performance.py -k test_assert_query_count -x` | ❌ W0 | ⬜ pending |
| 02-03-04 | 03 | 2 | PERF-05 | unit | `uv run pytest tests/test_performance.py -k test_streaming_memory_threshold -x` | ✅ | ⬜ pending |
| 02-03-05 | 03 | 2 | PERF-06 | unit | `uv run pytest tests/test_performance.py -k test_cache_response_decorator -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_performance.py` — stubs for: `test_api_mode_strips_middleware`, `test_no_get_type_hints_per_request`, `test_orjson_used_everywhere`, `test_streaming_memory_threshold`, `test_cache_response_decorator`, `test_assert_query_count`
- [ ] `tests/test_views.py` — stubs for: `test_list_uses_model_construct`, `test_optimize_queryset_prevents_n_plus_1`

*Existing test infrastructure (pytest, conftest.py, fixtures) covers all framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `make benchmark` produces rich table with framework comparison rows | PERF-07 | Visual output inspection required | Run `make benchmark`, verify table shows django-matt, DRF, django-ninja, FastAPI, Starlette with req/s + median latency + relative % columns |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

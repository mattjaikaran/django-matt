---
phase: 02-performance-baseline
plan: 01
subsystem: benchmarks
tags: [benchmarks, performance, orjson, rich, framework-comparison]
dependency_graph:
  requires: []
  provides:
    - FrameworkComparisonScenario (django_matt.benchmarks.comparison)
    - RichTableReporter (django_matt.benchmarks.reporters)
    - timestamped JSON results in .matt/benchmarks/
    - test_orjson_used_everywhere (CORE-10)
  affects:
    - django_matt/benchmarks/__init__.py
    - benchmarks/run_all.py
    - benchmarks/bench_comparison.py
    - Makefile benchmark target
tech_stack:
  added:
    - rich.table.Table for terminal benchmark output
    - FrameworkComparisonScenario extending BenchmarkScenario
    - RichTableReporter extending BenchmarkReporter
    - pyproject.toml [benchmark] optional-dep group (DRF, ninja, fastapi, psutil)
  patterns:
    - "Skipped framework rows use metadata={'skipped': True, 'reason': '...'} — not silent omission"
    - "run_all.py always saves timestamped JSON to .matt/benchmarks/ after every run"
    - "bench_comparison.py delegates to FrameworkComparisonScenario — no inline simulated benchmarks"
key_files:
  created:
    - django_matt/benchmarks/comparison.py
  modified:
    - django_matt/benchmarks/reporters.py
    - django_matt/benchmarks/__init__.py
    - benchmarks/run_all.py
    - benchmarks/bench_comparison.py
    - Makefile
    - pyproject.toml
    - tests/test_performance.py
decisions:
  - "bench_utils.BenchmarkResult conversion requires total_time_ms field — added to conversion loop in run_all.py"
  - "RichTableReporter uses separate _format_rich_ops()/_format_rich_ms() to avoid name clash with HTMLReporter's existing _format_ops/_format_time methods"
  - "run_all.py --rich defaults to True; --no-rich disables it for CI/non-color terminals"
metrics:
  duration: "5 minutes"
  completed: "2026-03-08"
  tasks_completed: 2
  files_created: 1
  files_modified: 7
requirements_satisfied: [PERF-07, CORE-10]
---

# Phase 02 Plan 01: Framework Comparison Benchmark Suite Summary

**One-liner:** Added FrameworkComparisonScenario + RichTableReporter so `make benchmark` renders a colored rich.table.Table comparing django-matt vs DRF/ninja/FastAPI/Starlette (with [NOT INSTALLED] rows for missing frameworks) and saves timestamped JSON to `.matt/benchmarks/`.

## What Was Built

### Task 1: FrameworkComparisonScenario and RichTableReporter

**`django_matt/benchmarks/comparison.py`** — New `FrameworkComparisonScenario(BenchmarkScenario)`:
- `name = "framework_comparison"`, extends the existing `BenchmarkScenario` ABC
- Benchmarks 5 frameworks, each with 2 sub-benchmarks: list serialization (20 items) and create validation
- django-matt: uses `model_construct()` for list (fast path), `model_validate()` for create
- DRF: `serializers.Serializer` with `is_valid()` and `.data`
- django-ninja: `ninja.Schema` wrapping Pydantic (same pattern as django-matt)
- FastAPI: Pydantic `model_validate()` (FastAPI delegates to Pydantic internally)
- Starlette: raw `orjson.dumps()` on plain dicts (no schema layer = raw ASGI baseline)
- Missing frameworks return `BenchmarkResult(metadata={"skipped": True, "reason": "..."})` instead of being silently omitted

**`django_matt/benchmarks/reporters.py`** — New `RichTableReporter(BenchmarkReporter)`:
- Uses `rich.console.Console` and `rich.table.Table` (consistent with `cli/console.py` patterns)
- For `framework_comparison` scenario: columns are Framework, List (ops/s), Create (ops/s), Median (ms), vs DRF
- `[NOT INSTALLED]` shown in cells for skipped frameworks
- django-matt row highlighted `style="green"`
- `vs DRF` = `list_dm_ops / list_drf_ops` ratio, or `N/A` if DRF not installed
- For other scenarios: generic table (Benchmark, Mean, Ops/s, Min, Max)
- `report()` returns rendered string; `print_report()` prints directly via `Console`

**`django_matt/benchmarks/__init__.py`** — exports `FrameworkComparisonScenario` and `RichTableReporter` in `__all__`.

### Task 2: Makefile, run_all.py, bench_comparison.py, pyproject.toml, CORE-10 test

**`Makefile`** — Updated `benchmark` target:
- Default (no `SUITE=`) now runs: `uv run python benchmarks/run_all.py --comparison --rich`
- `SUITE=json|schema|database|throughput` still runs individual bench scripts
- Comment added: `# Requires: uv add --dev djangorestframework django-ninja fastapi for full comparison`

**`benchmarks/run_all.py`** — Two new flags:
- `--comparison` / (default off): imports and runs `FrameworkComparisonScenario`, prints rich table
- `--rich` / `--no-rich` (default: rich=True): selects between `RichTableReporter` and ANSI console
- Always saves timestamped JSON to `.matt/benchmarks/benchmark_YYYYMMDD_HHMMSS.json` after every run
- Also maintains `.matt/benchmarks/latest.json` for easy baseline loading

**`benchmarks/bench_comparison.py`** — Rewritten to delegate to `FrameworkComparisonScenario`:
- Replaced inline "simulated FastAPI" benchmarks with actual framework imports
- `--rich` / `--no-rich` controls reporter; defaults to rich output
- Calculates and prints "django-matt is Nx faster than DRF" if DRF installed

**`pyproject.toml`** — New `[benchmark]` optional-dependency group:
```toml
benchmark = [
    "djangorestframework>=3.15.0",
    "django-ninja>=1.3.0",
    "fastapi>=0.115.0",
    "psutil>=6.0.0",
]
```

**`tests/test_performance.py`** — New `test_orjson_used_everywhere()` (CORE-10):
- Uses Python `ast` module to parse hot-path files
- Asserts zero `json.dumps` or `json.loads` calls in:
  - `django_matt/core/router.py`
  - `django_matt/core/controller.py`
  - `django_matt/views/base.py`
- All three files already use `orjson.loads()` — test confirms this invariant
- **Test passes: 1 passed**

## Verification Results

```
$ uv run python -c "from django_matt.benchmarks import FrameworkComparisonScenario, RichTableReporter; print('ok')"
ok

$ uv run pytest tests/test_performance.py -k test_orjson_used_everywhere -x -q
1 passed

$ ls .matt/benchmarks/*.json
.matt/benchmarks/benchmark_20260307_192322.json
.matt/benchmarks/benchmark_20260307_192337.json
.matt/benchmarks/latest.json
```

Rich table output (with DRF/ninja/FastAPI/Starlette not installed):
```
                         Framework Comparison Benchmark
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Framework      ┃    List (ops/s) ┃  Create (ops/s) ┃  Median (ms) ┃   vs DRF ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ django-matt    │    41.98K ops/s │    91.50K ops/s │     16.38 us │      N/A │
│ DRF            │ [NOT INSTALLED] │ [NOT INSTALLED] │            - │      N/A │
│ django-ninja   │ [NOT INSTALLED] │ [NOT INSTALLED] │            - │      N/A │
│ FastAPI        │ [NOT INSTALLED] │ [NOT INSTALLED] │            - │      N/A │
│ Starlette      │ [NOT INSTALLED] │ [NOT INSTALLED] │            - │      N/A │
└────────────────┴─────────────────┴─────────────────┴──────────────┴──────────┘
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed bench_utils.BenchmarkResult field mismatch**
- **Found during:** Task 2, `run_all.py` integration
- **Issue:** `bench_utils.BenchmarkResult` requires `total_time_ms` as a positional field; conversion loop omitted it
- **Fix:** Added `total_time_ms=r.total_time_ms` to the conversion loop in `run_all.py`
- **Files modified:** `benchmarks/run_all.py`
- **Commit:** 87bf210

**2. [Rule 2 - Missing functionality] run_all.py always saves JSON**
- **Found during:** Task 2, reviewing plan spec
- **Issue:** Plan said "Save results to .matt/benchmarks/ as timestamped JSON" but original run_all.py only saved when `--save` was passed
- **Fix:** Added `_save_to_matt_benchmarks()` call unconditionally at end of `main()`, so every run produces a timestamped record
- **Files modified:** `benchmarks/run_all.py`
- **Commit:** 87bf210

**3. [Rule 1 - Bug] RichTableReporter method name collision**
- **Found during:** Task 1, appending to reporters.py
- **Issue:** `HTMLReporter` and `MarkdownReporter` in the same file already define `_format_ops()`/`_format_time()` with different signatures
- **Fix:** Named the new methods `_format_rich_ops()` and `_format_rich_ms()` to avoid inheritance confusion and name shadowing
- **Files modified:** `django_matt/benchmarks/reporters.py`
- **Commit:** 19d7a4e

## Success Criteria Confirmation

- [x] **PERF-07:** `make benchmark` calls `run_all.py --comparison --rich` which renders a rich colored table with all 5 frameworks (missing ones show [NOT INSTALLED])
- [x] **CORE-10:** `test_orjson_used_everywhere` passes — zero `json.dumps`/`json.loads` in the 3 hot-path files
- [x] **Historical results:** Every `run_all.py` invocation saves `benchmark_YYYYMMDD_HHMMSS.json` to `.matt/benchmarks/`

## Commits

| Hash | Description |
|------|-------------|
| 19d7a4e | feat(02-01): add FrameworkComparisonScenario and RichTableReporter |
| 87bf210 | feat(02-01): wire Makefile, run_all.py, bench_comparison, pyproject; CORE-10 test |

## Self-Check: PASSED

All created files exist. Both commits verified in git log:
- `19d7a4e` feat(02-01): add FrameworkComparisonScenario and RichTableReporter
- `87bf210` feat(02-01): wire Makefile, run_all.py, bench_comparison, pyproject; CORE-10 test

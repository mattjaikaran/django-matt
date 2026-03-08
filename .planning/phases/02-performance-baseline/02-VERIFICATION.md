---
phase: 02-performance-baseline
verified: 2026-03-08T00:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 02: Performance Baseline Verification Report

**Phase Goal:** Establish performance baseline — benchmark suite, profiling, caching, query optimization verification
**Verified:** 2026-03-08
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All 11 must-have truths drawn from PLAN frontmatter across plans 02-01, 02-02, and 02-03.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running `make benchmark` produces a rich colored table comparing frameworks with ops/s and median latency columns | VERIFIED | `Makefile` benchmark target calls `run_all.py --comparison --rich`; `RichTableReporter._build_comparison_table()` renders Framework, List (ops/s), Create (ops/s), Median (ms), vs DRF columns |
| 2 | Benchmark results are saved as timestamped JSON in `.matt/benchmarks/` after each run | VERIFIED | `_save_to_matt_benchmarks()` called unconditionally in `run_all.py main()`; `.matt/benchmarks/benchmark_20260307_192322.json`, `benchmark_20260307_192337.json`, `latest.json` confirmed present |
| 3 | If DRF/ninja/FastAPI are not installed the table shows [NOT INSTALLED] rows instead of silently omitting them | VERIFIED | `_make_skipped_result()` returns `BenchmarkResult(metadata={"skipped": True, ...})`; `_build_comparison_table()` renders `[NOT INSTALLED]` for skipped frameworks |
| 4 | orjson is used for all JSON serialization in hot paths — no stdlib json.dumps calls in router, controller, or views | VERIFIED | Grep on `core/router.py`, `core/controller.py`, `views/base.py` shows only `orjson.loads()` calls; `test_orjson_used_everywhere` AST test passes |
| 5 | `MATT_API_MODE=True` in Django settings auto-strips CSRF, Sessions, Messages, and Clickjacking middleware on startup | VERIFIED | `apply_api_mode()` in `config/components/performance.py` removes all 4 from `MIDDLEWARE_STRIP_LIST`; `AppConfig.ready()` calls it when `MATT_API_MODE=True` |
| 6 | SecurityMiddleware and CommonMiddleware remain active even with `MATT_API_MODE=True` | VERIFIED | `MIDDLEWARE_KEEP_LIST` guards both; `apply_api_mode()` logic checks keep-list before strip-list; `test_api_mode_keeps_security_middleware` passes |
| 7 | Server startup logs clearly show which middleware were stripped and which remain active | VERIFIED | `apply_api_mode()` logs stripped list at INFO and active list at INFO via `logging.getLogger("django_matt")`; warning logged if nothing stripped |
| 8 | Zero `get_type_hints()` calls occur during request handling after app warmup — confirmed by cProfile test | VERIFIED | `test_no_get_type_hints_per_request` in `TestNoGetTypeHintsPerRequest`: 10 warmup + 100 profiled calls, pstats confirms `get_type_hints` absent from stats; test passes |
| 9 | `assert_query_count` works as both context manager and decorator, raising AssertionError with query details when count mismatches | VERIFIED | `assert_query_count` class in `testing/assertions.py` implements `__enter__`/`__exit__` (wrapping `CaptureQueriesContext`) and `__call__`; `TestAssertQueryCount` all pass |
| 10 | `model_construct()` is used on all list serialization ORM-read paths — verified by code audit test | VERIFIED | `TestListUsesModelConstruct.test_list_uses_model_construct` audits `views/list.py` source for `model_construct`/`from_orm_fast`/`from_queryset_fast`/`serialize_fast` — passes |
| 11 | `@cache_response` decorator caches view responses using Django cache backend and returns cached result on repeat calls | VERIFIED | `cache_response()` in `utils/performance.py` uses `django_cache.get/set` with `md5(path+querystring)` key; `TestCacheResponseDecorator` confirms body executes once, content matches on second call |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `django_matt/benchmarks/comparison.py` | `FrameworkComparisonScenario` class | VERIFIED | Substantive: 336 lines; 5 framework methods (`_run_django_matt`, `_run_drf`, `_run_django_ninja`, `_run_fastapi`, `_run_starlette`), each with graceful ImportError fallback; wired via `benchmarks/__init__.py` export and `run_all.py` import |
| `django_matt/benchmarks/reporters.py` | `RichTableReporter` using `rich.table.Table` | VERIFIED | Substantive: 824 lines; `class RichTableReporter` at line 608 uses `from rich.table import Table` and `from rich.console import Console`; `report()` + `print_report()` both implemented |
| `django_matt/benchmarks/__init__.py` | Exports `FrameworkComparisonScenario` and `RichTableReporter` | VERIFIED | Both in `__all__`, both imported at top of module |
| `Makefile` | Updated `benchmark:` target | VERIFIED | Target at line 662; calls `run_all.py --comparison --rich`; `SUITE=` param still supported; comment present |
| `benchmarks/run_all.py` | `--rich` and `--comparison` flags, saves JSON | VERIFIED | `--comparison` argparse flag wired to `FrameworkComparisonScenario`; `--rich`/`--no-rich` controls reporter; `_save_to_matt_benchmarks()` called unconditionally |
| `django_matt/config/components/performance.py` | `MATT_API_MODE`, `MIDDLEWARE_STRIP_LIST`, `apply_api_mode()` | VERIFIED | All 3 present; `apply_api_mode()` filters by strip list, guards keep list, logs at INFO |
| `django_matt/apps.py` | `AppConfig.ready()` calling `apply_api_mode` | VERIFIED | `ready()` guards with `getattr(settings, 'MATT_API_MODE', False)`, imports and calls `apply_api_mode(list(settings.MIDDLEWARE))` |
| `django_matt/testing/assertions.py` | `class assert_query_count` | VERIFIED | Class at line 328; `__enter__`, `__exit__`, `captured_queries`, `__call__` all implemented; uses `connections[self.using]` for multi-db |
| `django_matt/utils/performance.py` | `def cache_response` | VERIFIED | Module-level function at line 417; sync/async dispatch via `asyncio.iscoroutinefunction`; key prefix + path + querystring hashed with md5 |
| `tests/test_performance.py` | Tests for orjson audit, api_mode, get_type_hints, assert_query_count, streaming, cache | VERIFIED | `test_orjson_used_everywhere`, `TestApiModeMiddlewareStripping` (4 tests), `TestNoGetTypeHintsPerRequest`, `TestAssertQueryCount`, `TestStreamingMemoryThreshold`, `TestCacheResponseDecorator` all present and passing (14 selected, 14 passed) |
| `tests/test_views.py` | `TestListUsesModelConstruct` and `TestOptimizeQuerysetPreventsNPlus1` | VERIFIED | Both classes present; 4 tests selected and passing |
| `pyproject.toml` | `[benchmark]` optional-dependency group | VERIFIED | `djangorestframework>=3.15.0`, `django-ninja>=1.3.0`, `fastapi>=0.115.0`, `psutil>=6.0.0` in `[project.optional-dependencies].benchmark` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `Makefile` | `benchmarks/run_all.py` | `benchmark:` target calls `run_all.py --comparison --rich` | WIRED | Confirmed at Makefile line 668 |
| `benchmarks/run_all.py` | `django_matt/benchmarks/comparison.py` | `import FrameworkComparisonScenario` | WIRED | Import at line 66 of run_all.py |
| `django_matt/benchmarks/reporters.py` | `rich.table` | `RichTableReporter` uses `from rich.table import Table` | WIRED | Imports inside `_build_comparison_table()` and `_build_generic_table()` |
| `django_matt/apps.py` | `django_matt/config/components/performance.py` | `ready()` imports and calls `apply_api_mode()` | WIRED | Confirmed in `apps.py` lines 24–30 |
| `django_matt/apps.py` | `django.conf.settings` | reads `MATT_API_MODE` and `MIDDLEWARE` | WIRED | `getattr(settings, 'MATT_API_MODE', False)` and `settings.MIDDLEWARE` used |
| `django_matt/testing/assertions.py` | `django.test.utils.CaptureQueriesContext` | `assert_query_count` wraps it | WIRED | `from django.test.utils import CaptureQueriesContext` in `__enter__` |
| `django_matt/utils/performance.py` | `django.core.cache` | `cache_response` uses `django_cache` | WIRED | `from django.core.cache import cache as django_cache` at line 15; used in both sync and async wrappers |
| `tests/test_views.py` | `django_matt/testing/assertions.py` | N+1 test uses `assert_query_count` | WIRED | `TestOptimizeQuerysetPreventsNPlus1` imports confirmed by test passing |
| `django_matt/testing/__init__.py` | `assert_query_count` | exported in `__all__` | WIRED | `assert_query_count` present in `__all__` at line 117 |
| `django_matt/utils/__init__.py` | `cache_response` | exported in `__all__` | WIRED | `cache_response` in `__all__` at line 78 |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PERF-07 | 02-01 | Benchmark suite comparing django-matt vs DRF, django-ninja, FastAPI on equivalent endpoints | SATISFIED | `FrameworkComparisonScenario` benchmarks all 5 frameworks; `make benchmark` renders rich table; `.matt/benchmarks/` JSON files confirmed |
| CORE-10 | 02-01 | orjson used for all JSON serialization/deserialization (router, controller, views) | SATISFIED | `test_orjson_used_everywhere` AST-parses 3 hot-path files; confirms zero `json.dumps`/`json.loads` calls; test passes |
| CORE-12 | 02-02 | API-mode middleware profile — stripped middleware stack for maximum throughput | SATISFIED | `MATT_API_MODE=True` strips CSRF/Sessions/Messages/Clickjacking; `apply_api_mode()` guards Security/Common; 4 tests pass |
| CORE-09 | 02-02 | Startup-time introspection caching — zero per-request `get_type_hints()` or `_meta.fields` calls | SATISFIED | cProfile test confirms zero `get_type_hints` calls in 100 profiled requests after warmup; passes |
| CORE-08 | 02-03 | `model_construct()` fast path for list serialization (skip re-validation on ORM reads) | SATISFIED | `TestListUsesModelConstruct` code audit confirms `serialize_fast`, `from_orm_fast`, `aserialize_list` all present in source; passes |
| PERF-04 | 02-03 | Auto `optimize_queryset()` detects FK/M2M from schema for select_related/prefetch_related | SATISFIED | `TestOptimizeQuerysetPreventsNPlus1`: `select_related("content_type")` asserted for FK, `prefetch_related("permissions")` for M2M; 3 tests pass |
| PERF-05 | 02-03 | Streaming response support for large datasets | SATISFIED | `TestStreamingMemoryThreshold`: 10k records via `stream_json_list` confirmed < 50MB peak via `tracemalloc`; passes |
| PERF-06 | 02-03 | Caching utilities with configurable backends | SATISFIED | `@cache_response` decorator with Django cache backend; `TestCacheResponseDecorator` confirms body executes once, content identical on second call |
| PERF-08 | 02-03 | Query count assertion helper for tests (`assert_query_count()`) | SATISFIED | `assert_query_count` class dual-interface (context manager + decorator); `TestAssertQueryCount` confirms error includes SQL on mismatch |

**All 9 requirements satisfied.** No orphaned requirements detected — REQUIREMENTS.md maps CORE-08, CORE-09, CORE-10, CORE-12, PERF-04, PERF-05, PERF-06, PERF-07, PERF-08 to Phase 2, matching the plan frontmatter exactly.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `django_matt/benchmarks/comparison.py` | 69 | "placeholder" in docstring | Info | False positive — describes intentional skipped-framework result behavior, not a code stub |

No blockers or warnings found. The single "placeholder" match is in a docstring explaining design intent.

---

### Human Verification Required

None. All observable truths are verifiable programmatically:

- Framework comparison table: confirmed by output captured in SUMMARY and rich.table import chain
- Streaming memory: `tracemalloc` measurement is deterministic and tested
- Cache correctness: tested with `locmem` cache backend via `override_settings`
- Middleware stripping: tested with controlled middleware list via `override_settings`

---

### Commit Verification

All 6 commits confirmed present in git log:

| Hash | Description |
|------|-------------|
| `19d7a4e` | feat(02-01): add FrameworkComparisonScenario and RichTableReporter |
| `87bf210` | feat(02-01): wire Makefile, run_all.py, bench_comparison, pyproject; CORE-10 test |
| `4463d15` | feat(02-02): implement MATT_API_MODE middleware stripping |
| `c33de7f` | test(02-02): add MATT_API_MODE and hot-path introspection caching tests |
| `36c9f87` | feat(02-03): add assert_query_count and cache_response |
| `30051d3` | test(02-03): add verification tests for PERF-04, PERF-05, PERF-06, PERF-08, CORE-08 |

---

### Test Run Summary

```
tests/test_performance.py: 14 selected, 14 passed in 0.47s
tests/test_views.py: 4 selected, 4 passed in 0.12s
```

All phase-02 tests pass. Full suite context: previously confirmed at 4255 passed, 32 skipped.

---

## Summary

Phase 02 goal fully achieved. The three plans delivered:

**Plan 01 (PERF-07, CORE-10):** `FrameworkComparisonScenario` benchmarks django-matt against DRF, django-ninja, FastAPI, and Starlette with graceful `[NOT INSTALLED]` rows for missing dependencies. `RichTableReporter` renders a colored `rich.table.Table`. `make benchmark` invokes the full stack. Timestamped JSON results persist to `.matt/benchmarks/`. orjson hot-path audit passes via AST test.

**Plan 02 (CORE-12, CORE-09):** `MATT_API_MODE=True` in Django settings strips 4 browser-oriented middleware at server startup via `AppConfig.ready()`, preserving Security and Common middleware. cProfile CI test confirms zero `get_type_hints()` calls per-request after warmup populates `_hints_cache`.

**Plan 03 (CORE-08, PERF-04, PERF-05, PERF-06, PERF-08):** `assert_query_count` is a dual-interface (context manager + decorator) test utility wrapping `CaptureQueriesContext` with full SQL details on mismatch. `@cache_response` caches view responses against Django's cache backend with URL-discriminated keys. Streaming 10k records via `stream_json_list` stays under 50MB peak. `optimize_queryset()` N+1 prevention confirmed by mock-patched select_related/prefetch_related assertions. `model_construct()` fast path confirmed by code audit.

---

_Verified: 2026-03-08_
_Verifier: Claude (gsd-verifier)_

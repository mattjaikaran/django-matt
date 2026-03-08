---
phase: 02-performance-baseline
plan: "03"
subsystem: testing-utils, performance
tags: [assert_query_count, cache_response, streaming, n+1, model_construct]
dependency_graph:
  requires: ["02-02"]
  provides: [assert_query_count, cache_response, streaming-memory-test, n+1-prevention-test, model-construct-audit]
  affects: [django_matt/testing, django_matt/utils/performance, tests/test_performance.py, tests/test_views.py]
tech_stack:
  added: []
  patterns:
    - "assert_query_count wraps CaptureQueriesContext — context manager + decorator dual interface"
    - "cache_response decorator uses hashlib.md5(path+query) as cache key — different URLs = different entries"
    - "cache_response detects sync vs async via asyncio.iscoroutinefunction"
    - "Streaming test uses tracemalloc.get_traced_memory() for peak RSS measurement"
key_files:
  created: []
  modified:
    - django_matt/testing/assertions.py
    - django_matt/testing/__init__.py
    - django_matt/utils/performance.py
    - django_matt/utils/__init__.py
    - tests/test_performance.py
    - tests/test_views.py
decisions:
  - "assert_query_count.__exit__ checks exc_type is None before asserting — body exceptions propagate naturally"
  - "cache_response key prefix is md5(key_prefix:path:querystring) — path + params as discriminant"
  - "TestCacheResponseDecorator uses response content equality not object identity — Django cache pickles objects"
  - "TestOptimizeQuerysetPreventsNPlus1 uses Django built-in Permission/Group models — no custom migration needed"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-03-08"
  tasks_completed: 2
  files_modified: 6
requirements_completed: [CORE-08, PERF-04, PERF-05, PERF-06, PERF-08]
---

# Phase 02 Plan 03: Query Count Helper, Cache Decorator, Streaming + N+1 Tests Summary

**One-liner:** assert_query_count context-manager/decorator + module-level cache_response decorator + comprehensive verification tests for model_construct, streaming memory, N+1 prevention.

## What Was Built

### Task 1: assert_query_count + cache_response (commit: 36c9f87)

**`django_matt/testing/assertions.py` — `assert_query_count` class:**
- Wraps `django.test.utils.CaptureQueriesContext` to capture queries against a named DB connection
- Context manager: `with assert_query_count(N): ...` — raises `AssertionError` with full SQL listing if actual != expected
- Decorator: `@assert_query_count(N)` on test functions — calls `__call__` to wrap via context manager
- `captured_queries` property exposes queries after context exits for further inspection
- Uses `connections[self.using]` (not bare `connection`) to support multi-db setups

**`django_matt/utils/performance.py` — `cache_response` function:**
- Module-level standalone decorator (distinct from `CacheManager.cache_response` method)
- Cache key: `md5(f"{key_prefix}:{request.path}:{request.GET.urlencode()}")` — path + query string
- Resolves request object from both plain-function and method call signatures (handles `self` arg)
- Dispatches to async or sync wrapper via `asyncio.iscoroutinefunction`
- Exported from `django_matt.utils.__init__` and `django_matt.testing.__init__`

### Task 2: Verification Tests (commit: 30051d3)

**`tests/test_performance.py` additions:**

| Test Class | Coverage |
|---|---|
| `TestAssertQueryCount` | PERF-08: context manager correct count passes, wrong count raises AssertionError with SQL, decorator variant |
| `TestStreamingMemoryThreshold` | PERF-05: 10k dict records via stream_json_list < 50MB peak via tracemalloc |
| `TestCacheResponseDecorator` | PERF-06: view body executes once, second call returns cached content; different paths = different cache entries |

**`tests/test_views.py` additions:**

| Test Class | Coverage |
|---|---|
| `TestListUsesModelConstruct` | CORE-08: code audit — serialize_fast + from_orm_fast + aserialize_list all present in source |
| `TestOptimizeQuerysetPreventsNPlus1` | PERF-04: select_related called for FK fields, prefetch_related for M2M, unchanged for flat schema |

## Success Criteria Verification

- **CORE-08:** `serialize_fast` and `from_orm_fast` confirmed in `views/base.py` source; `aserialize_list` confirmed in `views/list.py` — all list ORM reads go through model_construct path.
- **PERF-04:** `optimize_queryset()` tested with Django's built-in `Permission` (FK: `content_type`) and `Group` (M2M: `permissions`) — `select_related` and `prefetch_related` asserted called with the right field names.
- **PERF-05:** 10k dict records streamed via `stream_json_list` measure peak memory < 50MB via `tracemalloc`.
- **PERF-06:** `@cache_response(timeout=300)` decorator caches view response — call counter confirms body executes exactly once; content equality on second call.
- **PERF-08:** `assert_query_count` works as context manager and decorator, raises `AssertionError` containing SQL text when count mismatches.

## Test Results

```
4255 passed, 32 skipped in 344.04s
```

All 4255 tests pass. 32 skips are pre-existing optional-dependency skips (msgpack, redis, onelogin, strawberry).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TestCacheResponseDecorator assertIs to use content equality**
- **Found during:** Task 2 first test run
- **Issue:** `assertIs(response1, response2)` fails because Django's locmem cache serializes/deserializes via pickle — the cached response is an equal but not identical object
- **Fix:** Changed assertion to `assertEqual(response1.content, response2.content)` — verifies cached content is identical, call_counter[0] == 1 verifies body executed once
- **Files modified:** `tests/test_performance.py`
- **Commit:** 30051d3 (included in task commit)

**2. [Rule 1 - Bug] Fixed assertFalse on pytest class**
- **Found during:** Task 2 first test run
- **Issue:** `TestOptimizeQuerysetPreventsNPlus1` is a plain pytest class (no `TestCase` parent) but used `self.assertFalse()` which does not exist on plain classes
- **Fix:** Changed to `assert not result.query.select_related, "..."` — pure pytest assertion style
- **Files modified:** `tests/test_views.py`
- **Commit:** 30051d3 (included in task commit)

## Self-Check: PASSED

- `django_matt/testing/assertions.py` — `class assert_query_count` — FOUND
- `django_matt/utils/performance.py` — `def cache_response` — FOUND
- `tests/test_performance.py` — `TestAssertQueryCount` class — FOUND
- `tests/test_views.py` — `test_optimize_queryset_*` methods — FOUND
- Commit 36c9f87 — FOUND
- Commit 30051d3 — FOUND
- Full suite: 4255 passed, 32 skipped — VERIFIED

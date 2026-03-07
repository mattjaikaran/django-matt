# Phase 2: Performance Baseline - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Document django-matt's throughput vs DRF/django-ninja/FastAPI, ship API-mode middleware profile that strips browser middleware for max API throughput, verify hot-path optimizations (model_construct, cached introspection, orjson), and provide query count assertion helpers. Streaming responses and caching utilities also ship in this phase.

</domain>

<decisions>
## Implementation Decisions

### Benchmark Comparison Scope
- Compare against DRF, django-ninja, FastAPI, and Starlette (raw ASGI baseline)
- Benchmark list endpoint (serialization-heavy) and create endpoint (validation-heavy)
- Both in-process Python timing (timeit, measures framework overhead) AND HTTP load testing (wrk/hey, measures real req/s)
- Default data source: SQLite in-memory for reproducibility; `--db postgres` flag for full-stack runs
- Existing `benchmarks/` directory and `django_matt/benchmarks/` module provide scaffolding to build on

### Middleware Profile Design
- Activated via `MATT_API_MODE = True` in settings — single boolean, django-matt auto-strips non-API middleware
- Default strip list: CSRF, Sessions, Messages, Clickjacking middleware
- Keep SecurityMiddleware and CommonMiddleware always active
- Log active vs stripped middleware on server startup — developers see exactly what's running
- Prove overhead reduction with before/after cProfile comparison (function call count + timing diff)

### Benchmark Output & Makefile UX
- Rich colored table in terminal for `make benchmark` output — framework rows, metric columns, winner highlighted
- Key metrics: operations per second, median latency (ms), relative comparison ("1.8x faster than DRF")
- Single `make benchmark` target runs both framework comparison + middleware profile comparison
- Save results to `.matt/benchmarks/` as timestamped JSON — future runs show improvement delta (BENCHMARK_STORAGE_DIR already defined in runner.py)

### Performance Verification Approach
- `assert_query_count()` supports both context manager (`with assert_query_count(3):`) and decorator (`@assert_query_count(3)`) patterns
- Hot-path introspection verified via cProfile-based test: assert `get_type_hints()` and `inspect` call count == 0 after app startup — runs in CI
- Streaming verified with memory threshold test: serialize 10k+ records via StreamingHttpResponse, assert memory stays below threshold
- Caching via `@cache_response(timeout=300)` decorator on view methods, extending existing `utils/performance.py` caching — uses Django cache backend

### Claude's Discretion
- Exact rich table formatting and color scheme
- HTTP load tester choice (wrk vs hey vs locust)
- Memory threshold value for streaming verification
- cProfile test implementation details
- Benchmark iteration counts and warmup strategy
- How to structure equivalent endpoints across DRF/ninja/FastAPI for fair comparison

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `django_matt/benchmarks/runner.py`: BenchmarkResult dataclass, timing infrastructure, BENCHMARK_STORAGE_DIR
- `django_matt/benchmarks/scenarios.py`: Benchmark scenario definitions
- `django_matt/benchmarks/reporters.py`: Result output formatting
- `django_matt/utils/performance.py`: FastJSONRenderer (orjson), MessagePackRenderer, caching utilities, streaming support
- `django_matt/management/commands/benchmark.py`: Management command entry point
- `benchmarks/`: Standalone comparison scripts (bench_json, bench_comparison, bench_throughput, bench_database, bench_schema)
- `django_matt/testing/assertions.py`: assert_status, assert_json_equal — extend with assert_query_count

### Established Patterns
- orjson used throughout (core/router, core/controller, views/base, testing) — base dependency, import directly
- `model_construct()` already used in views/list.py, views/read.py, core/schema.py for list serialization
- `optimize_queryset()` already in views/base.py, views/list.py — auto-detects FK/M2M from schema
- Type hints cached at registration time (not per-request) per architectural decision
- `config/components/performance.py` exists for performance-related settings

### Integration Points
- Makefile: add `benchmark` target
- `config/components/performance.py`: add MATT_API_MODE setting
- `testing/assertions.py`: add assert_query_count
- `utils/performance.py`: extend with @cache_response decorator
- Views: verify model_construct coverage on all ORM-read list paths

</code_context>

<specifics>
## Specific Ideas

- Benchmark output should feel like pytest output — familiar to Python developers
- `make benchmark` should be the single entry point, no separate commands needed
- Middleware profile should "just work" with one setting — no manual MIDDLEWARE list editing
- Query count helper should match Django's `assertNumQueries` pattern for familiarity
- Historical comparison ("improved 12% since last run") adds developer confidence

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-performance-baseline*
*Context gathered: 2026-03-07*

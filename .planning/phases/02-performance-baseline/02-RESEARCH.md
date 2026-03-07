# Phase 2: Performance Baseline - Research

**Researched:** 2026-03-07
**Domain:** Python/Django performance benchmarking, middleware profiling, query count testing, hot-path optimization
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Compare against DRF, django-ninja, FastAPI, and Starlette (raw ASGI baseline)
- Benchmark list endpoint (serialization-heavy) and create endpoint (validation-heavy)
- Both in-process Python timing (timeit, measures framework overhead) AND HTTP load testing (wrk/hey, measures real req/s)
- Default data source: SQLite in-memory for reproducibility; `--db postgres` flag for full-stack runs
- Existing `benchmarks/` directory and `django_matt/benchmarks/` module provide scaffolding to build on
- Activated via `MATT_API_MODE = True` in settings — single boolean, django-matt auto-strips non-API middleware
- Default strip list: CSRF, Sessions, Messages, Clickjacking middleware
- Keep SecurityMiddleware and CommonMiddleware always active
- Log active vs stripped middleware on server startup
- Prove overhead reduction with before/after cProfile comparison (function call count + timing diff)
- Rich colored table in terminal for `make benchmark` output — framework rows, metric columns, winner highlighted
- Key metrics: operations per second, median latency (ms), relative comparison ("1.8x faster than DRF")
- Single `make benchmark` target runs both framework comparison + middleware profile comparison
- Save results to `.matt/benchmarks/` as timestamped JSON
- `assert_query_count()` supports both context manager and decorator patterns
- Hot-path introspection verified via cProfile-based test: assert `get_type_hints()` and `inspect` call count == 0 after app startup
- Streaming verified with memory threshold test: serialize 10k+ records via StreamingHttpResponse, assert memory stays below threshold
- Caching via `@cache_response(timeout=300)` decorator on view methods, extending existing `utils/performance.py`

### Claude's Discretion
- Exact rich table formatting and color scheme
- HTTP load tester choice (wrk vs hey vs locust)
- Memory threshold value for streaming verification
- cProfile test implementation details
- Benchmark iteration counts and warmup strategy
- How to structure equivalent endpoints across DRF/ninja/FastAPI for fair comparison

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CORE-08 | `model_construct()` fast path for list serialization (skip re-validation on ORM reads) | Already implemented in `core/schema.py::from_orm_fast()` and `views/base.py::serialize_fast()` — needs audit coverage verification and test |
| CORE-09 | Startup-time introspection caching — zero per-request `get_type_hints()` or `_meta.fields` calls | `core/router.py` has `_hints_cache` per-function; `core/controller.py` calls `get_type_hints` in `_setup_methods()` at init time — needs cProfile CI test |
| CORE-10 | orjson used for all JSON serialization/deserialization | `orjson` is a base dep; usage in controller, router, views confirmed — needs audit sweep for any remaining `json.dumps` calls in hot paths |
| CORE-12 | API-mode middleware profile — stripped middleware stack for maximum throughput | Does not exist yet — `MATT_API_MODE` setting and AppConfig startup hook to be created in `config/components/performance.py` |
| PERF-04 | Auto `optimize_queryset()` detects FK/M2M from schema for select_related/prefetch_related | Already in `views/base.py::optimize_queryset()` and called in `views/list.py` — needs N+1 test using `assert_query_count()` |
| PERF-05 | Streaming response support for large datasets | `StreamingJsonResponse` and `stream_json_list()` already in `utils/performance.py` — needs memory threshold test for 10k+ records |
| PERF-06 | Caching utilities with configurable backends | `CacheManager` and `DistributedCacheManager` in `utils/performance.py` — needs `@cache_response()` decorator added |
| PERF-07 | Benchmark suite comparing django-matt vs DRF, django-ninja, and FastAPI on equivalent endpoints | Scaffolding exists in `benchmarks/` and `django_matt/benchmarks/` — needs new `FrameworkComparisonScenario` + Makefile `benchmark` target using this suite |
| PERF-08 | Query count assertion helper for tests (`assert_query_count()`) | `testing/assertions.py` has `assert_status`, `assert_json_equal` — needs `assert_query_count` added following Django's `assertNumQueries` pattern |
</phase_requirements>

---

## Summary

Phase 2 is a performance verification and tooling phase, not a features-from-scratch phase. The existing codebase already has most of the implementation: `model_construct()` fast path, `optimize_queryset()`, streaming responses, and a robust benchmark infrastructure. The gaps are: (1) the framework comparison scenario for `make benchmark` is simulated/incomplete and needs actual DRF/ninja endpoints side-by-side; (2) `MATT_API_MODE` middleware stripping does not exist; (3) `@cache_response()` decorator is missing; and (4) `assert_query_count()` is not yet in `testing/assertions.py`.

The critical insight for planning is that existing code in `benchmarks/` simulates DRF and FastAPI behavior rather than actually running equivalent HTTP endpoints through live servers. The decision to use both in-process timing AND HTTP load testing (wrk/hey) means two distinct benchmark strategies: in-process for framework overhead, HTTP for real-world req/s. SQLite in-memory as the default data source makes the comparison reproducible without external services.

**Primary recommendation:** Build on the existing `BenchmarkRunner`/`BenchmarkScenario` infrastructure. Add a `FrameworkComparisonScenario` that runs equivalent DRF/ninja/django-matt endpoints in-process with the same test data. Extend `reporters.py` to use `rich.table.Table` (already a base dependency). Add `MATT_API_MODE` as a Django AppConfig `ready()` hook that mutates `settings.MIDDLEWARE` at startup. Add `assert_query_count` to `testing/assertions.py` using Django's `django.test.utils.CaptureQueriesContext`.

---

## Standard Stack

### Core (All Already Available as Base Dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| orjson | >=3.10.0 | JSON serialization (base dep) | 2-5x faster than stdlib json; already used throughout |
| rich | >=13.0.0 | Colored terminal tables (base dep) | Already used in `cli/console.py`; `Table`, `Console` patterns established |
| pydantic | >=2.0.0 | Schema validation (base dep) | `model_construct()` skip-validation fast path built in |
| django | >=5.2.0 | ORM query counting via `CaptureQueriesContext` | `django.test.utils.CaptureQueriesContext` is the standard approach |
| cProfile | stdlib | Function call counting for hot-path verification | Standard library, no install needed |

### Supporting (For Comparison Benchmarks — Optional Install)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| djangorestframework | >=3.15.0 | DRF comparison benchmarks | Install as optional dev dep for `make benchmark` |
| django-ninja | >=1.3.0 | Ninja comparison benchmarks | Install as optional dev dep for `make benchmark` |
| fastapi | >=0.115.0 | FastAPI comparison benchmarks | Install as optional dev dep; use with httpx for in-process testing |
| starlette | >=0.41.0 | Raw ASGI baseline | Comes with FastAPI; minimal overhead reference |
| httpx | >=0.27.0 | In-process HTTP client for FastAPI/Starlette | Already in dev deps |
| psutil | >=6.0.0 | Memory RSS measurement in benchmarks | Already used conditionally in `runner.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| cProfile | py-spy, yappi | cProfile is stdlib; sufficient for call-count verification; py-spy requires sudo |
| Django CaptureQueriesContext | SQLAlchemy event listeners | Django-native; matches `assertNumQueries` pattern developers know |
| rich.table | tabulate, prettytable | rich is already a base dep; consistent with cli/console.py patterns |
| wrk/hey (HTTP load) | locust | wrk/hey are simpler for single-endpoint throughput; locust overkill for CI |

**Installation for comparison framework benchmarks:**
```bash
uv add --optional benchmark djangorestframework django-ninja fastapi starlette psutil
```

Or as dev-only installs for local benchmark runs:
```bash
uv add --dev djangorestframework django-ninja fastapi starlette psutil
```

---

## Architecture Patterns

### Recommended Project Structure
```
django_matt/
├── benchmarks/
│   ├── runner.py               # EXISTS: BenchmarkResult, BenchmarkRunner, BENCHMARK_STORAGE_DIR
│   ├── scenarios.py            # EXISTS: JSONSerializationScenario, SchemaValidationScenario, etc.
│   ├── reporters.py            # EXISTS: ConsoleReporter — EXTEND with RichTableReporter
│   └── comparison.py           # NEW: FrameworkComparisonScenario (DRF/ninja/FastAPI/django-matt)
├── config/
│   └── components/
│       └── performance.py      # EXISTS: sparse — ADD MATT_API_MODE setting + middleware strip logic
├── utils/
│   └── performance.py          # EXISTS: StreamingJsonResponse, CacheManager — ADD @cache_response
└── testing/
    └── assertions.py           # EXISTS: assert_status, assert_json_equal — ADD assert_query_count

benchmarks/                     # EXISTS: standalone scripts — UPDATE run_all.py as `make benchmark` entry
├── run_all.py                  # UPDATE: wire up to new FrameworkComparisonScenario
├── bench_comparison.py         # UPDATE: use actual installed frameworks, not simulations
└── bench_throughput.py         # EXISTS: keep for middleware profile comparison
```

### Pattern 1: Django CaptureQueriesContext for assert_query_count
**What:** Wrap code under test in Django's query capture context, count queries, assert against expected.
**When to use:** Any test verifying N+1 prevention, optimize_queryset behavior, or query budget.
**Example:**
```python
# Source: Django docs — django.test.utils.CaptureQueriesContext
from contextlib import contextmanager
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext

class assert_query_count:
    """Context manager and decorator for asserting query counts."""

    def __init__(self, expected: int, using: str = "default"):
        self.expected = expected
        self.using = using

    def __enter__(self):
        self._ctx = CaptureQueriesContext(connection)
        self._ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._ctx.__exit__(exc_type, exc_val, exc_tb)
        actual = len(self._ctx.captured_queries)
        if exc_type is None and actual != self.expected:
            raise AssertionError(
                f"Expected {self.expected} queries, got {actual}.\n"
                f"Queries: {[q['sql'] for q in self._ctx.captured_queries]}"
            )

    def __call__(self, func):
        """Use as a decorator."""
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.__class__(self.expected, self.using):
                return func(*args, **kwargs)
        return wrapper
```

### Pattern 2: MATT_API_MODE Middleware Stripping via AppConfig
**What:** On `AppConfig.ready()`, if `MATT_API_MODE=True` in settings, mutate `settings.MIDDLEWARE` to remove non-API middleware. Log the strip decision.
**When to use:** API-only Django deployments where browser-oriented middleware wastes cycles.
**Example:**
```python
# Source: Django docs — AppConfig.ready()
# django_matt/apps.py or config/components/performance.py
from django.conf import settings
import logging
logger = logging.getLogger("django_matt")

MIDDLEWARE_STRIP_LIST = [
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

def apply_api_mode(middleware_list: list[str]) -> list[str]:
    """Remove non-API middleware, log what was stripped."""
    stripped = []
    kept = []
    for mw in middleware_list:
        if any(mw == s for s in MIDDLEWARE_STRIP_LIST):
            stripped.append(mw)
        else:
            kept.append(mw)
    if stripped:
        logger.info("MATT_API_MODE: stripped %d middleware: %s", len(stripped), stripped)
    logger.info("MATT_API_MODE: active middleware: %s", kept)
    return kept
```

### Pattern 3: cProfile Call-Count Test for Hot Path
**What:** Use `cProfile` to run a simulated request cycle, then assert that `get_type_hints` call count is zero after app startup.
**When to use:** CI gate to prevent introspection regressions being introduced into hot paths.
**Example:**
```python
import cProfile
import pstats
import io

def test_no_get_type_hints_per_request():
    """Assert get_type_hints() is not called during request handling after startup."""
    pr = cProfile.Profile()
    pr.enable()
    # simulate request handling N times
    for _ in range(100):
        handler(mock_request)
    pr.disable()
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s)
    ps.print_stats("get_type_hints")
    output = s.getvalue()
    # "get_type_hints" appears in the stats if it was called; 0 calls = not in output
    # pstats shows function name only if ncalls > 0
    assert "get_type_hints" not in output or "0 function calls" in output
```

### Pattern 4: Rich Table for Benchmark Reporter
**What:** Use `rich.table.Table` for the benchmark output in `make benchmark`, matching the project's existing `cli/console.py` patterns.
**When to use:** All benchmark output — replaces the ANSI-escape `ConsoleReporter`.
**Example:**
```python
# Source: rich docs, consistent with django_matt/cli/console.py
from rich.console import Console
from rich.table import Table

console = Console()

table = Table(title="Framework Comparison", show_header=True, header_style="bold cyan")
table.add_column("Framework", style="bold")
table.add_column("List (ops/s)", justify="right")
table.add_column("Create (ops/s)", justify="right")
table.add_column("vs DRF", justify="right")
# Winner row highlighted in green:
table.add_row("django-matt", "45,200", "38,100", "[green]1.8x[/green]", style="green")
table.add_row("DRF", "25,100", "21,200", "baseline")
console.print(table)
```

### Pattern 5: @cache_response Decorator
**What:** Wraps an async view method to cache its response using Django's cache backend.
**When to use:** Read-heavy endpoints where results can be safely cached for a configurable TTL.
**Example:**
```python
# Source: existing CacheManager pattern in utils/performance.py
import functools
import hashlib
from django.core.cache import cache as django_cache

def cache_response(timeout: int = 300, key_prefix: str = "matt_view"):
    """Cache view method response for `timeout` seconds."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, request, *args, **kwargs):
            # Build cache key from prefix + path + query string
            cache_key = f"{key_prefix}:{request.path}:{request.GET.urlencode()}"
            cache_key = hashlib.md5(cache_key.encode()).hexdigest()
            cached = django_cache.get(cache_key)
            if cached is not None:
                return cached
            result = await func(self, request, *args, **kwargs)
            django_cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator
```

### Pattern 6: Streaming Memory Test
**What:** Serialize 10k+ records via `StreamingHttpResponse`, consume the stream, assert peak memory below threshold.
**When to use:** Verifying that streaming serialization doesn't buffer entire dataset in memory.
**Example:**
```python
import tracemalloc
from django_matt.utils.performance import stream_json_list

def test_streaming_memory_below_threshold():
    records = [{"id": i, "name": f"item {i}"} for i in range(10_000)]
    tracemalloc.start()
    response = stream_json_list(records)
    content = b"".join(response.streaming_content)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak / 1024 / 1024
    # Threshold: peak should be < 50MB for 10k simple records
    # (actual threshold is Claude's discretion per CONTEXT.md)
    assert peak_mb < 50, f"Peak memory {peak_mb:.1f}MB exceeded threshold"
```

### Anti-Patterns to Avoid
- **Running HTTP load tests (wrk/hey) in pytest CI**: wrk/hey require a live server; keep HTTP load testing in the Makefile as a manual step, not in `pytest tests/`. CI tests use in-process only.
- **Mocking the comparison frameworks**: `bench_comparison.py` currently simulates DRF and FastAPI behavior rather than importing and running them. Use actual installed packages for the comparison scenario so results reflect real behavior.
- **Global mutation of settings.MIDDLEWARE at import time**: Do it in `AppConfig.ready()` only, not at module level. Module-level mutation runs during `manage.py collectstatic` and other non-server commands.
- **Calling `connection.queries` directly**: Use `CaptureQueriesContext` — it handles `DEBUG=True` requirement and thread safety correctly.
- **Per-request `get_type_hints()` calls**: Already prevented in `core/router.py` via `_hints_cache`. The DI container (`di/depends.py`, `di/container.py`) calls `get_type_hints` during wire-up, not per-request — verify by checking call sites are in `__init__` or `_setup_methods`, not in handlers.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query counting | Custom SQL logging hooks | `django.test.utils.CaptureQueriesContext` | Thread-safe, handles `DEBUG=True`, exact Django behavior |
| Memory profiling | Custom allocator hooks | `tracemalloc` (stdlib) | No install needed, tracks Python allocations accurately |
| Function call profiling | Custom `sys.settrace` | `cProfile` + `pstats` (stdlib) | Standard, deterministic, no overhead in production |
| Rich terminal tables | ANSI escape codes in `ConsoleReporter` | `rich.table.Table` | Already a base dependency; consistent with `cli/console.py` |
| Cache key generation | Custom hash schemes | `hashlib.md5(key.encode()).hexdigest()` | Simple, deterministic, collision-resistant for cache keys |
| Middleware introspection | Parsing MIDDLEWARE list manually | `django.utils.module_loading.import_string` | Handles dotted paths correctly |

**Key insight:** Django's `CaptureQueriesContext` is the canonical way to count queries in tests — it's what `assertNumQueries` uses internally. Do not replicate it; just call it.

---

## Common Pitfalls

### Pitfall 1: MIDDLEWARE Mutation Timing
**What goes wrong:** Modifying `settings.MIDDLEWARE` in a module-level import rather than `AppConfig.ready()` causes the mutation to run during migrations, test collection, management commands, and `collectstatic` — not just server startup.
**Why it happens:** Django loads app code at import time during `django.setup()`.
**How to avoid:** Place the `apply_api_mode()` call inside `DjangoMattAppConfig.ready()`. Guard with `if getattr(settings, 'MATT_API_MODE', False):`.
**Warning signs:** `manage.py migrate` output shows "MATT_API_MODE: stripped..." — middleware strip is running during migrations.

### Pitfall 2: cProfile Test Flakiness on First Request
**What goes wrong:** The first request after app startup may still trigger `get_type_hints()` during lazy initialization. Asserting zero calls on request #1 fails.
**Why it happens:** Some code paths cache on first use (e.g., `_hints_cache` populates on first call per endpoint, not before). The test must first "warm up" the app with a request to trigger all lazy caching, then measure subsequent requests.
**How to avoid:** Run N warmup requests before enabling the cProfile profiler. The `Benchmark.run()` class already has `warmup_iterations` — use it.
**Warning signs:** Test passes locally (warm app) but fails in CI (cold start).

### Pitfall 3: in-process vs HTTP Benchmark Gap
**What goes wrong:** In-process timing shows 50K ops/s, but actual HTTP load test shows 8K req/s. Reporting both as "50K ops/s" is misleading.
**Why it happens:** HTTP benchmarks include TCP, Django's WSGI/ASGI overhead, connection handling — all absent from in-process timing.
**How to avoid:** Label outputs clearly: "in-process ops/s (framework overhead only)" vs "HTTP req/s (full stack)". The CONTEXT.md decision to run both is correct — just label them separately in the rich table.
**Warning signs:** Framework comparison table shows only one metric column labeled ambiguously as "performance".

### Pitfall 4: SQLite vs PostgreSQL Benchmark Gap
**What goes wrong:** SQLite in-memory benchmarks show 3x better query performance than PostgreSQL, making django-matt look faster than it is in production.
**Why it happens:** SQLite in-memory has near-zero I/O cost; PostgreSQL has network round-trips even on localhost.
**How to avoid:** The CONTEXT.md decision to use SQLite as default with `--db postgres` flag is correct. Always label results with the database engine. Never compare SQLite results to PostgreSQL results.
**Warning signs:** Benchmark output lacks a "database: SQLite in-memory" line in the environment section.

### Pitfall 5: DRF/ninja Not Installed When Running `make benchmark`
**What goes wrong:** `make benchmark` silently skips the comparison frameworks and shows only django-matt numbers, making it look like comparison was done.
**Why it happens:** `bench_comparison.py` uses `try/except ImportError` to skip missing frameworks.
**How to avoid:** In the Makefile `benchmark` target, check for presence of comparison packages and print a clear warning if missing. In the `FrameworkComparisonScenario`, mark skipped frameworks as `[NOT INSTALLED]` in the rich table rather than omitting the row.
**Warning signs:** Rich table has only 1-2 framework rows when running `make benchmark` on a fresh install.

### Pitfall 6: assert_query_count Requires DEBUG=True
**What goes wrong:** `CaptureQueriesContext` only captures queries when `django.db.connection.queries` is populated, which requires `DEBUG=True` or explicit `settings.DEBUG=True` override.
**Why it happens:** Django only logs queries to `connection.queries` in debug mode.
**How to avoid:** In `assert_query_count`, use `@override_settings(DEBUG=True)` around the context, or document that test settings must have `DEBUG=True`. Check `tests/settings.py` — it likely already has `DEBUG=True`.
**Warning signs:** `assert_query_count` always reports 0 queries regardless of what the code does.

---

## Code Examples

Verified patterns from project source:

### optimize_queryset (already implemented, needs N+1 test)
```python
# Source: django_matt/views/base.py:182-208
def optimize_queryset(self, queryset: models.QuerySet) -> models.QuerySet:
    """Auto-apply select_related/prefetch_related based on response schema."""
    schema = self.get_response_schema()
    if schema is None:
        return queryset

    model = queryset.model
    meta = model._meta
    select_fields = []
    prefetch_fields = []

    for field_name in schema.model_fields:
        try:
            field = meta.get_field(field_name)
        except Exception:
            continue
        if isinstance(field, (models.ForeignKey, models.OneToOneField)):
            select_fields.append(field_name)
        elif isinstance(field, models.ManyToManyField):
            prefetch_fields.append(field_name)

    if select_fields:
        queryset = queryset.select_related(*select_fields)
    if prefetch_fields:
        queryset = queryset.prefetch_related(*prefetch_fields)
    return queryset
```

### from_orm_fast (already implemented, needs list path audit)
```python
# Source: django_matt/core/schema.py:287-304
@classmethod
def from_orm_fast(cls, obj: models.Model) -> "ModelSchema":
    """Create a schema instance without re-validation (model_construct)."""
    return cls.model_construct(**cls._extract_data(obj))

@classmethod
def from_queryset_fast(cls, queryset) -> list["ModelSchema"]:
    return [cls.from_orm_fast(obj) for obj in queryset]

@classmethod
async def afrom_queryset_fast(cls, queryset) -> list["ModelSchema"]:
    return [cls.from_orm_fast(obj) async for obj in queryset]
```

### get_type_hints caching (already implemented in router)
```python
# Source: django_matt/core/router.py:64-75
_hints_cache: dict[int, dict] = {}

def _get_endpoint_hints(endpoint):
    """
    Results are cached per-function to avoid repeated get_type_hints() calls.
    """
    key = id(endpoint)
    if key not in _hints_cache:
        try:
            _hints_cache[key] = get_type_hints(endpoint)
        except Exception:
            _hints_cache[key] = {}
    return _hints_cache[key]
```

### BenchmarkResult dataclass (use for FrameworkComparisonScenario)
```python
# Source: django_matt/benchmarks/runner.py:23-55
@dataclass
class BenchmarkResult:
    name: str
    scenario: str
    iterations: int
    total_time_ms: float
    mean_time_ms: float
    median_time_ms: float
    min_time_ms: float
    max_time_ms: float
    std_dev_ms: float
    ops_per_second: float
    memory_mb: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Rich table pattern (from cli/console.py:174)
```python
# Source: django_matt/cli/console.py
from rich.table import Table
from rich.console import Console

table = Table(title="Benchmark Results", show_header=True, header_style="bold cyan")
table.add_column("Framework", style="bold", min_width=15)
table.add_column("List ops/s", justify="right", min_width=12)
table.add_column("Create ops/s", justify="right", min_width=12)
table.add_column("Median (ms)", justify="right", min_width=12)
table.add_column("vs DRF", justify="right", min_width=10)
```

### CaptureQueriesContext pattern
```python
# Source: Django source — django.test.utils.CaptureQueriesContext
from django.test.utils import CaptureQueriesContext
from django.db import connection

with CaptureQueriesContext(connection) as ctx:
    list(queryset)  # execute queries
actual_count = len(ctx.captured_queries)
```

---

## What Already Exists vs What Needs to Be Built

This section is critical for planning — most of Phase 2 is extension, not greenfield.

| Feature | Status | Location | Gap |
|---------|--------|----------|-----|
| `model_construct()` fast path | EXISTS | `core/schema.py::from_orm_fast()` | Need test verifying it's on all list paths |
| `optimize_queryset()` | EXISTS | `views/base.py:182`, `views/list.py:163` | Need N+1 test using `assert_query_count` |
| orjson everywhere | EXISTS | base dep, used in controller/router/views | Need audit for remaining `json.dumps` in hot paths |
| Type hints caching | EXISTS | `core/router.py::_hints_cache` | Controller calls `get_type_hints` in `_setup_methods` (init-time, correct) — need CI cProfile test to guard |
| `StreamingJsonResponse` | EXISTS | `utils/performance.py` | Need memory threshold test |
| `CacheManager` | EXISTS | `utils/performance.py` | Need `@cache_response` decorator |
| `BenchmarkRunner` / `BenchmarkScenario` | EXISTS | `django_matt/benchmarks/` | Need `FrameworkComparisonScenario` class |
| `ConsoleReporter` | EXISTS | `django_matt/benchmarks/reporters.py` | Need `RichTableReporter` using `rich.table.Table` |
| `make benchmark` target | EXISTS (partial) | `Makefile:662` | Currently points to `benchmarks/run_all.py` — needs to run `FrameworkComparisonScenario` and output rich table |
| `assert_query_count` | MISSING | `testing/assertions.py` | Add context manager + decorator |
| `MATT_API_MODE` | MISSING | `config/components/performance.py` | Add setting + `AppConfig.ready()` hook |
| `@cache_response` | MISSING | `utils/performance.py` | Add decorator |
| `FrameworkComparisonScenario` | MISSING | `django_matt/benchmarks/comparison.py` | New file |
| `RichTableReporter` | MISSING | `django_matt/benchmarks/reporters.py` | Add to existing file |
| cProfile hot-path test | MISSING | `tests/test_performance.py` | Add test function |
| Streaming memory test | MISSING | `tests/test_performance.py` | Add test function |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `json.dumps` in Django views | `orjson.dumps` | orjson >=3.0, 2020+ | 2-5x faster serialization; bytes output |
| `model.from_orm()` for list serialization | `model_construct()` skipping re-validation | Pydantic v2, 2023 | Skips all validators; safe for trusted ORM data |
| `type(hint)` per-request introspection | `get_type_hints()` cached at registration | Framework architecture | Eliminates startup-to-steady-state latency cliff |
| Full middleware stack in API apps | Stripped API-mode middleware | API-first frameworks (2022+) | Removes 4-6 unnecessary middleware per request |
| Custom query counting hacks | `CaptureQueriesContext` | Django >=1.11 | Thread-safe, accurate, no monkey-patching |
| `traceback.print_stats()` | `cProfile` + `pstats` | Always | Deterministic, low overhead |

**Deprecated/outdated in this codebase:**
- `benchmarks/bench_comparison.py` "simulates" DRF/FastAPI by calling Pydantic directly — this is a proxy, not a real framework comparison. Phase 2 replaces this with actual installed framework comparison.
- `ConsoleReporter` uses raw ANSI escape codes — `RichTableReporter` using the base-dep `rich` library is the correct approach going forward.

---

## Open Questions

1. **DRF/ninja availability during CI**
   - What we know: These are not currently in `pyproject.toml` as any dependency group.
   - What's unclear: Should the `make benchmark` target fail or warn-and-skip when DRF/ninja are not installed?
   - Recommendation: Warn-and-skip with clear "[NOT INSTALLED — run `uv add --dev djangorestframework django-ninja fastapi` to enable comparison]" message. The CI `pytest` suite should never require these — they're local developer tooling.

2. **HTTP load tester (wrk vs hey)**
   - What we know: Both are mature CLI tools; hey is a single Go binary, wrk requires C compilation. The CONTEXT.md says this is Claude's discretion.
   - What's unclear: Either can be run from the Makefile but neither should be in the pytest suite.
   - Recommendation: Use `hey` — it's a single binary (`brew install hey`), cross-platform, outputs req/s and latency percentiles in a parseable format. Add a `make benchmark-http` target (separate from `make benchmark` which is in-process only).

3. **Controller `get_type_hints` timing**
   - What we know: `core/controller.py::_setup_methods()` calls `get_type_hints(method)` at `__init__` time (line 112), not per-request. This is correct behavior.
   - What's unclear: The DI container (`di/depends.py:116`, `di/depends.py:173`, `di/container.py:292`) calls `get_type_hints` during wire-up. If DI is request-scoped (via `ContextVar`), is `get_type_hints` called per-request?
   - Recommendation: Audit `di/depends.py` and `di/container.py` to confirm `get_type_hints` is only called during container setup (at Django startup), not during request handling. The cProfile CI test will catch any regression.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-django |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_performance.py tests/test_benchmarks.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-08 | `model_construct()` used on all list serialization ORM-read paths | unit | `uv run pytest tests/test_views.py -k test_list_uses_model_construct -x` | ❌ Wave 0 |
| CORE-09 | Zero `get_type_hints()` calls after app startup in hot path | unit | `uv run pytest tests/test_performance.py -k test_no_get_type_hints_per_request -x` | ❌ Wave 0 |
| CORE-10 | orjson used in all JSON paths, no stdlib `json.dumps` in hot paths | unit | `uv run pytest tests/test_performance.py -k test_orjson_used_everywhere -x` | ❌ Wave 0 |
| CORE-12 | `MATT_API_MODE=True` strips CSRF/Sessions/Messages/Clickjacking | unit | `uv run pytest tests/test_performance.py -k test_api_mode_strips_middleware -x` | ❌ Wave 0 |
| PERF-04 | N+1 introduced: `assert_query_count` fails; with optimize_queryset: passes | unit | `uv run pytest tests/test_views.py -k test_optimize_queryset_prevents_n_plus_1 -x` | ❌ Wave 0 |
| PERF-05 | 10k+ records via StreamingHttpResponse stays below memory threshold | unit | `uv run pytest tests/test_performance.py -k test_streaming_memory_threshold -x` | ✅ (file exists, test missing) |
| PERF-06 | `@cache_response` caches response on second call | unit | `uv run pytest tests/test_performance.py -k test_cache_response_decorator -x` | ✅ (file exists, test missing) |
| PERF-07 | `make benchmark` produces rich table with django-matt, DRF, ninja, FastAPI rows | manual | `make benchmark` | ❌ Wave 0 |
| PERF-08 | `assert_query_count` context manager and decorator both work | unit | `uv run pytest tests/test_performance.py -k test_assert_query_count -x` | ✅ (file exists, test missing) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_performance.py tests/test_benchmarks.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_performance.py` — new test functions for: `test_no_get_type_hints_per_request`, `test_api_mode_strips_middleware`, `test_streaming_memory_threshold`, `test_cache_response_decorator`, `test_assert_query_count`, `test_orjson_used_everywhere`
- [ ] `tests/test_views.py` — new test functions: `test_list_uses_model_construct`, `test_optimize_queryset_prevents_n_plus_1`
- [ ] `django_matt/benchmarks/comparison.py` — new file: `FrameworkComparisonScenario`
- [ ] `django_matt/testing/assertions.py` — extend: `assert_query_count` class
- [ ] `django_matt/utils/performance.py` — extend: `@cache_response` decorator
- [ ] `config/components/performance.py` — extend: `MATT_API_MODE` + `apply_api_mode()` + AppConfig integration

*(PERF-07 is manual-only — benchmark output requires human visual inspection of the rich table)*

---

## Sources

### Primary (HIGH confidence)
- Django source `django.test.utils.CaptureQueriesContext` — verified by reading Django internals and CONTEXT.md reference to `assertNumQueries` pattern
- `django_matt/views/base.py:182-208` — `optimize_queryset()` implementation confirmed by direct read
- `django_matt/core/schema.py:287-304` — `from_orm_fast()` and `model_construct()` usage confirmed by direct read
- `django_matt/core/router.py:64-75` — `_hints_cache` per-function caching confirmed by direct read
- `django_matt/utils/performance.py` — `StreamingJsonResponse`, `CacheManager`, `stream_json_list` confirmed by direct read
- `django_matt/benchmarks/runner.py` — `BenchmarkResult`, `BenchmarkRunner`, `BENCHMARK_STORAGE_DIR` confirmed by direct read
- `django_matt/testing/assertions.py` — existing assertions confirmed; `assert_query_count` absence confirmed by direct read
- `pyproject.toml` — `rich>=13.0.0` confirmed as base dependency; DRF/ninja/FastAPI confirmed absent from all dep groups
- `django_matt/cli/console.py:33-39` — `rich.table.Table` usage pattern confirmed by direct read

### Secondary (MEDIUM confidence)
- Python stdlib `cProfile` + `pstats` + `tracemalloc` — standard library, no version dependency, stable API
- `rich.table.Table` API — rich is a base dependency and the project already uses it; Table API is stable since rich 10.x

### Tertiary (LOW confidence — not needed, known facts from project source)
- HTTP load tester comparison (wrk vs hey) — based on general ecosystem knowledge; hey recommended for simplicity

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core tools are already base deps; comparison framework availability is the only uncertainty
- Architecture: HIGH — all extension points identified from direct source code reading; no speculative design
- Pitfalls: HIGH — derived from direct reading of existing code patterns and decision constraints in CONTEXT.md

**Research date:** 2026-03-07
**Valid until:** 2026-06-07 (stable domain — Django, rich, cProfile APIs are very stable)

# Memory Profiling

## What It Is

Memory profiling verifies that django-matt's Rust extensions don't leak memory when called millions of times from a long-running Python process. This is a production safety net — a slow memory leak that grows 1MB per 100K requests will eventually OOM a server after a few hours of traffic.

## Why It Matters

Every Rust function crosses the PyO3 FFI boundary. On each call, Rust creates Python objects (dicts, strings, bytes, lists) and returns them to Python's garbage collector. If PyO3 reference counting is wrong — a `Py<PyDict>` held after it should be freed, a buffer `Vec<u8>` not dropped after conversion to `PyBytes` — those objects accumulate and never get freed.

This is different from a Python memory leak. Python's garbage collector handles cycles between Python objects. But objects allocated on the Rust side live outside Python's cycle detector — they rely on correct reference counting at the FFI boundary.

### What Could Go Wrong

| Component | Allocation per Call | Risk |
|-----------|-------------------|------|
| `RadixRouter.match_route` | 1 `PyDict` (url params) | Dict not freed if PyO3 ref is held |
| `jwt_encode` | 1 `PyString` (token) | Minimal — simple return |
| `jwt_decode` | 1 `PyDict` (payload) + internal `orjson.loads()` | Two allocations, internal Python call |
| `jwt_verify` | 1 `bool` | Negligible — no heap allocation |
| `parse_query_string` | 5 `PyDict`s + `PyList`s (fields, filters, sort, pagination, extras) | Highest allocation count per call |
| `parse_headers` | 2-4 `PyDict`s (authorization, content_type, accept, result) | Nested dict creation |
| `serialize_dicts_to_json` | 1 `PyBytes` (JSON output) | Buffer Vec must be freed after conversion |
| `build_camel_case_map` | 1 `PyDict` (alias map) | Typically called once at startup |

## How We Test

The approach is straightforward: call each function 1,000,000 times and watch if RSS (Resident Set Size) grows.

```
                RSS (MB)
                  ^
Leak:             |          ____________________
                  |      ___/
                  |  ___/
                  | /
                  +-----------------------------------> iterations

No leak:          |
                  |  ____________________________________
                  | /
                  +-----------------------------------> iterations
```

### Methodology

1. **Force GC** before starting to establish a clean baseline
2. **Run in batches** of 100K iterations (10 batches = 1M total)
3. **Force GC between batches** to give Python every opportunity to free objects
4. **Measure RSS** via `resource.getrusage()` — captures both Python and native allocations
5. **Compare peak RSS growth** against threshold (10MB)

We use `resource.getrusage()` instead of `tracemalloc` because `tracemalloc` only tracks Python-side allocations. A Rust-side leak (e.g., a `Vec` that grows but never shrinks) would be invisible to `tracemalloc` but visible in RSS.

### Running

```bash
# Run memory profiling
make rust-mem

# Or directly
uv run python benchmarks/bench_memory.py
```

### Output

```
  Function                       Base         Final        Growth       Peak         Status
  ----------------------------------------------------------------------------------------
     RadixRouter.match_route        base=13.7MB  final=13.9MB  growth=+0.17MB  peak=+0.17MB  [PASS]
     jwt_encode                     base=13.9MB  final=14.3MB  growth=+0.48MB  peak=+0.48MB  [PASS]
     jwt_decode                     base=14.3MB  final=14.6MB  growth=+0.30MB  peak=+0.30MB  [PASS]
     jwt_verify                     base=14.6MB  final=14.6MB  growth=+0.00MB  peak=+0.00MB  [PASS]
     parse_query_string             base=14.6MB  final=14.7MB  growth=+0.02MB  peak=+0.02MB  [PASS]
     parse_headers                  base=14.7MB  final=14.7MB  growth=+0.00MB  peak=+0.00MB  [PASS]
     serialize_dicts_to_json        base=14.7MB  final=14.7MB  growth=+0.03MB  peak=+0.03MB  [PASS]
     serialize_dicts + camelCase    base=14.7MB  final=14.7MB  growth=+0.05MB  peak=+0.05MB  [PASS]
     serialize_dict_to_json         base=14.7MB  final=14.7MB  growth=+0.00MB  peak=+0.00MB  [PASS]
     build_camel_case_map           base=14.7MB  final=14.7MB  growth=+0.00MB  peak=+0.00MB  [PASS]
     Full lifecycle (combined)      base=14.7MB  final=14.9MB  growth=+0.12MB  peak=+0.12MB  [PASS]
```

All growth values are under 0.5MB across 1M iterations — well within normal Python allocator noise.

## Why These Numbers Are Safe

The small RSS growth (0.1-0.5MB) across 1M calls is expected Python allocator behavior:

- **Python's memory allocator** (`pymalloc`) requests memory from the OS in arenas (256KB blocks). Once allocated, arenas are rarely returned to the OS even after objects are freed — they're reused for future allocations.
- **GC overhead** — Python's cycle detector maintains internal data structures that grow slightly as more objects are tracked.
- **No linear growth** — a real leak would show RSS growing proportionally to iteration count. Our numbers plateau after the first batch.

A real leak at this scale would look like 100-500MB of growth over 1M iterations (each call leaking a dict = ~200 bytes × 1M = 200MB).

## When to Re-Run

Re-run memory profiling after:

- Adding a new Rust function that returns Python objects
- Changing how an existing Rust function creates or returns Python objects
- Upgrading PyO3 version (ref-counting semantics can change)
- Changing `Bound<'py, ...>` lifetimes in Rust code

## Future Enhancements

### memray Integration

[memray](https://github.com/bloomberg/memray) can track native (C/Rust) allocations when compiled with debug symbols. This would give per-allocation-site tracking rather than just RSS deltas:

```bash
# Build Rust extensions with debug symbols
cd rust && RUSTFLAGS="-C debuginfo=2" maturin develop

# Run under memray
memray run benchmarks/bench_memory.py
memray flamegraph memray-*.bin
```

This would show exactly which Rust function and line number is allocating, making it trivial to identify leaks if they ever occur.

### Sustained Load Testing

The current test runs 1M iterations sequentially. A more realistic test would:

- Run across multiple threads (simulating ASGI workers)
- Run for extended duration (hours, not seconds)
- Monitor RSS via an external process (not self-reporting)

This could be built as a CI job that runs nightly against a development server.

### Valgrind / LeakSanitizer

For the most thorough leak detection, the Rust code can be compiled with AddressSanitizer:

```bash
RUSTFLAGS="-Z sanitizer=address" cargo +nightly build
```

This catches leaks at the allocator level but requires running without Python (using the fuzz targets or standalone test harness).

"""Memory profiling for Rust extensions.

Verifies that Rust FFI functions don't leak memory when called millions
of times — simulating a long-running ASGI server handling sustained traffic.

Each Rust function crosses the PyO3 boundary, creating Python objects
(dicts, strings, bytes, lists) on the Rust side. If reference counting
is wrong, those objects never get freed and RSS grows linearly.

This script:
  1. Runs each Rust function 1M times in batches of 100K
  2. Records RSS (resident set size) after each batch
  3. Reports RSS growth per function
  4. Flags any function whose RSS grows > threshold across all batches

Run with: uv run python benchmarks/bench_memory.py
"""

import gc
import resource
import sys
import time


def get_rss_mb() -> float:
    """Get current RSS in MB (macOS returns bytes, Linux returns KB)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = usage.ru_maxrss
    if sys.platform == "darwin":
        return rss / (1024 * 1024)  # bytes → MB
    return rss / 1024  # KB → MB


def run_memory_test(
    name: str,
    func,
    total_iterations: int = 1_000_000,
    batch_size: int = 100_000,
    rss_threshold_mb: float = 10.0,
) -> dict:
    """Run a function many times and track RSS growth.

    Returns a dict with RSS measurements and pass/fail status.
    """
    gc.collect()
    gc.collect()

    batches = total_iterations // batch_size
    rss_readings = []

    # Baseline RSS
    rss_readings.append(get_rss_mb())

    for batch in range(batches):
        for _ in range(batch_size):
            func()

        # Force GC between batches to give Python every chance to free
        gc.collect()
        gc.collect()
        rss_readings.append(get_rss_mb())

    baseline = rss_readings[0]
    final = rss_readings[-1]
    growth = final - baseline
    peak = max(rss_readings)
    peak_growth = peak - baseline

    passed = peak_growth < rss_threshold_mb

    return {
        "name": name,
        "total_iterations": total_iterations,
        "baseline_mb": baseline,
        "final_mb": final,
        "peak_mb": peak,
        "growth_mb": growth,
        "peak_growth_mb": peak_growth,
        "rss_readings": rss_readings,
        "passed": passed,
        "threshold_mb": rss_threshold_mb,
    }


def print_result(result: dict) -> None:
    """Print a single test result."""
    status = "PASS" if result["passed"] else "FAIL"
    marker = "  " if result["passed"] else ">>"

    print(f"  {marker} {result['name']:<30} ", end="")
    print(f"base={result['baseline_mb']:.1f}MB  ", end="")
    print(f"final={result['final_mb']:.1f}MB  ", end="")
    print(f"growth={result['growth_mb']:+.2f}MB  ", end="")
    print(f"peak={result['peak_growth_mb']:+.2f}MB  ", end="")
    print(f"[{status}]")

    # Show per-batch RSS if there's notable growth
    if result["peak_growth_mb"] > 1.0:
        readings = result["rss_readings"]
        baseline = readings[0]
        deltas = [f"{r - baseline:+.1f}" for r in readings[1:]]
        print(f"       RSS deltas per batch: {', '.join(deltas)} MB")


def main():
    try:
        from django_matt._rust import (
            RadixRouter,
            build_camel_case_map,
            jwt_decode,
            jwt_encode,
            jwt_verify,
            parse_headers,
            parse_query_string,
            serialize_dict_to_json,
            serialize_dicts_to_json,
        )
    except ImportError:
        print("ERROR: Rust extensions not installed. Run `make rust-dev` first.")
        sys.exit(1)

    import orjson

    print("=" * 75)
    print("  Memory Profiling — Rust Extension FFI Leak Detection")
    print("=" * 75)
    print()
    print(f"  Python {sys.version.split()[0]} | {sys.platform}")
    print(f"  Iterations per test: 1,000,000 (10 batches of 100,000)")
    print(f"  Threshold: RSS growth < 10 MB")
    print()

    # ---- Setup test data ----

    secret = b"memory-test-secret-key-32-bytes!"
    jwt_payload = orjson.dumps(
        {"sub": "user123", "role": "admin", "iat": int(time.time()),
         "exp": int(time.time()) + 3600},
        option=orjson.OPT_SORT_KEYS,
    )
    test_token = jwt_encode(jwt_payload, secret, "HS256")

    route_defs = [
        ("GET", "/users", "list_users"),
        ("GET", "/users/{id}", "user_detail"),
        ("GET", "/users/{user_id}/posts/{post_id}", "user_post_detail"),
        ("GET", "/products/{id}/reviews", "product_reviews"),
        ("POST", "/orders", "create_order"),
    ]
    router = RadixRouter()
    for method, pattern, eid in route_defs:
        router.add_route(method, pattern, eid)

    meta = {
        "HTTP_AUTHORIZATION": f"Bearer {test_token}",
        "HTTP_ACCEPT": "application/json;q=1.0, text/html;q=0.5, */*;q=0.1",
        "CONTENT_TYPE": "application/json; charset=utf-8",
        "HTTP_X_REQUEST_ID": "req-abc-123-def-456",
        "HTTP_X_API_KEY": "sk_live_test1234567890",
    }

    query_string = (
        "fields=id,name,email,created_at"
        "&filter[status]=active&filter[role]=admin"
        "&sort=-created_at,name"
        "&page=3&limit=25"
    )

    test_dicts = [
        {"id": i, "first_name": f"User{i}", "last_name": f"Smith{i}",
         "email": f"user{i}@example.com", "is_active": True, "score": i * 1.5}
        for i in range(10)
    ]
    single_dict = test_dicts[0]
    field_names = list(single_dict.keys())
    alias_map = build_camel_case_map(field_names)

    # ---- Run tests ----

    results = []

    # 1. RadixRouter.match_route — creates PyDict of params per call
    results.append(run_memory_test(
        "RadixRouter.match_route",
        lambda: router.match_route("GET", "/users/42"),
    ))

    # 2. jwt_encode — creates a String, returned as PyString
    results.append(run_memory_test(
        "jwt_encode",
        lambda: jwt_encode(jwt_payload, secret, "HS256"),
    ))

    # 3. jwt_decode — creates PyDict via orjson.loads internally
    results.append(run_memory_test(
        "jwt_decode",
        lambda: jwt_decode(test_token, secret, "HS256", False, 0),
    ))

    # 4. jwt_verify — returns bool, minimal allocation
    results.append(run_memory_test(
        "jwt_verify",
        lambda: jwt_verify(test_token, secret, "HS256"),
    ))

    # 5. parse_query_string — creates 5 PyDicts + PyLists
    results.append(run_memory_test(
        "parse_query_string",
        lambda: parse_query_string(query_string),
    ))

    # 6. parse_headers — creates nested PyDicts
    results.append(run_memory_test(
        "parse_headers",
        lambda: parse_headers(meta),
    ))

    # 7. serialize_dicts_to_json — creates PyBytes
    results.append(run_memory_test(
        "serialize_dicts_to_json",
        lambda: serialize_dicts_to_json(test_dicts),
    ))

    # 8. serialize_dicts_to_json + alias — creates PyBytes with rename
    results.append(run_memory_test(
        "serialize_dicts + camelCase",
        lambda: serialize_dicts_to_json(test_dicts, alias_map),
    ))

    # 9. serialize_dict_to_json — single dict
    results.append(run_memory_test(
        "serialize_dict_to_json",
        lambda: serialize_dict_to_json(single_dict),
    ))

    # 10. build_camel_case_map — creates PyDict
    results.append(run_memory_test(
        "build_camel_case_map",
        lambda: build_camel_case_map(field_names),
    ))

    # 11. Combined lifecycle — all components in sequence
    def lifecycle():
        router.match_route("GET", "/users/42")
        parse_headers(meta)
        jwt_decode(test_token, secret, "HS256", False, 0)
        parse_query_string(query_string)
        serialize_dicts_to_json(test_dicts, alias_map)

    results.append(run_memory_test(
        "Full lifecycle (combined)",
        lifecycle,
    ))

    # ---- Print results ----

    print(f"  {'Function':<30} {'Base':<12} {'Final':<12} {'Growth':<12} {'Peak':<12} {'Status'}")
    print(f"  {'-' * 88}")

    for r in results:
        print_result(r)

    print()

    # ---- Summary ----
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])

    if failed == 0:
        print(f"  All {passed} tests PASSED — no memory leaks detected.")
        print(f"  RSS remained stable across 1M+ iterations per function.")
    else:
        print(f"  {failed} test(s) FAILED — potential memory leak detected!")
        for r in results:
            if not r["passed"]:
                print(f"    - {r['name']}: grew {r['peak_growth_mb']:.1f}MB (threshold: {r['threshold_mb']:.0f}MB)")

    print()
    print("=" * 75)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

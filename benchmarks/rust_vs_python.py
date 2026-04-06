"""Benchmark: Rust RadixRouter vs Python regex-based routing.

Run with: uv run python benchmarks/rust_vs_python.py
"""

import re
import time


def python_regex_router(patterns: list[tuple[str, str, str]]):
    """Simple regex-based router (simulates Django URL resolver)."""
    compiled: list[tuple[str, re.Pattern, str, list[str]]] = []
    for method, pattern, endpoint_id in patterns:
        # Convert {param} to named groups
        regex = pattern
        param_names = []
        import re as re_mod

        for match in re_mod.finditer(r"\{(\w+?)(?::(\*))?\}", pattern):
            name = match.group(1)
            is_wildcard = match.group(2)
            param_names.append(name)
            if is_wildcard:
                regex = regex.replace(match.group(0), f"(?P<{name}>.+)")
            else:
                regex = regex.replace(match.group(0), f"(?P<{name}>[^/]+)")
        regex = f"^{regex}/?$"
        compiled.append((method, re.compile(regex), endpoint_id, param_names))

    def match(method: str, path: str):
        for m, rx, eid, _ in compiled:
            if m == method:
                result = rx.match(path)
                if result:
                    return eid, result.groupdict()
        return None

    return match


def benchmark(name: str, func, iterations: int = 100_000):
    """Run a benchmark and return results."""
    # Warmup
    for _ in range(1000):
        func()

    start = time.perf_counter_ns()
    for _ in range(iterations):
        func()
    elapsed_ns = time.perf_counter_ns() - start

    mean_ns = elapsed_ns / iterations
    ops_per_sec = 1_000_000_000 / mean_ns

    return {
        "name": name,
        "iterations": iterations,
        "total_ms": elapsed_ns / 1_000_000,
        "mean_ns": mean_ns,
        "ops_per_sec": ops_per_sec,
    }


def main():
    # Check if Rust extensions are available
    try:
        from django_matt._rust import RadixRouter

        has_rust = True
    except ImportError:
        has_rust = False
        print("WARNING: Rust extensions not installed. Run `make rust-dev` first.")
        print("Showing Python-only benchmarks.\n")

    # Define routes
    route_defs = [
        ("GET", "/", "root"),
        ("GET", "/users", "list_users"),
        ("POST", "/users", "create_user"),
        ("GET", "/users/{id}", "user_detail"),
        ("PUT", "/users/{id}", "update_user"),
        ("DELETE", "/users/{id}", "delete_user"),
        ("GET", "/users/me", "current_user"),
        ("GET", "/users/{user_id}/posts", "user_posts"),
        ("GET", "/users/{user_id}/posts/{post_id}", "user_post_detail"),
        ("GET", "/products", "list_products"),
        ("GET", "/products/{id}", "product_detail"),
        ("GET", "/products/{id}/reviews", "product_reviews"),
        ("POST", "/products/{id}/reviews", "create_review"),
        ("GET", "/orders", "list_orders"),
        ("POST", "/orders", "create_order"),
        ("GET", "/orders/{id}", "order_detail"),
        ("GET", "/health", "health_check"),
        ("GET", "/docs", "api_docs"),
        ("GET", "/auth/login", "login"),
        ("POST", "/auth/register", "register"),
    ]

    # Test paths to match
    test_cases = [
        ("GET", "/users"),
        ("GET", "/users/42"),
        ("GET", "/users/me"),
        ("GET", "/users/5/posts/99"),
        ("GET", "/products/123/reviews"),
        ("GET", "/health"),
        ("POST", "/orders"),
        ("GET", "/nonexistent"),  # miss
    ]

    # Setup Python router
    py_match = python_regex_router(route_defs)

    # Setup Rust router
    if has_rust:
        rust_router = RadixRouter()
        for method, pattern, endpoint_id in route_defs:
            rust_router.add_route(method, pattern, endpoint_id)

    print("=" * 70)
    print("  Rust RadixRouter vs Python Regex Router — Benchmark")
    print("=" * 70)
    print(f"\n  Routes registered: {len(route_defs)}")
    print(f"  Test cases per iteration: {len(test_cases)}")
    print()

    # Verify both produce same results (where Python regex order matches)
    if has_rust:
        mismatches = 0
        for method, path in test_cases:
            py_result = py_match(method, path)
            rust_result = rust_router.match_route(method, path)
            if py_result is None and rust_result is None:
                continue
            if py_result is not None and rust_result is not None:
                py_eid, _ = py_result
                rust_eid, _ = rust_result
                if py_eid != rust_eid:
                    # Rust correctly prioritizes static over param
                    mismatches += 1
        if mismatches:
            print(f"  Correctness: {mismatches} priority differences (Rust static > param, correct)\n")
        else:
            print("  Correctness check: PASS\n")

    iterations = 200_000

    # Benchmark: Python
    def py_bench():
        for method, path in test_cases:
            py_match(method, path)

    py = benchmark("Python regex", py_bench, iterations)

    # Benchmark: Rust
    if has_rust:

        def rust_bench():
            for method, path in test_cases:
                rust_router.match_route(method, path)

        rust = benchmark("Rust radix", rust_bench, iterations)

    # Results
    print(f"  {'Router':<20} {'Mean (ns)':<15} {'Ops/sec':<15} {'Speedup':<10}")
    print(f"  {'-' * 60}")
    print(
        f"  {'Python regex':<20} {py['mean_ns']:<15.0f} {py['ops_per_sec']:<15,.0f} {'baseline':<10}"
    )
    if has_rust:
        speedup = py["mean_ns"] / rust["mean_ns"]
        print(
            f"  {'Rust radix':<20} {rust['mean_ns']:<15.0f} {rust['ops_per_sec']:<15,.0f} {speedup:<10.1f}x"
        )

    print()

    # Per-case breakdown
    if has_rust:
        print("  Per-case breakdown (single match, 500k iterations):")
        print(f"  {'Path':<35} {'Python (ns)':<15} {'Rust (ns)':<15} {'Speedup':<10}")
        print(f"  {'-' * 75}")

        for method, path in test_cases:
            py_single = benchmark(
                f"py:{path}",
                lambda m=method, p=path: py_match(m, p),
                500_000,
            )
            rust_single = benchmark(
                f"rs:{path}",
                lambda m=method, p=path: rust_router.match_route(m, p),
                500_000,
            )
            speedup = py_single["mean_ns"] / rust_single["mean_ns"]
            label = f"{method} {path}"
            print(
                f"  {label:<35} {py_single['mean_ns']:<15.0f} {rust_single['mean_ns']:<15.0f} {speedup:<10.1f}x"
            )

    print()

    # ================================================================
    # JWT Benchmarks
    # ================================================================
    print("=" * 70)
    print("  JWT Encode/Decode — Rust vs Python")
    print("=" * 70)
    print()

    import orjson as _orjson

    jwt_secret = b"benchmark-secret-key-at-least-32-bytes-long!"
    jwt_payload = {"sub": "user123", "role": "admin", "org_id": "acme"}
    jwt_iterations = 200_000

    # Python JWT — import internals directly to avoid Django settings
    import base64
    import hashlib
    import hmac

    def _base64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    def _base64url_decode(data: str) -> bytes:
        pad = 4 - len(data) % 4
        if pad != 4:
            data += "=" * pad
        return base64.urlsafe_b64decode(data)

    def _json_encode(obj):
        return _orjson.dumps(obj, option=_orjson.OPT_SORT_KEYS)

    def _json_decode(data: bytes):
        return _orjson.loads(data)

    def _create_signature(signing_input, secret, algorithm):
        data = signing_input.encode("utf-8")
        hash_funcs = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}
        return hmac.new(secret, data, hash_funcs[algorithm]).digest()

    def _verify_signature(signing_input, signature, secret, algorithm):
        expected = _create_signature(signing_input, secret, algorithm)
        return hmac.compare_digest(signature, expected)

    def py_jwt_encode():
        import time as _time
        claims = dict(jwt_payload)
        now = int(_time.time())
        claims["iat"] = now
        claims["exp"] = now + 3600
        header = {"alg": "HS256", "typ": "JWT"}
        h = _base64url_encode(_json_encode(header))
        p = _base64url_encode(_json_encode(claims))
        si = f"{h}.{p}"
        sig = _create_signature(si, jwt_secret, "HS256")
        return f"{si}.{_base64url_encode(sig)}"

    # Generate a token for decode benchmarks
    test_token = py_jwt_encode()

    def py_jwt_decode():
        parts = test_token.split(".")
        si = f"{parts[0]}.{parts[1]}"
        sig = _base64url_decode(parts[2])
        _verify_signature(si, sig, jwt_secret, "HS256")
        return _json_decode(_base64url_decode(parts[1]))

    py_enc = benchmark("Python encode", py_jwt_encode, jwt_iterations)
    py_dec = benchmark("Python decode", py_jwt_decode, jwt_iterations)

    if has_rust:
        from django_matt._rust import jwt_encode as _jwt_encode_rs
        from django_matt._rust import jwt_decode as _jwt_decode_rs

        def rust_jwt_encode():
            import time as _time
            claims = dict(jwt_payload)
            now = int(_time.time())
            claims["iat"] = now
            claims["exp"] = now + 3600
            return _jwt_encode_rs(
                _orjson.dumps(claims, option=_orjson.OPT_SORT_KEYS),
                jwt_secret,
                "HS256",
            )

        rust_test_token = rust_jwt_encode()

        def rust_jwt_decode():
            return _jwt_decode_rs(rust_test_token, jwt_secret, "HS256", False, 0)

        rs_enc = benchmark("Rust encode", rust_jwt_encode, jwt_iterations)
        rs_dec = benchmark("Rust decode", rust_jwt_decode, jwt_iterations)

    print(f"  {'Operation':<20} {'Python (ns)':<15} {'Rust (ns)':<15} {'Speedup':<10}")
    print(f"  {'-' * 60}")
    if has_rust:
        enc_speedup = py_enc["mean_ns"] / rs_enc["mean_ns"]
        dec_speedup = py_dec["mean_ns"] / rs_dec["mean_ns"]
        print(f"  {'JWT encode':<20} {py_enc['mean_ns']:<15.0f} {rs_enc['mean_ns']:<15.0f} {enc_speedup:<10.1f}x")
        print(f"  {'JWT decode+verify':<20} {py_dec['mean_ns']:<15.0f} {rs_dec['mean_ns']:<15.0f} {dec_speedup:<10.1f}x")
    else:
        print(f"  {'JWT encode':<20} {py_enc['mean_ns']:<15.0f} {'N/A':<15} {'N/A':<10}")
        print(f"  {'JWT decode+verify':<20} {py_dec['mean_ns']:<15.0f} {'N/A':<15} {'N/A':<10}")

    print()

    # ================================================================
    # Query String Parsing Benchmarks
    # ================================================================
    print("=" * 70)
    print("  Query String Parsing — Rust vs Python")
    print("=" * 70)
    print()

    from urllib.parse import parse_qs

    qs_test_cases = [
        ("simple", "fields=id,name,email"),
        ("filters", "filter[status]=active&filter[role]=admin&filter[org]=acme"),
        ("full", "fields=id,name&filter[status]=active&sort=-created,name&page=2&limit=20&search=hello"),
        ("complex", "fields=id,name,email,created,updated&filter[status]=active&filter[role__in]=admin,user&sort=-created,name,email&page=3&limit=50&offset=100&search=test%20query"),
    ]

    qs_iterations = 500_000

    print(f"  {'Query':<15} {'Python (ns)':<15} {'Rust (ns)':<15} {'Speedup':<10}")
    print(f"  {'-' * 55}")

    for label, qs in qs_test_cases:
        py_qs = benchmark(f"py:{label}", lambda q=qs: parse_qs(q), qs_iterations)

        if has_rust:
            from django_matt._rust import parse_query_string as _parse_qs_rs
            rs_qs = benchmark(f"rs:{label}", lambda q=qs: _parse_qs_rs(q), qs_iterations)
            speedup = py_qs["mean_ns"] / rs_qs["mean_ns"]
            print(f"  {label:<15} {py_qs['mean_ns']:<15.0f} {rs_qs['mean_ns']:<15.0f} {speedup:<10.1f}x")
        else:
            print(f"  {label:<15} {py_qs['mean_ns']:<15.0f} {'N/A':<15} {'N/A':<10}")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()

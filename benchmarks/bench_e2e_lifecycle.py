"""End-to-end request lifecycle benchmark.

Simulates the full framework overhead path:
  routing → header parsing → JWT auth → query string parsing → serialization

Compares total per-request overhead with and without Rust extensions.

Run with: uv run python benchmarks/bench_e2e_lifecycle.py
"""

import base64
import hashlib
import hmac
import json
import re
import time


def benchmark(name: str, func, iterations: int = 100_000):
    """Run a benchmark and return results."""
    for _ in range(1000):
        func()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        func()
    elapsed_ns = time.perf_counter_ns() - start
    mean_ns = elapsed_ns / iterations
    return {"name": name, "mean_ns": mean_ns, "iterations": iterations}


# ================================================================
# Python implementations (pure Python baselines)
# ================================================================

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    pad = 4 - len(data) % 4
    if pad != 4:
        data += "=" * pad
    return base64.urlsafe_b64decode(data)


def _create_signature(signing_input, secret, algorithm):
    data = signing_input.encode("utf-8")
    hash_funcs = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}
    return hmac.new(secret, data, hash_funcs[algorithm]).digest()


def py_jwt_decode(token, secret):
    """Python JWT decode + verify."""
    parts = token.split(".")
    si = f"{parts[0]}.{parts[1]}"
    sig = _base64url_decode(parts[2])
    expected = _create_signature(si, secret, "HS256")
    hmac.compare_digest(sig, expected)
    return json.loads(_base64url_decode(parts[1]))


def py_jwt_encode(payload_dict, secret):
    """Python JWT encode."""
    header = {"alg": "HS256", "typ": "JWT"}
    h = _base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _base64url_encode(json.dumps(payload_dict, separators=(",", ":")).encode())
    si = f"{h}.{p}"
    sig = _create_signature(si, secret, "HS256")
    return f"{si}.{_base64url_encode(sig)}"


def py_regex_router(patterns):
    """Build a regex router."""
    compiled = []
    for method, pattern, endpoint_id in patterns:
        regex = pattern
        for match in re.finditer(r"\{(\w+?)(?::(\*))?\}", pattern):
            name = match.group(1)
            is_wildcard = match.group(2)
            if is_wildcard:
                regex = regex.replace(match.group(0), f"(?P<{name}>.+)")
            else:
                regex = regex.replace(match.group(0), f"(?P<{name}>[^/]+)")
        compiled.append((method, re.compile(f"^{regex}/?$"), endpoint_id))

    def match(method, path):
        for m, rx, eid in compiled:
            if m == method:
                result = rx.match(path)
                if result:
                    return eid, result.groupdict()
        return None
    return match


def py_parse_headers(meta):
    """Python header parsing."""
    result = {}
    auth = meta.get("HTTP_AUTHORIZATION", "")
    if auth:
        parts = auth.split(" ", 1)
        if len(parts) == 2:
            result["authorization"] = {"type": parts[0], "credential": parts[1]}
    api_key = meta.get("HTTP_X_API_KEY")
    if api_key:
        result["api_key"] = api_key
    req_id = meta.get("HTTP_X_REQUEST_ID")
    if req_id:
        result["request_id"] = req_id
    ct = meta.get("CONTENT_TYPE")
    if ct:
        if ";" in ct:
            media, params = ct.split(";", 1)
            result["content_type"] = {"media_type": media.strip(), "params": params.strip()}
        else:
            result["content_type"] = {"media_type": ct.strip()}
    accept = meta.get("HTTP_ACCEPT")
    if accept:
        accepts = {}
        for part in accept.split(","):
            part = part.strip()
            if ";q=" in part:
                media, q_str = part.split(";q=", 1)
                try:
                    q = float(q_str.split(";")[0])
                except ValueError:
                    q = 1.0
                accepts[media.strip()] = q
            else:
                accepts[part] = 1.0
        result["accept"] = accepts
    return result


def py_parse_qs(qs):
    """Python query string parsing."""
    from urllib.parse import parse_qs
    return parse_qs(qs)


def py_serialize_list(dicts):
    """Python JSON serialization."""
    return json.dumps(dicts).encode()


def main():
    try:
        from django_matt._rust import (
            RadixRouter,
            build_camel_case_map,
            jwt_decode as jwt_decode_rs,
            jwt_encode as jwt_encode_rs,
            parse_headers as parse_headers_rs,
            parse_query_string as parse_qs_rs,
            serialize_dicts_to_json as serialize_rs,
        )
        has_rust = True
    except ImportError:
        has_rust = False
        print("WARNING: Rust extensions not installed. Run `make rust-dev` first.")
        print("Showing Python-only benchmarks.\n")

    import orjson

    # ---- Setup ----

    secret = b"benchmark-secret-key-at-least-32-bytes-long!"
    jwt_payload = {"sub": "user123", "role": "admin", "org_id": "acme",
                   "iat": int(time.time()), "exp": int(time.time()) + 3600}

    # Generate a valid JWT
    test_token_py = py_jwt_encode(jwt_payload, secret)
    if has_rust:
        test_token_rs = jwt_encode_rs(
            orjson.dumps(jwt_payload, option=orjson.OPT_SORT_KEYS),
            secret, "HS256",
        )

    # Routes
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

    py_match = py_regex_router(route_defs)
    if has_rust:
        rust_router = RadixRouter()
        for method, pattern, endpoint_id in route_defs:
            rust_router.add_route(method, pattern, endpoint_id)

    # Request META (simulating Django request.META)
    meta = {
        "HTTP_AUTHORIZATION": f"Bearer {test_token_py}",
        "HTTP_ACCEPT": "application/json;q=1.0, text/html;q=0.5",
        "CONTENT_TYPE": "application/json; charset=utf-8",
        "HTTP_X_REQUEST_ID": "req-abc-123-def-456",
    }

    query_string = "fields=id,name,email&filter[status]=active&sort=-created,name&page=2&limit=20"

    # Response data (10 user objects)
    response_data = [
        {
            "id": i,
            "first_name": f"User{i}",
            "last_name": f"Smith{i}",
            "email": f"user{i}@example.com",
            "is_active": i % 3 != 0,
            "score": i * 1.5,
            "bio": None if i % 5 == 0 else f"Bio for user {i}",
        }
        for i in range(10)
    ]

    if has_rust:
        alias_map = build_camel_case_map(list(response_data[0].keys()))

    # ================================================================
    # Individual component benchmarks
    # ================================================================
    iterations = 200_000

    print("=" * 75)
    print("  End-to-End Request Lifecycle Benchmark")
    print("=" * 75)
    print()
    print("  Simulated request: GET /users/42")
    print("    Authorization: Bearer <jwt>")
    print("    Query: fields=id,name,email&filter[status]=active&sort=-created&page=2")
    print("    Response: 10 user objects serialized to JSON")
    print()

    print(f"  {'Stage':<25} {'Python (ns)':<15} {'Rust (ns)':<15} {'Speedup':<10}")
    print(f"  {'-' * 65}")

    stages_py = {}
    stages_rs = {}

    # 1. Route matching
    py_route = benchmark("py:route", lambda: py_match("GET", "/users/42"), iterations)
    stages_py["route"] = py_route["mean_ns"]
    if has_rust:
        rs_route = benchmark("rs:route", lambda: rust_router.match_route("GET", "/users/42"), iterations)
        stages_rs["route"] = rs_route["mean_ns"]
        speedup = py_route["mean_ns"] / rs_route["mean_ns"]
        print(f"  {'1. Route matching':<25} {py_route['mean_ns']:<15.0f} {rs_route['mean_ns']:<15.0f} {speedup:<10.1f}x")
    else:
        print(f"  {'1. Route matching':<25} {py_route['mean_ns']:<15.0f} {'N/A':<15} {'N/A':<10}")

    # 2. Header parsing
    py_hdr = benchmark("py:headers", lambda: py_parse_headers(meta), iterations)
    stages_py["headers"] = py_hdr["mean_ns"]
    if has_rust:
        rs_hdr = benchmark("rs:headers", lambda: parse_headers_rs(meta), iterations)
        stages_rs["headers"] = rs_hdr["mean_ns"]
        speedup = py_hdr["mean_ns"] / rs_hdr["mean_ns"]
        print(f"  {'2. Header parsing':<25} {py_hdr['mean_ns']:<15.0f} {rs_hdr['mean_ns']:<15.0f} {speedup:<10.1f}x")
    else:
        print(f"  {'2. Header parsing':<25} {py_hdr['mean_ns']:<15.0f} {'N/A':<15} {'N/A':<10}")

    # 3. JWT decode+verify
    py_jwt = benchmark("py:jwt", lambda: py_jwt_decode(test_token_py, secret), iterations)
    stages_py["jwt"] = py_jwt["mean_ns"]
    if has_rust:
        rs_jwt = benchmark("rs:jwt", lambda: jwt_decode_rs(test_token_rs, secret, "HS256", False, 0), iterations)
        stages_rs["jwt"] = rs_jwt["mean_ns"]
        speedup = py_jwt["mean_ns"] / rs_jwt["mean_ns"]
        print(f"  {'3. JWT decode+verify':<25} {py_jwt['mean_ns']:<15.0f} {rs_jwt['mean_ns']:<15.0f} {speedup:<10.1f}x")
    else:
        print(f"  {'3. JWT decode+verify':<25} {py_jwt['mean_ns']:<15.0f} {'N/A':<15} {'N/A':<10}")

    # 4. Query string parsing
    py_qs = benchmark("py:qs", lambda: py_parse_qs(query_string), iterations)
    stages_py["qs"] = py_qs["mean_ns"]
    if has_rust:
        rs_qs = benchmark("rs:qs", lambda: parse_qs_rs(query_string), iterations)
        stages_rs["qs"] = rs_qs["mean_ns"]
        speedup = py_qs["mean_ns"] / rs_qs["mean_ns"]
        print(f"  {'4. Query string parse':<25} {py_qs['mean_ns']:<15.0f} {rs_qs['mean_ns']:<15.0f} {speedup:<10.1f}x")
    else:
        print(f"  {'4. Query string parse':<25} {py_qs['mean_ns']:<15.0f} {'N/A':<15} {'N/A':<10}")

    # 5. Serialization (JSON + camelCase)
    py_ser = benchmark("py:serialize", lambda: py_serialize_list(response_data), iterations)
    stages_py["serialize"] = py_ser["mean_ns"]
    if has_rust:
        rs_ser = benchmark("rs:serialize", lambda: serialize_rs(response_data, alias_map), iterations)
        stages_rs["serialize"] = rs_ser["mean_ns"]
        speedup = py_ser["mean_ns"] / rs_ser["mean_ns"]
        print(f"  {'5. Serialize (camelCase)':<25} {py_ser['mean_ns']:<15.0f} {rs_ser['mean_ns']:<15.0f} {speedup:<10.1f}x")
    else:
        print(f"  {'5. Serialize (camelCase)':<25} {py_ser['mean_ns']:<15.0f} {'N/A':<15} {'N/A':<10}")

    # ================================================================
    # Total lifecycle
    # ================================================================
    print(f"  {'-' * 65}")

    total_py = sum(stages_py.values())
    if has_rust:
        total_rs = sum(stages_rs.values())
        total_speedup = total_py / total_rs
        print(f"  {'TOTAL':<25} {total_py:<15.0f} {total_rs:<15.0f} {total_speedup:<10.1f}x")
    else:
        print(f"  {'TOTAL':<25} {total_py:<15.0f} {'N/A':<15} {'N/A':<10}")

    print()

    # ================================================================
    # Combined lifecycle benchmark (all stages in one call)
    # ================================================================
    print("  Combined lifecycle (all 5 stages in sequence):")
    print()

    def py_lifecycle():
        py_match("GET", "/users/42")
        py_parse_headers(meta)
        py_jwt_decode(test_token_py, secret)
        py_parse_qs(query_string)
        py_serialize_list(response_data)

    py_combined = benchmark("py:lifecycle", py_lifecycle, iterations)

    if has_rust:
        def rs_lifecycle():
            rust_router.match_route("GET", "/users/42")
            parse_headers_rs(meta)
            jwt_decode_rs(test_token_rs, secret, "HS256", False, 0)
            parse_qs_rs(query_string)
            serialize_rs(response_data, alias_map)

        rs_combined = benchmark("rs:lifecycle", rs_lifecycle, iterations)
        combined_speedup = py_combined["mean_ns"] / rs_combined["mean_ns"]

        print(f"  {'Python total':<25} {py_combined['mean_ns']:<15.0f} ns/request")
        print(f"  {'Rust total':<25} {rs_combined['mean_ns']:<15.0f} ns/request")
        print(f"  {'Speedup':<25} {combined_speedup:.1f}x")
        print()

        # Throughput
        py_rps = 1_000_000_000 / py_combined["mean_ns"]
        rs_rps = 1_000_000_000 / rs_combined["mean_ns"]
        print(f"  {'Python throughput':<25} {py_rps:,.0f} req/s (framework overhead only)")
        print(f"  {'Rust throughput':<25} {rs_rps:,.0f} req/s (framework overhead only)")
        print(f"  {'Extra capacity':<25} +{rs_rps - py_rps:,.0f} req/s")
    else:
        print(f"  {'Python total':<25} {py_combined['mean_ns']:<15.0f} ns/request")
        py_rps = 1_000_000_000 / py_combined["mean_ns"]
        print(f"  {'Python throughput':<25} {py_rps:,.0f} req/s (framework overhead only)")

    print()
    print("=" * 75)
    print("  Note: These numbers measure framework overhead only — actual request")
    print("  throughput depends on database queries, business logic, and I/O.")
    print("=" * 75)


if __name__ == "__main__":
    main()

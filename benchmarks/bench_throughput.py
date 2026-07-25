#!/usr/bin/env python
"""
Request/Response Throughput Benchmarks for Django Matt.

Simulates API request/response cycles to measure:
- Request parsing overhead
- Response serialization
- Middleware simulation
- Full request/response cycle

Usage:
    python benchmarks/bench_throughput.py
    python benchmarks/bench_throughput.py --iterations 5000
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.bench_utils import (
    BenchmarkResult,
    print_environment,
    print_table,
    run_benchmark,
)

# --- Simulated Request/Response objects ---


@dataclass
class MockRequest:
    """Simulated HTTP request."""

    method: str
    path: str
    headers: dict[str, str]
    body: bytes
    query_params: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MockRequest":
        return cls(
            method=data.get("method", "GET"),
            path=data.get("path", "/"),
            headers=data.get("headers", {}),
            body=data.get("body", b""),
            query_params=data.get("query_params", {}),
        )


@dataclass
class MockResponse:
    """Simulated HTTP response."""

    status_code: int
    headers: dict[str, str]
    body: bytes

    def to_bytes(self) -> bytes:
        return self.body


# --- Simulated Middleware ---


class TimingMiddleware:
    """Simulated timing middleware."""

    def process_request(self, request: MockRequest) -> None:
        pass

    def process_response(self, response: MockResponse) -> MockResponse:
        return response


class AuthMiddleware:
    """Simulated auth middleware."""

    def process_request(self, request: MockRequest) -> None:
        # Simulate token validation
        _ = request.headers.get("Authorization", "").split(" ")

    def process_response(self, response: MockResponse) -> MockResponse:
        return response


# --- Simulated View ---


class MockView:
    """Simulated API view."""

    def __init__(self):
        self.middleware = [TimingMiddleware(), AuthMiddleware()]

    def dispatch(self, request: MockRequest) -> MockResponse:
        # Process request through middleware
        for mw in self.middleware:
            mw.process_request(request)

        # Handle request
        response = self.handle(request)

        # Process response through middleware (reverse order)
        for mw in reversed(self.middleware):
            response = mw.process_response(response)

        return response

    def handle(self, request: MockRequest) -> MockResponse:
        # Simulate view logic
        data = {"message": "Hello, World!", "path": request.path}
        body = json.dumps(data).encode()

        return MockResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=body,
        )


class MockListView(MockView):
    """Simulated list API view."""

    def handle(self, request: MockRequest) -> MockResponse:
        # Simulate list response
        items = [{"id": i, "name": f"Item {i}", "active": True} for i in range(20)]
        data = {"items": items, "count": len(items)}
        body = json.dumps(data).encode()

        return MockResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=body,
        )


class MockCreateView(MockView):
    """Simulated create API view."""

    def handle(self, request: MockRequest) -> MockResponse:
        # Parse request body
        if request.body:
            data = json.loads(request.body)
        else:
            data = {}

        # Simulate create response
        response_data = {"id": 1, **data}
        body = json.dumps(response_data).encode()

        return MockResponse(
            status_code=201,
            headers={"Content-Type": "application/json"},
            body=body,
        )


def run_throughput_benchmarks(iterations: int = 5000) -> list[BenchmarkResult]:
    """Run all throughput benchmarks."""
    results = []

    # --- Request Parsing ---
    print("Benchmarking request parsing...")

    raw_request = {
        "method": "POST",
        "path": "/api/users",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer token123",
            "X-Request-ID": "abc123",
        },
        "body": b'{"name": "Test User", "email": "test@example.com"}',
        "query_params": {"page": "1", "limit": "20"},
    }

    results.append(
        run_benchmark(
            "Request parsing (from dict)",
            lambda: MockRequest.from_dict(raw_request),
            iterations=iterations,
        )
    )

    # --- JSON Body Parsing ---
    print("Benchmarking JSON body parsing...")

    small_body = b'{"id": 1, "name": "Test"}'
    medium_body = json.dumps(
        {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "profile": {"bio": "Test bio", "location": "NYC"},
            "tags": ["python", "django"],
        }
    ).encode()

    results.append(
        run_benchmark(
            "JSON body parse (small)",
            lambda: json.loads(small_body),
            iterations=iterations,
        )
    )

    results.append(
        run_benchmark(
            "JSON body parse (medium)",
            lambda: json.loads(medium_body),
            iterations=iterations,
        )
    )

    # --- Response Serialization ---
    print("Benchmarking response serialization...")

    small_response_data = {"id": 1, "message": "OK"}
    list_response_data = {
        "items": [{"id": i, "name": f"Item {i}"} for i in range(20)],
        "count": 20,
    }

    results.append(
        run_benchmark(
            "Response serialize (small)",
            lambda: json.dumps(small_response_data).encode(),
            iterations=iterations,
        )
    )

    results.append(
        run_benchmark(
            "Response serialize (list 20)",
            lambda: json.dumps(list_response_data).encode(),
            iterations=iterations,
        )
    )

    # --- Full Request/Response Cycle ---
    print("Benchmarking full request/response cycle...")

    simple_view = MockView()
    list_view = MockListView()
    create_view = MockCreateView()

    get_request = MockRequest(
        method="GET",
        path="/api/hello",
        headers={"Authorization": "Bearer token123"},
        body=b"",
        query_params={},
    )

    results.append(
        run_benchmark(
            "Full cycle: GET (simple response)",
            lambda: simple_view.dispatch(get_request),
            iterations=iterations,
        )
    )

    list_request = MockRequest(
        method="GET",
        path="/api/items",
        headers={"Authorization": "Bearer token123"},
        body=b"",
        query_params={"page": "1", "limit": "20"},
    )

    results.append(
        run_benchmark(
            "Full cycle: GET (list response)",
            lambda: list_view.dispatch(list_request),
            iterations=iterations,
        )
    )

    post_request = MockRequest(
        method="POST",
        path="/api/items",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer token123",
        },
        body=b'{"name": "New Item", "description": "Test item"}',
        query_params={},
    )

    results.append(
        run_benchmark(
            "Full cycle: POST (create)",
            lambda: create_view.dispatch(post_request),
            iterations=iterations,
        )
    )

    # --- Middleware Overhead ---
    print("Benchmarking middleware overhead...")

    class NoMiddlewareView(MockView):
        def __init__(self):
            self.middleware = []

    no_mw_view = NoMiddlewareView()

    results.append(
        run_benchmark(
            "View dispatch (no middleware)",
            lambda: no_mw_view.dispatch(get_request),
            iterations=iterations,
        )
    )

    class ManyMiddlewareView(MockView):
        def __init__(self):
            self.middleware = [
                TimingMiddleware(),
                AuthMiddleware(),
                TimingMiddleware(),
                AuthMiddleware(),
                TimingMiddleware(),
            ]

    many_mw_view = ManyMiddlewareView()

    results.append(
        run_benchmark(
            "View dispatch (5 middleware)",
            lambda: many_mw_view.dispatch(get_request),
            iterations=iterations,
        )
    )

    # --- orjson throughput (if available) ---
    try:
        import orjson

        print("Benchmarking orjson throughput...")

        results.append(
            run_benchmark(
                "Response serialize orjson (list 20)",
                lambda: orjson.dumps(list_response_data),
                iterations=iterations,
            )
        )

    except ImportError:
        pass

    return results


def run_pydantic_throughput(iterations: int = 5000) -> list[BenchmarkResult]:
    """Run Pydantic-based throughput benchmarks."""
    results = []

    try:
        from pydantic import BaseModel

        print("\nBenchmarking Pydantic request/response...")

        class CreateItemRequest(BaseModel):
            name: str
            description: str = ""
            price: float = 0.0

        class ItemResponse(BaseModel):
            id: int
            name: str
            description: str
            price: float

        # Request validation
        raw_body = {"name": "Test Item", "description": "A test item", "price": 29.99}

        results.append(
            run_benchmark(
                "Pydantic request validation",
                lambda: CreateItemRequest(**raw_body),
                iterations=iterations,
            )
        )

        # Response serialization
        response_item = ItemResponse(id=1, name="Test Item", description="A test item", price=29.99)

        results.append(
            run_benchmark(
                "Pydantic response model_dump()",
                response_item.model_dump,
                iterations=iterations,
            )
        )

        results.append(
            run_benchmark(
                "Pydantic response model_dump_json()",
                response_item.model_dump_json,
                iterations=iterations,
            )
        )

        # Full cycle with Pydantic
        def pydantic_full_cycle():
            # Validate request
            req = CreateItemRequest(**raw_body)
            # Create response
            resp = ItemResponse(id=1, **req.model_dump())
            # Serialize
            return resp.model_dump_json().encode()

        results.append(
            run_benchmark(
                "Pydantic full cycle (validate + serialize)",
                pydantic_full_cycle,
                iterations=iterations,
            )
        )

    except ImportError:
        print("\nPydantic not installed, skipping Pydantic throughput...")

    return results


def main():
    parser = argparse.ArgumentParser(description="Request/response throughput benchmarks")
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=5000,
        help="Number of iterations (default: 5000)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" Request/Response Throughput Benchmarks")
    print("=" * 70)

    print_environment()

    results = run_throughput_benchmarks(iterations=args.iterations)
    results.extend(run_pydantic_throughput(iterations=args.iterations))

    if results:
        print_table(results, "Throughput Results")

        # Summary
        fastest = min(results, key=lambda r: r.mean_time_ms)
        print(f"Fastest: {fastest.name} ({fastest.ops_per_second:,.0f} ops/s)")

        # Calculate theoretical max throughput
        full_cycle_results = [r for r in results if "Full cycle" in r.name]
        if full_cycle_results:
            avg_ops = sum(r.ops_per_second for r in full_cycle_results) / len(full_cycle_results)
            print(
                f"\nTheoretical max throughput: ~{avg_ops:,.0f} requests/second (single-threaded)"
            )


if __name__ == "__main__":
    main()

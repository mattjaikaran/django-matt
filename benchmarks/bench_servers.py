#!/usr/bin/env python
"""Server backend HTTP benchmark — uvicorn / gunicorn / granian / robyn.

Spawns each available backend against ``benchmarks/_bench_asgi:app`` on a
free port, hammers it with concurrent ``httpx`` clients for a fixed
duration, and prints a comparison of request/sec and p50/p95/p99 latency.

Backends that aren't installed are skipped with a note. Run with::

    uv run python benchmarks/bench_servers.py
    uv run python benchmarks/bench_servers.py --duration 10 --concurrency 64
    uv run python benchmarks/bench_servers.py --backends granian,uvicorn --json out.json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_APP = "_bench_asgi:app"


@dataclass
class BackendResult:
    """Per-backend benchmark result."""

    name: str
    available: bool
    requests: int
    errors: int
    duration_s: float
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    note: str = ""

    @property
    def display_rps(self) -> str:
        return f"{self.rps:,.0f}" if self.requests else "—"

    @property
    def display_latency(self) -> str:
        if not self.requests:
            return "—"
        return f"{self.p50_ms:.2f} / {self.p95_ms:.2f} / {self.p99_ms:.2f}"


# --- Backend command builders -----------------------------------------------


def _uvicorn_cmd(port: int) -> list[str]:
    return [
        sys.executable, "-m", "uvicorn", BENCH_APP,
        "--host", "127.0.0.1", "--port", str(port),
        "--workers", "1", "--log-level", "warning",
    ]


def _gunicorn_cmd(port: int) -> list[str]:
    return [
        sys.executable, "-m", "gunicorn", BENCH_APP,
        "--worker-class", "uvicorn.workers.UvicornWorker",
        "--bind", f"127.0.0.1:{port}",
        "--workers", "1",
        "--log-level", "warning",
    ]


def _granian_cmd(port: int) -> list[str]:
    return [
        sys.executable, "-m", "granian",
        "--interface", "asgi",
        "--host", "127.0.0.1", "--port", str(port),
        "--workers", "1", "--log-level", "warning",
        BENCH_APP,
    ]


# Robyn isn't a generic ASGI host (it's a framework with its own router),
# so we don't shell it out against an arbitrary ASGI app — it would either
# fail or measure something unrelated. Keep the slot but mark it skipped.
BACKENDS: dict[str, dict] = {
    "uvicorn": {
        "module": "uvicorn",
        "build_cmd": _uvicorn_cmd,
        "skip_reason": "",
    },
    "gunicorn": {
        "module": "gunicorn",
        "build_cmd": _gunicorn_cmd,
        "skip_reason": "",
        "extra_modules": ["uvicorn"],
    },
    "granian": {
        "module": "granian",
        "build_cmd": _granian_cmd,
        "skip_reason": "",
    },
    "robyn": {
        "module": "robyn",
        "build_cmd": None,
        "skip_reason": "robyn ships its own framework — not a generic ASGI host",
    },
}


# --- Helpers ----------------------------------------------------------------


def _free_port() -> int:
    """Bind/release a socket to discover a free TCP port."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


async def _wait_until_ready(url: str, timeout: float = 10.0) -> bool:
    """Poll the backend until /ready returns 200 or timeout expires."""
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=1.0) as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    return True
            except (httpx.HTTPError, OSError):
                pass
            await asyncio.sleep(0.05)
    return False


async def _hammer(url: str, duration: float, concurrency: int) -> tuple[list[float], int]:
    """Issue requests across `concurrency` clients for `duration` seconds.

    Returns (per-request latencies in ms, error count).
    """
    latencies: list[float] = []
    errors = 0
    stop_at = time.monotonic() + duration
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)

    async def worker(client: httpx.AsyncClient) -> None:
        nonlocal errors
        while time.monotonic() < stop_at:
            t0 = time.perf_counter()
            try:
                r = await client.get(url)
                if r.status_code != 200:
                    errors += 1
                    continue
                latencies.append((time.perf_counter() - t0) * 1000.0)
            except httpx.HTTPError:
                errors += 1

    async with httpx.AsyncClient(limits=limits, timeout=5.0, http2=False) as client:
        await asyncio.gather(*(worker(client) for _ in range(concurrency)))

    return latencies, errors


def _percentiles(latencies: list[float]) -> tuple[float, float, float]:
    if not latencies:
        return 0.0, 0.0, 0.0
    s = sorted(latencies)
    return (
        s[int(len(s) * 0.50)],
        s[int(len(s) * 0.95)],
        s[min(int(len(s) * 0.99), len(s) - 1)],
    )


async def _bench_one(
    name: str,
    spec: dict,
    duration: float,
    concurrency: int,
    warmup: float,
) -> BackendResult:
    """Spawn one backend, warm it up, hammer it, kill it, return results."""
    if spec.get("skip_reason"):
        return BackendResult(name, False, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, spec["skip_reason"])

    module = spec["module"]
    if not _module_available(module):
        return BackendResult(name, False, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, f"{module} not installed")

    for extra in spec.get("extra_modules", []):
        if not _module_available(extra):
            return BackendResult(
                name, False, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, f"requires {extra}"
            )

    port = _free_port()
    cmd = spec["build_cmd"](port)
    env = os.environ.copy()
    # Make the bench app importable from REPO_ROOT/benchmarks/
    env["PYTHONPATH"] = (
        str(REPO_ROOT / "benchmarks") + os.pathsep + env.get("PYTHONPATH", "")
    )

    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    url = f"http://127.0.0.1:{port}/"
    try:
        ready = await _wait_until_ready(url, timeout=10.0)
        if not ready:
            return BackendResult(
                name, True, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, "failed to start"
            )

        # Warmup pass — discard latencies
        await _hammer(url, warmup, concurrency)

        # Real measurement
        t0 = time.monotonic()
        latencies, errors = await _hammer(url, duration, concurrency)
        elapsed = time.monotonic() - t0

        rps = len(latencies) / elapsed if elapsed > 0 else 0.0
        p50, p95, p99 = _percentiles(latencies)
        return BackendResult(
            name=name,
            available=True,
            requests=len(latencies),
            errors=errors,
            duration_s=elapsed,
            rps=rps,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


# --- Reporting --------------------------------------------------------------


def _print_table(results: list[BackendResult]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Server Backend Throughput", show_lines=True)
        table.add_column("Backend", style="cyan", no_wrap=True)
        table.add_column("Status", style="green")
        table.add_column("RPS", justify="right", style="bold")
        table.add_column("p50/p95/p99 ms", justify="right")
        table.add_column("Errors", justify="right", style="red")
        for r in results:
            status = "ok" if r.available and r.requests else (r.note or "skipped")
            table.add_row(
                r.name,
                status,
                r.display_rps,
                r.display_latency,
                str(r.errors) if r.requests else "—",
            )
        console.print(table)
    except ImportError:
        print(f"{'Backend':<10} {'RPS':>10} {'p50':>8} {'p95':>8} {'p99':>8}  Note")
        for r in results:
            note = r.note if not r.requests else ""
            print(
                f"{r.name:<10} {r.display_rps:>10} "
                f"{r.p50_ms:>8.2f} {r.p95_ms:>8.2f} {r.p99_ms:>8.2f}  {note}"
            )


def _baseline_speedup(results: list[BackendResult]) -> None:
    """Print speedup of each backend relative to uvicorn (the baseline)."""
    baseline = next(
        (r for r in results if r.name == "uvicorn" and r.requests), None
    )
    if not baseline:
        return
    print("\nSpeedup vs uvicorn (RPS ratio):")
    for r in results:
        if r.requests and r.name != "uvicorn":
            ratio = r.rps / baseline.rps
            print(f"  {r.name:<10} {ratio:>5.2f}x")


# --- Entry point ------------------------------------------------------------


async def main_async(args: argparse.Namespace) -> list[BackendResult]:
    selected = [b.strip() for b in args.backends.split(",")] if args.backends else list(BACKENDS)
    results: list[BackendResult] = []
    for name in selected:
        spec = BACKENDS.get(name)
        if not spec:
            results.append(
                BackendResult(name, False, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, "unknown backend")
            )
            continue
        print(f"-> Benchmarking {name}...", flush=True)
        results.append(
            await _bench_one(name, spec, args.duration, args.concurrency, args.warmup)
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=5.0, help="Seconds per backend (default: 5)")
    parser.add_argument("--warmup", type=float, default=1.0, help="Warmup seconds (default: 1)")
    parser.add_argument("--concurrency", type=int, default=32, help="Concurrent clients (default: 32)")
    parser.add_argument(
        "--backends",
        default="",
        help="Comma list of backends to run (default: all). E.g. granian,uvicorn",
    )
    parser.add_argument("--json", default="", help="Optional path to write JSON results")
    args = parser.parse_args()

    print(
        f"\nBackend benchmark: duration={args.duration}s "
        f"concurrency={args.concurrency} warmup={args.warmup}s\n"
    )
    results = asyncio.run(main_async(args))
    _print_table(results)
    _baseline_speedup(results)

    if args.json:
        out = {
            "config": vars(args),
            "results": [asdict(r) for r in results],
            "ts": int(time.time()),
        }
        Path(args.json).write_text(json.dumps(out, indent=2))
        print(f"\nWrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

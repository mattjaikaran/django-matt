#!/usr/bin/env python
"""Generate an HTML benchmark dashboard from ``.matt/benchmarks/*.json``.

Reads every timestamped baseline in ``.matt/benchmarks/`` (skipping the
``latest.json`` / ``servers-latest.json`` pointers) and renders a self-contained
static HTML page with Chart.js plots of each scenario's ops/sec + latency over
time and each server backend's RPS / p95 / peak RSS over time.

Usage:
    uv run python scripts/publish_bench_charts.py \
        --input .matt/benchmarks \
        --output docs/benchmarks/index.html

The output is a single HTML file (no external asset directory) — the Docs
workflow picks it up as part of the mkdocs build.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Skip the "latest" pointer files — they duplicate the newest timestamped run.
_POINTER_NAMES = {"latest.json", "servers-latest.json"}
_TS_IN_NAME = re.compile(r"(\d{8}_\d{6})")


@dataclass
class Point:
    ts: str
    label: str
    value: float


@dataclass
class Series:
    name: str
    points: list[Point] = field(default_factory=list)


def _iter_benchmark_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for p in root.iterdir():
        if p.suffix != ".json" or p.name in _POINTER_NAMES:
            continue
        files.append(p)
    return sorted(files, key=lambda p: p.stat().st_mtime)


def _extract_ts(path: Path, payload: dict) -> str:
    """Prefer the payload timestamp, fall back to the filename, then mtime."""
    ts = payload.get("timestamp") or payload.get("ts")
    if isinstance(ts, int | float):
        return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")
    if isinstance(ts, str):
        return ts
    m = _TS_IN_NAME.search(path.name)
    if m:
        raw = m.group(1)
        try:
            return (
                datetime.strptime(raw, "%Y%m%d_%H%M%S")
                .replace(tzinfo=UTC)
                .isoformat(timespec="seconds")
            )
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")


def _load_scenario_series(files: list[Path]) -> dict[str, Series]:
    """Load ops_per_second per benchmark name across all files.

    Main benchmarks (bench_json, bench_schema, bench_routing) dump a flat
    ``results`` list of dicts with ``name`` and ``ops_per_second``.
    """
    series: dict[str, Series] = {}
    for path in files:
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        results = payload.get("results")
        if not isinstance(results, list):
            continue
        # Server backend runs have a different shape — skip them here.
        if results and isinstance(results[0], dict) and "rss_peak_mb" in results[0]:
            continue
        ts = _extract_ts(path, payload)
        for row in results:
            name = row.get("name")
            ops = row.get("ops_per_second")
            if not name or ops is None:
                continue
            series.setdefault(name, Series(name=name)).points.append(
                Point(ts=ts, label=path.name, value=float(ops))
            )
    return series


def _load_server_series(files: list[Path]) -> dict[str, dict[str, Series]]:
    """Load RPS / p95 / peak RSS per server backend across all files."""
    metrics: dict[str, dict[str, Series]] = {}
    for path in files:
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            continue
        if not isinstance(results[0], dict) or "rss_peak_mb" not in results[0]:
            continue
        ts = _extract_ts(path, payload)
        for row in results:
            name = row.get("name")
            if not name or not row.get("requests"):
                continue
            per_backend = metrics.setdefault(name, {})
            for metric_key in ("rps", "p95_ms", "rss_peak_mb"):
                value = row.get(metric_key)
                if value is None:
                    continue
                s = per_backend.setdefault(metric_key, Series(name=metric_key))
                s.points.append(Point(ts=ts, label=path.name, value=float(value)))
    return metrics


def _series_to_dataset(s: Series, color: str) -> dict:
    return {
        "label": s.name,
        "data": [{"x": p.ts, "y": p.value} for p in s.points],
        "borderColor": color,
        "backgroundColor": color,
        "tension": 0.2,
        "fill": False,
    }


_PALETTE = [
    "#6366f1",
    "#22c55e",
    "#f97316",
    "#0ea5e9",
    "#eab308",
    "#ec4899",
    "#14b8a6",
    "#a855f7",
    "#f43f5e",
    "#84cc16",
]


def _render_html(
    scenario_series: dict[str, Series], server_series: dict[str, dict[str, Series]]
) -> str:
    scenario_datasets = [
        _series_to_dataset(s, _PALETTE[i % len(_PALETTE)])
        for i, s in enumerate(scenario_series.values())
    ]

    backend_palette = {
        name: _PALETTE[i % len(_PALETTE)] for i, name in enumerate(sorted(server_series))
    }

    def _per_metric_datasets(metric: str) -> list[dict]:
        datasets: list[dict] = []
        for backend, per_metric in server_series.items():
            s = per_metric.get(metric)
            if not s:
                continue
            datasets.append(
                {
                    "label": backend,
                    "data": [{"x": p.ts, "y": p.value} for p in s.points],
                    "borderColor": backend_palette[backend],
                    "backgroundColor": backend_palette[backend],
                    "tension": 0.2,
                    "fill": False,
                }
            )
        return datasets

    rps_datasets = _per_metric_datasets("rps")
    p95_datasets = _per_metric_datasets("p95_ms")
    rss_datasets = _per_metric_datasets("rss_peak_mb")

    payload = {
        "scenarios": scenario_datasets,
        "server_rps": rps_datasets,
        "server_p95": p95_datasets,
        "server_rss": rss_datasets,
    }

    return _HTML_TEMPLATE.replace("__DATA__", json.dumps(payload))


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>django-matt Benchmarks</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body { font-family: 'Inter', system-ui, sans-serif; max-width: 1100px;
         margin: 2rem auto; padding: 0 1rem; color: #1f2937;
         background: #f9fafb; }
  h1 { font-size: 1.8rem; font-weight: 700; margin-bottom: 0.25rem; }
  h2 { font-size: 1.15rem; margin-top: 2rem; color: #374151; }
  p.lede { color: #6b7280; }
  .card { background: white; border: 1px solid #e5e7eb; border-radius: 12px;
          padding: 1.25rem 1.25rem 0.75rem; margin: 1rem 0;
          box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
  canvas { width: 100% !important; height: 340px !important; }
  .empty { color: #9ca3af; font-style: italic; }
  footer { color: #9ca3af; font-size: 0.85rem; margin-top: 3rem; text-align: center; }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
</head>
<body>
<h1>django-matt Benchmarks</h1>
<p class="lede">Auto-generated from baseline JSONs in <code>.matt/benchmarks/</code>.
Higher is better for ops/sec &amp; RPS, lower is better for latency &amp; RSS.</p>

<h2>Scenarios — ops/sec over time</h2>
<div class="card"><canvas id="scenarios"></canvas></div>

<h2>Server backends — RPS</h2>
<div class="card"><canvas id="server_rps"></canvas></div>

<h2>Server backends — p95 latency (ms)</h2>
<div class="card"><canvas id="server_p95"></canvas></div>

<h2>Server backends — peak RSS (MB)</h2>
<div class="card"><canvas id="server_rss"></canvas></div>

<footer>Generated by <code>scripts/publish_bench_charts.py</code>.</footer>

<script>
  const DATA = __DATA__;
  const common = (datasets, yTitle) => ({
    type: 'line',
    data: { datasets },
    options: {
      responsive: true,
      interaction: { mode: 'nearest', intersect: false },
      plugins: { legend: { position: 'bottom' } },
      scales: {
        x: { type: 'time', time: { tooltipFormat: 'yyyy-LL-dd HH:mm' },
             ticks: { color: '#6b7280' }, grid: { color: '#f3f4f6' } },
        y: { title: { display: true, text: yTitle }, beginAtZero: true,
             ticks: { color: '#6b7280' }, grid: { color: '#f3f4f6' } },
      },
    },
  });
  const render = (id, datasets, yTitle) => {
    const el = document.getElementById(id);
    if (!datasets || datasets.length === 0) {
      el.replaceWith(Object.assign(document.createElement('div'),
        { className: 'empty', textContent: 'No data yet — run benchmarks with --save.' }));
      return;
    }
    new Chart(el.getContext('2d'), common(datasets, yTitle));
  };
  render('scenarios', DATA.scenarios, 'ops/sec');
  render('server_rps', DATA.server_rps, 'requests/sec');
  render('server_p95', DATA.server_p95, 'p95 latency (ms)');
  render('server_rss', DATA.server_rss, 'peak RSS (MB)');
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(".matt/benchmarks"),
        help="Directory with baseline JSONs (default: .matt/benchmarks)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/benchmarks/live.html"),
        help="HTML output path (default: docs/benchmarks/live.html)",
    )
    args = parser.parse_args(argv)

    files = _iter_benchmark_files(args.input)
    if not files:
        print(f"No benchmark JSONs under {args.input} — writing empty dashboard.")

    scenario_series = _load_scenario_series(files)
    server_series = _load_server_series(files)

    html = _render_html(scenario_series, server_series)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(
        f"Wrote {args.output} "
        f"(scenarios={len(scenario_series)}, servers={len(server_series)}, runs={len(files)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

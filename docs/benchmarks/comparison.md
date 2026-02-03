# Comparing Results

Tracking performance over time is crucial for preventing regressions. Django Matt provides built-in tools for comparing benchmark results against baselines.

## Basic Comparison

### Saving a Baseline

First, establish a baseline to compare against:

```bash
# Run benchmarks and save results
python manage.py benchmark --save
```

This creates two files in `.matt/benchmarks/`:

- `benchmark_YYYYMMDD_HHMMSS.json` - Timestamped results
- `latest.json` - Always points to most recent run

### Comparing with Baseline

After making changes, compare against the baseline:

```bash
python manage.py benchmark --compare
```

Output shows changes relative to baseline:

```
================================================================================
 Django Matt Benchmark Results
================================================================================

[JSON]
--------------------------------------------------------------------------------
Benchmark                                       Mean     Ops/s    vs Baseline
  orjson.dumps (small)                        0.002ms   500.0K        -2.5%
  json.dumps (small)                          0.016ms    62.5K        +6.2%
  FastJSONRenderer.dumps (medium)             0.043ms    23.3K        -5.1%

Comparison with baseline:
  Faster: 8
  Slower: 2
  Same: 5
```

### Understanding Comparison Status

| Status | Meaning | Threshold |
|--------|---------|-----------|
| `faster` | Performance improved | < -5% change |
| `slower` | Performance regressed | > +5% change |
| `same` | Within acceptable range | -5% to +5% |

Adjust the threshold with `--threshold`:

```bash
# Stricter: 2% threshold
python manage.py benchmark --compare --threshold 2.0

# Looser: 10% threshold
python manage.py benchmark --compare --threshold 10.0
```

## Comparison Workflow

### Development Workflow

1. **Before changes:** Create baseline on main branch

   ```bash
   git checkout main
   python manage.py benchmark --save
   ```

2. **After changes:** Compare on feature branch

   ```bash
   git checkout feature-branch
   python manage.py benchmark --compare
   ```

3. **If regressions detected:** Investigate and fix

   ```bash
   # Run specific scenario to isolate
   python manage.py benchmark --scenario json --compare
   ```

### Release Workflow

1. **Tag baseline:** Save with meaningful name

   ```bash
   python manage.py benchmark --save
   cp .matt/benchmarks/latest.json .matt/benchmarks/release_v1.0.json
   ```

2. **Compare against release:**

   ```bash
   python manage.py benchmark --compare --baseline release_v1.0.json
   ```

## Programmatic Comparison

### Basic Comparison

```python
from django_matt.benchmarks import BenchmarkRunner, BenchmarkSuite

suite = BenchmarkSuite()
runner = BenchmarkRunner(suite)

# Run current benchmarks
results = runner.run()

# Load baseline
baseline = runner.load_baseline()

# Compare
comparisons = runner.compare(baseline=baseline, threshold_percent=5.0)

for comp in comparisons:
    print(f"{comp.name}: {comp.mean_diff_percent:+.1f}% ({comp.status})")
```

### BenchmarkComparison Object

```python
@dataclass
class BenchmarkComparison:
    name: str              # Benchmark identifier
    scenario: str          # Parent scenario
    current: BenchmarkResult    # Current run result
    baseline: BenchmarkResult   # Baseline result
    mean_diff_percent: float    # Change in mean time
    ops_diff_percent: float     # Change in ops/second
    status: str            # "faster", "slower", or "same"
```

### Filtering Comparisons

```python
# Find regressions
regressions = [c for c in comparisons if c.status == "slower"]

# Find improvements
improvements = [c for c in comparisons if c.status == "faster"]

# Find significant changes (>10%)
significant = [c for c in comparisons if abs(c.mean_diff_percent) > 10]
```

## Detecting Regressions

### Threshold Selection

Choose thresholds based on your requirements:

| Use Case | Threshold | Rationale |
|----------|-----------|-----------|
| Production API | 2-5% | User-facing latency matters |
| Background tasks | 10-20% | Some variance acceptable |
| Development | 5-10% | Balance speed and accuracy |

### Statistical Significance

For critical comparisons, consider statistical significance:

```python
def is_significant(current: BenchmarkResult, baseline: BenchmarkResult) -> bool:
    """Check if difference is statistically significant."""
    # Use standard deviation to assess significance
    combined_std = (current.std_dev_ms + baseline.std_dev_ms) / 2
    diff = abs(current.mean_time_ms - baseline.mean_time_ms)

    # Difference should be > 2x combined std dev
    return diff > (2 * combined_std)
```

### Multi-Run Comparison

For more reliable results, run benchmarks multiple times:

```python
import statistics

def multi_run_comparison(runner, runs=5):
    """Run benchmarks multiple times and average results."""
    all_results = []

    for _ in range(runs):
        results = runner.run()
        all_results.append(results)

    # Average results by benchmark name
    averaged = {}
    for results in all_results:
        for r in results:
            if r.name not in averaged:
                averaged[r.name] = []
            averaged[r.name].append(r.mean_time_ms)

    return {
        name: statistics.mean(times)
        for name, times in averaged.items()
    }
```

## Reporting Comparisons

### Console Report with Comparisons

```python
from django_matt.benchmarks import ConsoleReporter

reporter = ConsoleReporter(use_colors=True)
report = reporter.report(results, comparisons=comparisons)
print(report)
```

### Markdown Report

```python
from django_matt.benchmarks import MarkdownReporter

reporter = MarkdownReporter()
report = reporter.report(results, comparisons=comparisons)

# Includes comparison columns
# | Benchmark | Mean | Ops/s | vs Baseline | Status |
```

### JSON Report

```python
from django_matt.benchmarks import JSONReporter

reporter = JSONReporter()
json_data = reporter.report(results, comparisons=comparisons)

# Includes comparison data
# {
#   "results": [...],
#   "comparisons": [
#     {
#       "name": "orjson.dumps (small)",
#       "mean_diff_percent": -2.5,
#       "status": "faster",
#       ...
#     }
#   ]
# }
```

## Tracking Trends

### Historical Analysis

Store results with meaningful names for trend tracking:

```bash
# After each release
python manage.py benchmark --save
cp .matt/benchmarks/latest.json .matt/benchmarks/v$(date +%Y%m%d).json
```

### Comparing Multiple Baselines

```python
from pathlib import Path
import json

def load_historical_results(storage_dir=".matt/benchmarks"):
    """Load all historical benchmark results."""
    results = {}
    for filepath in Path(storage_dir).glob("*.json"):
        if filepath.name == "latest.json":
            continue
        with open(filepath) as f:
            data = json.load(f)
            results[filepath.stem] = data
    return results

def plot_trend(benchmark_name: str, historical: dict):
    """Show performance trend for a specific benchmark."""
    for run_name, data in sorted(historical.items()):
        for result in data["results"]:
            if result["name"] == benchmark_name:
                print(f"{run_name}: {result['mean_time_ms']:.4f}ms")
```

### Export for Visualization

```python
import csv

def export_for_plotting(historical: dict, output_file="trends.csv"):
    """Export historical data for visualization tools."""
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "benchmark", "mean_ms", "ops_per_second"])

        for run_name, data in sorted(historical.items()):
            timestamp = data.get("timestamp", run_name)
            for result in data["results"]:
                writer.writerow([
                    timestamp,
                    result["name"],
                    result["mean_time_ms"],
                    result["ops_per_second"],
                ])
```

## Best Practices

### 1. Consistent Environment

Always run comparisons on the same hardware:

```bash
# Document environment in baseline
python manage.py benchmark --save --format json --output baseline_m1_macbook.json
```

### 2. Clean State

Ensure consistent state before benchmarking:

```bash
# Clear caches
python manage.py clear_cache

# Restart workers
supervisorctl restart all

# Then benchmark
python manage.py benchmark --compare
```

### 3. Version Control Baselines

Track baselines in version control:

```bash
# .gitignore
.matt/benchmarks/*.json
!.matt/benchmarks/baseline.json  # Keep the official baseline
```

### 4. Document Significant Changes

When intentionally accepting performance changes:

```python
# In commit message or PR description:
"""
Performance impact:
- json.dumps: +15% (acceptable - added validation)
- db_query: -20% (improvement - added index)

Benchmark comparison: python manage.py benchmark --compare
"""
```

### 5. Automate in CI

See [CI Integration](ci-integration.md) for automated regression detection.

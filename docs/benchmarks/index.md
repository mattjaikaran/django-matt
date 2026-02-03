# Benchmarking Overview

Django Matt includes a comprehensive benchmarking framework for measuring and tracking performance across your application. This guide covers why benchmarking matters and how to use the built-in tools effectively.

## Why Benchmark?

Performance is a critical aspect of API development. Regular benchmarking helps you:

- **Identify bottlenecks** before they affect users
- **Track regressions** as your codebase evolves
- **Compare implementations** to choose the best approach
- **Validate optimizations** with concrete data
- **Set baselines** for performance requirements

## Benchmarking Architecture

The Django Matt benchmarking system consists of several components:

```
django_matt/benchmarks/
    __init__.py      # Public API exports
    runner.py        # Core benchmark execution
    scenarios.py     # Built-in test scenarios
    reporters.py     # Output formatters
```

### Core Classes

| Class | Purpose |
|-------|---------|
| `BenchmarkRunner` | Orchestrates benchmark execution and manages results |
| `BenchmarkSuite` | Collection of benchmark scenarios |
| `BenchmarkScenario` | Base class for grouped benchmarks |
| `Benchmark` | Single measurement unit |
| `BenchmarkResult` | Timing statistics and metadata |

## Quick Start

Run all benchmarks with default settings:

```bash
python manage.py benchmark
```

Run a specific scenario:

```bash
python manage.py benchmark --scenario json
```

Compare with previous results:

```bash
python manage.py benchmark --compare --save
```

## Available Scenarios

Django Matt includes five built-in benchmark scenarios:

| Scenario | Description | Default Iterations |
|----------|-------------|-------------------|
| `json` | JSON serialization with stdlib, orjson, ujson | 5,000 |
| `schema` | Pydantic schema validation and serialization | 5,000 |
| `routing` | URL pattern matching and route resolution | 5,000 |
| `database` | CRUD operations on SQLite | 500 |
| `caching` | Cache get/set operations | 5,000 |

## Understanding Results

Each benchmark produces a `BenchmarkResult` with:

```python
@dataclass
class BenchmarkResult:
    name: str              # Benchmark identifier
    scenario: str          # Parent scenario name
    iterations: int        # Number of runs
    total_time_ms: float   # Sum of all iterations
    mean_time_ms: float    # Average time per iteration
    median_time_ms: float  # Middle value (50th percentile)
    min_time_ms: float     # Fastest iteration
    max_time_ms: float     # Slowest iteration
    std_dev_ms: float      # Standard deviation
    ops_per_second: float  # Throughput (1000/mean_time_ms)
    memory_mb: float       # Memory usage (requires psutil)
    metadata: dict         # Additional context
```

### Key Metrics

- **Mean Time**: Average execution time - use for general comparisons
- **Median Time**: Less affected by outliers - use for skewed distributions
- **Ops/Second**: Throughput metric - higher is better
- **Std Dev**: Consistency measure - lower indicates more stable performance

## Example Output

```
================================================================================
 Django Matt Benchmark Results
================================================================================

Environment:
  python_version: 3.12.0
  platform: macOS-14.0-arm64-arm-64bit
  orjson_version: 3.9.10
  django_version: 5.0

[JSON]
--------------------------------------------------------------------------------
Benchmark                                       Mean        Min        Max     Ops/s
  orjson.dumps (small)                        0.002ms    0.001ms    0.015ms   500.0K
  json.dumps (small)                          0.015ms    0.012ms    0.089ms    66.7K
  FastJSONRenderer.dumps (medium)             0.045ms    0.038ms    0.156ms    22.2K

[SCHEMA]
--------------------------------------------------------------------------------
Benchmark                                       Mean        Min        Max     Ops/s
  SimpleSchema validation                     0.008ms    0.006ms    0.045ms   125.0K
  NestedSchema validation                     0.025ms    0.020ms    0.098ms    40.0K

Summary:
  Total benchmarks: 15
  Total iterations: 75,000
```

## Best Practices

### 1. Run Benchmarks in Isolation

Ensure consistent results by:

- Closing other applications
- Running on the same hardware
- Using production-like settings

### 2. Use Sufficient Iterations

More iterations provide more accurate results:

```bash
# Quick check (development)
python manage.py benchmark --iterations 100

# Accurate measurement (CI/staging)
python manage.py benchmark --iterations 5000
```

### 3. Track Historical Data

Save results for trend analysis:

```bash
python manage.py benchmark --save
```

Results are stored in `.matt/benchmarks/` with timestamps.

### 4. Compare Before Merging

Check for regressions before merging changes:

```bash
# On main branch
python manage.py benchmark --save

# On feature branch
python manage.py benchmark --compare
```

## Next Steps

- [Running Benchmarks](running.md) - CLI options and configuration
- [Benchmark Scenarios](scenarios.md) - Available scenarios in detail
- [Comparing Results](comparison.md) - Regression detection
- [Custom Benchmarks](custom.md) - Creating your own scenarios
- [CI Integration](ci-integration.md) - Automated performance testing

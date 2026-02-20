# Running Benchmarks

This guide covers all the ways to run benchmarks using the Django Matt CLI and programmatic API.

## CLI Reference

### Basic Usage

```bash
# Run all benchmarks with defaults
python manage.py benchmark

# Run specific scenarios
python manage.py benchmark --scenario json schema

# Run with custom iterations
python manage.py benchmark --iterations 10000
```

### Command Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--scenario` | `-s` | Scenario(s) to run | All |
| `--iterations` | `-n` | Iterations per benchmark | Scenario default |
| `--warmup` | `-w` | Warmup iterations | 10 |
| `--compare` | `-c` | Compare with baseline | False |
| `--baseline` | `-b` | Baseline file to compare | latest.json |
| `--output` | `-o` | Output file path | stdout |
| `--format` | `-f` | Output format | console |
| `--save` | | Save results for comparison | False |
| `--list` | `-l` | List available scenarios | - |
| `--no-color` | | Disable colored output | False |
| `--threshold` | | Regression threshold % | 5.0 |
| `--quiet` | `-q` | Minimal output | False |

### Listing Scenarios

View all available benchmark scenarios:

```bash
python manage.py benchmark --list
```

Output:

```
Available Benchmark Scenarios:

  json
    JSON serialization benchmarks
    Default iterations: 5000

  schema
    Schema validation benchmarks
    Default iterations: 5000

  routing
    Request routing benchmarks
    Default iterations: 5000

  database
    Database CRUD benchmarks
    Default iterations: 500

  caching
    Caching benchmarks
    Default iterations: 5000
```

### Output Formats

#### Console (Default)

Colored terminal output with tables:

```bash
python manage.py benchmark --format console
```

#### JSON

Machine-readable JSON for processing:

```bash
python manage.py benchmark --format json --output results.json
```

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "results": [
    {
      "name": "orjson.dumps (small)",
      "scenario": "json",
      "iterations": 5000,
      "mean_time_ms": 0.002,
      "ops_per_second": 500000.0,
      ...
    }
  ],
  "metadata": {
    "python_version": "3.12.0",
    "orjson_version": "3.9.10"
  }
}
```

#### Markdown

Documentation-ready tables:

```bash
python manage.py benchmark --format markdown --output BENCHMARKS.md
```

```markdown
# Django Matt Benchmark Report

## Results

### Json

| Benchmark | Mean | Min | Max | Ops/s | Iterations |
|-----------|------|-----|-----|-------|------------|
| orjson.dumps (small) | 2.00us | 1.50us | 15.00us | 500.00K ops/s | 5,000 |
```

#### HTML

Interactive web report:

```bash
python manage.py benchmark --format html --output report.html
```

Generates a styled HTML page with summary cards and sortable tables.

## Programmatic API

### Basic Usage

```python
from django_matt.benchmarks import BenchmarkRunner, BenchmarkSuite

# Create suite with default scenarios
suite = BenchmarkSuite()

# Create runner
runner = BenchmarkRunner(suite)

# Run all benchmarks
results = runner.run()

# Print results
for result in results:
    print(f"{result.name}: {result.ops_per_second:.0f} ops/s")
```

### Running Specific Scenarios

```python
from django_matt.benchmarks import BenchmarkRunner, BenchmarkSuite

suite = BenchmarkSuite()
runner = BenchmarkRunner(suite)

# Run only JSON and schema scenarios
results = runner.run(scenarios=["json", "schema"])
```

### Custom Iterations

```python
# Override default iterations
results = runner.run(iterations=10000)
```

### Using Individual Benchmarks

```python
from django_matt.benchmarks import Benchmark

# Create a single benchmark
benchmark = Benchmark(
    name="my_operation",
    scenario="custom",
    iterations=1000,
    warmup_iterations=10,
)

# Run the benchmark
def my_function(x, y):
    return x + y

result = benchmark.run(my_function, 1, 2)

print(f"Mean: {result.mean_time_ms:.4f}ms")
print(f"Ops/s: {result.ops_per_second:.0f}")
```

### Async Benchmarks

```python
import asyncio
from django_matt.benchmarks import Benchmark

benchmark = Benchmark(name="async_operation", iterations=1000)

async def async_function():
    await asyncio.sleep(0.001)
    return "done"

# Use run_async for async functions
result = benchmark.run_async(async_function)
```

### Setup and Teardown

```python
from django_matt.benchmarks import Benchmark

benchmark = Benchmark(name="db_insert", iterations=100)

counter = [0]

def setup():
    # Called before each iteration
    pass

def teardown():
    # Called after each iteration
    counter[0] += 1

result = benchmark.run(
    my_insert_function,
    setup=setup,
    teardown=teardown,
)
```

## Using Reporters

### Console Reporter

```python
from django_matt.benchmarks import (
    BenchmarkRunner,
    BenchmarkSuite,
    ConsoleReporter,
)

suite = BenchmarkSuite()
runner = BenchmarkRunner(suite)
results = runner.run()

reporter = ConsoleReporter(use_colors=True)
report = reporter.report(results)
print(report)
```

### JSON Reporter

```python
from django_matt.benchmarks import JSONReporter

reporter = JSONReporter(indent=2)
json_output = reporter.report(results)

# Save to file
reporter.save("results.json", results)
```

### Markdown Reporter

```python
from django_matt.benchmarks import MarkdownReporter

reporter = MarkdownReporter(include_charts=True)
markdown = reporter.report(results)

# Save to file
reporter.save("BENCHMARKS.md", results)
```

### HTML Reporter

```python
from django_matt.benchmarks import HTMLReporter

reporter = HTMLReporter()
html = reporter.report(results)

# Save to file
reporter.save("report.html", results)
```

## Saving and Loading Results

### Saving Results

```python
runner = BenchmarkRunner()
results = runner.run()

# Save with automatic timestamp
runner.save_results()  # Saves to .matt/benchmarks/benchmark_YYYYMMDD_HHMMSS.json

# Save with custom filename
runner.save_results("custom_name.json")
```

### Loading Baseline

```python
# Load the most recent results
baseline = runner.load_baseline()  # Loads from latest.json

# Load specific file
baseline = runner.load_baseline("baseline_v1.json")
```

## Configuration

### Environment Variables

```bash
# Enable memory tracking (requires psutil)
uv add psutil

# Set custom storage directory
export DJANGO_MATT_BENCHMARK_DIR=".benchmarks"
```

### Django Settings

```python
# settings.py

DJANGO_MATT = {
    # Enable benchmark features
    "BENCHMARK_ENABLED": True,

    # Default storage directory
    "BENCHMARK_STORAGE_DIR": ".matt/benchmarks",
}
```

## Performance Tips

### 1. Disable GC During Benchmarks

The benchmark runner automatically disables garbage collection during measurements for more consistent results.

### 2. Warmup Iterations

Warmup runs help eliminate JIT compilation and cache warmup effects:

```bash
python manage.py benchmark --warmup 50
```

### 3. Multiple Runs

For critical measurements, run benchmarks multiple times:

```bash
for i in {1..5}; do
    python manage.py benchmark --scenario json --output "run_$i.json" --format json
done
```

### 4. Isolated Environment

Run in an isolated environment for production-like results:

```bash
# Use dedicated Docker container
docker run --rm -it myapp:latest python manage.py benchmark

# Or use isolated CPU cores (Linux)
taskset -c 0,1 python manage.py benchmark
```

## Troubleshooting

### Benchmark Shows "Skipped"

Some benchmarks require optional dependencies:

```bash
# For database benchmarks
uv add django

# For accurate memory tracking
uv add psutil

# For fastest JSON serialization
uv add orjson
```

### High Variance in Results

If `std_dev_ms` is high relative to `mean_time_ms`:

1. Increase warmup iterations: `--warmup 100`
2. Close background applications
3. Check for I/O-bound operations
4. Run on dedicated hardware

### Memory Issues with Large Iterations

For memory-intensive benchmarks:

```bash
# Reduce iterations
python manage.py benchmark --iterations 100

# Run scenarios separately
python manage.py benchmark --scenario json
python manage.py benchmark --scenario database
```

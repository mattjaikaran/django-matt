# Django Matt Benchmarks

This directory contains standalone performance benchmarks for the Django Matt framework.

## Quick Start

```bash
# Run all benchmarks
make benchmark

# Or run directly
python benchmarks/run_all.py

# Run specific benchmark
python benchmarks/bench_json.py
python benchmarks/bench_schema.py
python benchmarks/bench_database.py
python benchmarks/bench_throughput.py
```

## Available Benchmarks

| Script | Description |
|--------|-------------|
| `bench_json.py` | JSON serialization performance (stdlib vs orjson vs ujson) |
| `bench_schema.py` | Pydantic schema validation performance |
| `bench_database.py` | Database CRUD operation performance |
| `bench_throughput.py` | Request/response throughput simulation |
| `run_all.py` | Run all benchmarks with summary |

## Requirements

The benchmarks use Python's built-in `timeit` module. Optional dependencies:

```bash
# For fastest JSON serialization
uv add orjson ujson

# For memory tracking
uv add psutil

# For database benchmarks (requires Django)
uv add django
```

## Output Formats

### Console (default)

```bash
python benchmarks/run_all.py
```

### JSON

```bash
python benchmarks/run_all.py --format json --output results.json
```

### Markdown

```bash
python benchmarks/run_all.py --format markdown --output BENCHMARKS.md
```

## Comparison Mode

Compare current results against a baseline:

```bash
# Save baseline
python benchmarks/run_all.py --save

# Run and compare
python benchmarks/run_all.py --compare
```

Results are stored in `.matt/benchmarks/`.

## Framework Comparison

The benchmarks include a comparison structure for testing against other frameworks:

```bash
python benchmarks/bench_comparison.py
```

This compares Django Matt against:
- Django REST Framework (if installed)
- FastAPI (if installed)
- Raw Django (baseline)

## Writing Custom Benchmarks

```python
from bench_utils import Benchmark, run_benchmark

# Define your benchmark
def my_operation():
    # Your code here
    pass

# Run it
result = run_benchmark(
    name="my_operation",
    func=my_operation,
    iterations=1000,
)

print(f"Mean: {result['mean_ms']:.4f}ms")
print(f"Ops/s: {result['ops_per_second']:.0f}")
```

## CI Integration

Add to your CI pipeline:

```yaml
# .github/workflows/benchmark.yml
- name: Run benchmarks
  run: python benchmarks/run_all.py --format json --output benchmark-results.json

- name: Compare with baseline
  run: python benchmarks/run_all.py --compare --threshold 10
```

## Performance Tips

1. **Run on isolated hardware** - Close other applications
2. **Use warmup iterations** - Default is 10 warmup runs
3. **Multiple runs** - Run benchmarks multiple times for consistency
4. **Disable GC** - Benchmarks automatically disable GC during measurement

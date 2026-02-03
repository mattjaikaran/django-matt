# benchmark Command

Run performance benchmarks for the Django Matt framework.

## Synopsis

```bash
python manage.py benchmark [OPTIONS]
```

## Description

The `benchmark` command runs performance benchmarks to measure and compare the speed of various Django Matt operations:

- JSON serialization performance
- Schema validation speed
- Routing performance
- Database operations
- Caching performance

Use benchmarks to:

- Identify performance bottlenecks
- Compare different serialization options
- Track performance regressions
- Validate optimization efforts

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--scenario`, `-s` | All | Specific scenario(s) to run |
| `--iterations`, `-n` | Scenario default | Number of iterations per benchmark |
| `--warmup`, `-w` | `10` | Number of warmup iterations |
| `--compare`, `-c` | `false` | Compare with last saved run |
| `--baseline`, `-b` | `latest.json` | Baseline file for comparison |
| `--output`, `-o` | None | Output file for results |
| `--format`, `-f` | `console` | Format: `console`, `json`, `markdown`, `html` |
| `--save` | `false` | Save results for future comparison |
| `--list`, `-l` | `false` | List available scenarios |
| `--no-color` | `false` | Disable colored output |
| `--threshold` | `5.0` | Percentage threshold for comparison |
| `--quiet`, `-q` | `false` | Minimal output |

## Available Scenarios

List scenarios with:

```bash
python manage.py benchmark --list
```

| Scenario | Description | Default Iterations |
|----------|-------------|-------------------|
| `json` | JSON serialization/deserialization | 10000 |
| `schema` | Pydantic schema validation | 10000 |
| `routing` | URL routing resolution | 5000 |
| `database` | Database CRUD operations | 1000 |
| `caching` | Cache read/write operations | 5000 |

## Examples

### Run All Benchmarks

```bash
python manage.py benchmark
```

### Run Specific Scenarios

```bash
# Single scenario
python manage.py benchmark --scenario json

# Multiple scenarios
python manage.py benchmark --scenario json schema routing
```

### Custom Iterations

```bash
# More iterations for precision
python manage.py benchmark --scenario json --iterations 50000

# Fewer for quick check
python manage.py benchmark --iterations 100
```

### Compare with Previous Run

```bash
# Save current results
python manage.py benchmark --save

# Later, compare with saved results
python manage.py benchmark --compare
```

### Output Formats

```bash
# Console (default, colored)
python manage.py benchmark

# JSON for processing
python manage.py benchmark --format json --output results.json

# Markdown for documentation
python manage.py benchmark --format markdown --output BENCHMARKS.md

# HTML report
python manage.py benchmark --format html --output report.html
```

### CI/CD Integration

```bash
# Compare and fail if regression detected
python manage.py benchmark --compare --threshold 10.0
```

## Output Examples

### Console Output

```
============================================================
 Django Matt Benchmark Suite
============================================================

Running all scenarios...

Scenarios: json, schema, routing, database, caching

Running benchmarks...

JSON Serialization Benchmarks
------------------------------------------------------------
  orjson_serialize        10000 iterations
    Mean: 0.0234ms  Std: 0.0012ms  Ops: 42,735/s
  ujson_serialize         10000 iterations
    Mean: 0.0456ms  Std: 0.0023ms  Ops: 21,929/s
  stdlib_serialize        10000 iterations
    Mean: 0.1234ms  Std: 0.0089ms  Ops: 8,103/s

Schema Validation Benchmarks
------------------------------------------------------------
  pydantic_validate       10000 iterations
    Mean: 0.0567ms  Std: 0.0034ms  Ops: 17,636/s
  simple_validate         10000 iterations
    Mean: 0.0123ms  Std: 0.0008ms  Ops: 81,300/s

------------------------------------------------------------
Completed 5 benchmarks

Fastest: orjson_serialize (42,735 ops/s)
Slowest: stdlib_serialize (8,103 ops/s)
```

### JSON Output

```json
{
  "timestamp": "2024-03-01T10:30:00Z",
  "environment": {
    "python_version": "3.12.0",
    "django_version": "5.2.0",
    "django_matt_version": "0.1.0",
    "os": "darwin",
    "cpu": "Apple M1 Pro"
  },
  "results": [
    {
      "name": "orjson_serialize",
      "scenario": "json",
      "iterations": 10000,
      "mean_time_ms": 0.0234,
      "std_dev_ms": 0.0012,
      "min_time_ms": 0.0198,
      "max_time_ms": 0.0312,
      "ops_per_second": 42735
    }
  ]
}
```

### Markdown Output

```markdown
# Django Matt Benchmark Results

**Date:** 2024-03-01 10:30:00
**Environment:** Python 3.12.0, Django 5.2.0

## JSON Serialization

| Benchmark | Mean | Std Dev | Ops/s |
|-----------|------|---------|-------|
| orjson_serialize | 0.023ms | 0.001ms | 42,735 |
| ujson_serialize | 0.046ms | 0.002ms | 21,929 |
| stdlib_serialize | 0.123ms | 0.009ms | 8,103 |

## Schema Validation

| Benchmark | Mean | Std Dev | Ops/s |
|-----------|------|---------|-------|
| pydantic_validate | 0.057ms | 0.003ms | 17,636 |
```

### Comparison Output

```
============================================================
 Django Matt Benchmark Suite
============================================================

Comparing with baseline: latest.json

JSON Serialization Benchmarks
------------------------------------------------------------
  orjson_serialize
    Current:  0.0234ms  (42,735 ops/s)
    Baseline: 0.0256ms  (39,062 ops/s)
    Change:   -8.6% FASTER [OK]

  ujson_serialize
    Current:  0.0456ms  (21,929 ops/s)
    Baseline: 0.0412ms  (24,271 ops/s)
    Change:   +10.7% SLOWER [WARNING]

------------------------------------------------------------
Performance improved in 3 benchmarks
Performance regressed in 1 benchmark
```

## Benchmark Scenarios Detail

### JSON Scenario

Tests JSON serialization libraries:

- `orjson` (fastest, recommended)
- `ujson` (fast, good compatibility)
- `stdlib` (Python json module)

```bash
python manage.py benchmark --scenario json --iterations 50000
```

### Schema Scenario

Tests Pydantic schema operations:

- Model validation
- Model serialization
- Complex nested schemas

```bash
python manage.py benchmark --scenario schema
```

### Routing Scenario

Tests Django Matt router performance:

- URL resolution
- Path parameter extraction
- Middleware execution

```bash
python manage.py benchmark --scenario routing
```

### Database Scenario

Tests async database operations:

- Single object retrieval
- List queries with pagination
- Create operations
- Update operations

Requires database connection.

```bash
python manage.py benchmark --scenario database
```

### Caching Scenario

Tests cache operations:

- Single key get/set
- Bulk operations
- Cache with expiration

Requires cache backend configuration.

```bash
python manage.py benchmark --scenario caching
```

## Best Practices

### Regular Benchmarking

Run benchmarks regularly to catch regressions:

```bash
# In CI/CD
python manage.py benchmark --compare --save

# Check for significant regressions (>10%)
python manage.py benchmark --compare --threshold 10.0
```

### Consistent Environment

For accurate comparisons:

- Run on the same hardware
- Close other applications
- Use consistent database state
- Run multiple iterations

### Warmup Iterations

Always use warmup to avoid cold-start effects:

```bash
# Default warmup of 10 is usually sufficient
python manage.py benchmark --warmup 10

# More warmup for JIT compilation
python manage.py benchmark --warmup 100
```

### Save Baselines

Save results after optimization work:

```bash
# After performance improvements
python manage.py benchmark --save

# Results saved to .matt/benchmarks/latest.json
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Performance Tests

on: [push, pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -e .

      - name: Download baseline
        uses: actions/download-artifact@v3
        with:
          name: benchmark-baseline
        continue-on-error: true

      - name: Run benchmarks
        run: |
          python manage.py benchmark \
            --compare \
            --threshold 15.0 \
            --format json \
            --output benchmark-results.json \
            --save

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-baseline
          path: .matt/benchmarks/latest.json
```

## See Also

- [Performance Documentation](../performance/optimization.md)
- [Caching Guide](../performance/caching.md)
- [Serialization Options](../performance/serialization.md)

# CI/CD Integration

Integrating benchmarks into your CI/CD pipeline helps catch performance regressions before they reach production. This guide covers setup for popular CI platforms.

## Overview

A typical CI benchmark workflow:

1. Run benchmarks on every PR
2. Compare against baseline (main branch)
3. Fail if regressions exceed threshold
4. Store results for historical tracking
5. Generate reports for review

## GitHub Actions

### Basic Workflow

```yaml
# .github/workflows/benchmarks.yml
name: Benchmarks

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  benchmark:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
          pip install orjson  # For accurate JSON benchmarks

      - name: Run benchmarks
        run: |
          python manage.py benchmark --format json --output benchmark_results.json

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: benchmark_results.json
```

### With Baseline Comparison

```yaml
# .github/workflows/benchmarks.yml
name: Benchmarks

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  contents: read
  pull-requests: write

jobs:
  benchmark:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Need history for baseline

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          pip install orjson psutil

      - name: Download baseline (if exists)
        uses: actions/cache@v4
        with:
          path: .matt/benchmarks/baseline.json
          key: benchmark-baseline-${{ github.base_ref || 'main' }}
          restore-keys: |
            benchmark-baseline-main

      - name: Run benchmarks
        id: benchmark
        run: |
          mkdir -p .matt/benchmarks

          # Run benchmarks with comparison if baseline exists
          if [ -f .matt/benchmarks/baseline.json ]; then
            cp .matt/benchmarks/baseline.json .matt/benchmarks/latest.json
            python manage.py benchmark --compare --threshold 5.0 --format json --output results.json
            echo "has_baseline=true" >> $GITHUB_OUTPUT
          else
            python manage.py benchmark --format json --output results.json
            echo "has_baseline=false" >> $GITHUB_OUTPUT
          fi

      - name: Check for regressions
        if: steps.benchmark.outputs.has_baseline == 'true'
        run: |
          python << 'EOF'
          import json
          import sys

          with open("results.json") as f:
              data = json.load(f)

          comparisons = data.get("comparisons", [])
          regressions = [c for c in comparisons if c["status"] == "slower" and c["mean_diff_percent"] > 10]

          if regressions:
              print("Performance regressions detected:")
              for r in regressions:
                  print(f"  - {r['name']}: {r['mean_diff_percent']:+.1f}%")
              sys.exit(1)
          else:
              print("No significant regressions detected")
          EOF

      - name: Update baseline (main branch only)
        if: github.ref == 'refs/heads/main'
        run: |
          cp results.json .matt/benchmarks/baseline.json

      - name: Save new baseline
        if: github.ref == 'refs/heads/main'
        uses: actions/cache/save@v4
        with:
          path: .matt/benchmarks/baseline.json
          key: benchmark-baseline-main

      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('results.json', 'utf8'));

            let body = '## Benchmark Results\n\n';

            // Summary
            const summary = results.summary || {};
            body += `**Total benchmarks:** ${summary.total_benchmarks || 'N/A'}\n`;
            body += `**Scenarios:** ${(summary.scenarios || []).join(', ')}\n\n`;

            // Comparison summary if available
            if (results.comparisons && results.comparisons.length > 0) {
              const faster = results.comparisons.filter(c => c.status === 'faster').length;
              const slower = results.comparisons.filter(c => c.status === 'slower').length;
              const same = results.comparisons.filter(c => c.status === 'same').length;

              body += '### Comparison with baseline\n\n';
              body += `| Status | Count |\n|--------|-------|\n`;
              body += `| Faster | ${faster} |\n`;
              body += `| Slower | ${slower} |\n`;
              body += `| Same | ${same} |\n\n`;

              // List significant changes
              const significant = results.comparisons.filter(c =>
                Math.abs(c.mean_diff_percent) > 5
              );

              if (significant.length > 0) {
                body += '### Significant changes\n\n';
                body += '| Benchmark | Change | Status |\n|-----------|--------|--------|\n';
                for (const c of significant) {
                  const emoji = c.status === 'faster' ? ':white_check_mark:' : ':warning:';
                  body += `| ${c.name} | ${c.mean_diff_percent > 0 ? '+' : ''}${c.mean_diff_percent.toFixed(1)}% | ${emoji} |\n`;
                }
              }
            }

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });
```

### Dedicated Benchmark Runner

For more consistent results, use a dedicated self-hosted runner:

```yaml
jobs:
  benchmark:
    runs-on: [self-hosted, benchmark-runner]
    # ... rest of workflow
```

## GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - test
  - benchmark

benchmark:
  stage: benchmark
  image: python:3.12
  cache:
    key: benchmark-baseline
    paths:
      - .matt/benchmarks/baseline.json
  script:
    - pip install -e ".[dev]" orjson psutil
    - mkdir -p .matt/benchmarks

    # Run with comparison if baseline exists
    - |
      if [ -f .matt/benchmarks/baseline.json ]; then
        cp .matt/benchmarks/baseline.json .matt/benchmarks/latest.json
        python manage.py benchmark --compare --format markdown --output benchmark_report.md
      else
        python manage.py benchmark --format markdown --output benchmark_report.md
      fi

    # Update baseline on main
    - |
      if [ "$CI_COMMIT_BRANCH" == "main" ]; then
        python manage.py benchmark --format json --output .matt/benchmarks/baseline.json
      fi

  artifacts:
    paths:
      - benchmark_report.md
    reports:
      metrics: benchmark_report.md

  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"
```

## CircleCI

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  benchmark:
    docker:
      - image: cimg/python:3.12
    resource_class: medium+  # Consistent resources
    steps:
      - checkout
      - restore_cache:
          keys:
            - benchmark-baseline-v1

      - run:
          name: Install dependencies
          command: |
            pip install -e ".[dev]" orjson psutil

      - run:
          name: Run benchmarks
          command: |
            mkdir -p .matt/benchmarks
            if [ -f .matt/benchmarks/baseline.json ]; then
              cp .matt/benchmarks/baseline.json .matt/benchmarks/latest.json
              python manage.py benchmark --compare --format json --output results.json
            else
              python manage.py benchmark --format json --output results.json
            fi

      - run:
          name: Check for regressions
          command: |
            python scripts/check_benchmark_regressions.py results.json

      - run:
          name: Update baseline
          command: |
            if [ "$CIRCLE_BRANCH" == "main" ]; then
              cp results.json .matt/benchmarks/baseline.json
            fi

      - save_cache:
          key: benchmark-baseline-v1
          paths:
            - .matt/benchmarks/baseline.json

      - store_artifacts:
          path: results.json

workflows:
  version: 2
  test-and-benchmark:
    jobs:
      - benchmark:
          filters:
            branches:
              only:
                - main
                - /feature\/.*/
```

## Regression Check Script

Create a reusable script for checking regressions:

```python
#!/usr/bin/env python
# scripts/check_benchmark_regressions.py
"""
Check benchmark results for regressions.

Usage:
    python scripts/check_benchmark_regressions.py results.json [--threshold 10.0]
"""

import argparse
import json
import sys


def check_regressions(results_file: str, threshold: float = 10.0) -> int:
    """
    Check benchmark results for regressions.

    Args:
        results_file: Path to JSON results file
        threshold: Percentage threshold for regression

    Returns:
        Exit code (0 = pass, 1 = fail)
    """
    with open(results_file) as f:
        data = json.load(f)

    comparisons = data.get("comparisons", [])

    if not comparisons:
        print("No comparison data available (no baseline)")
        return 0

    # Find regressions exceeding threshold
    regressions = [
        c for c in comparisons
        if c["status"] == "slower" and c["mean_diff_percent"] > threshold
    ]

    # Print summary
    faster = len([c for c in comparisons if c["status"] == "faster"])
    slower = len([c for c in comparisons if c["status"] == "slower"])
    same = len([c for c in comparisons if c["status"] == "same"])

    print(f"Benchmark Comparison Summary")
    print(f"============================")
    print(f"Faster: {faster}")
    print(f"Slower: {slower}")
    print(f"Same:   {same}")
    print()

    if regressions:
        print(f"REGRESSIONS EXCEEDING {threshold}% THRESHOLD:")
        print("-" * 50)
        for r in regressions:
            print(f"  {r['name']}: {r['mean_diff_percent']:+.1f}%")
            print(f"    Baseline: {r['baseline']['mean_time_ms']:.4f}ms")
            print(f"    Current:  {r['current']['mean_time_ms']:.4f}ms")
            print()

        print(f"\nFAILED: {len(regressions)} regression(s) detected")
        return 1

    print(f"\nPASSED: No regressions exceeding {threshold}%")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check for benchmark regressions")
    parser.add_argument("results_file", help="Path to benchmark results JSON")
    parser.add_argument("--threshold", type=float, default=10.0,
                        help="Regression threshold percentage (default: 10.0)")

    args = parser.parse_args()
    sys.exit(check_regressions(args.results_file, args.threshold))
```

## Best Practices for CI Benchmarks

### 1. Use Consistent Hardware

```yaml
# GitHub Actions - use specific runner
runs-on: ubuntu-latest  # May vary
runs-on: [self-hosted, benchmark]  # Consistent

# GitLab CI - use tagged runners
benchmark:
  tags:
    - benchmark-runner
```

### 2. Reduce Noise

```yaml
# Minimize concurrent processes
benchmark:
  script:
    # Stop unnecessary services
    - sudo systemctl stop docker || true
    - sudo systemctl stop snapd || true

    # Set process priority
    - nice -n -20 python manage.py benchmark
```

### 3. Use Fewer Iterations in CI

```yaml
# CI benchmarks should be faster
- python manage.py benchmark --iterations 500
```

### 4. Cache Dependencies

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: pip-${{ hashFiles('**/requirements.txt') }}
```

### 5. Store Historical Data

```yaml
# Upload as artifact for historical analysis
- uses: actions/upload-artifact@v4
  with:
    name: benchmark-${{ github.sha }}
    path: results.json
    retention-days: 90
```

### 6. Set Appropriate Thresholds

| Environment | Threshold | Rationale |
|-------------|-----------|-----------|
| PR checks | 10-15% | Avoid false positives |
| Main branch | 5-10% | Catch real regressions |
| Release | 2-5% | Strict quality gate |

### 7. Run on Schedule

```yaml
# Run comprehensive benchmarks nightly
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM daily

jobs:
  nightly-benchmark:
    runs-on: [self-hosted, benchmark]
    steps:
      - run: python manage.py benchmark --iterations 10000
```

## Reporting and Visualization

### Generate HTML Reports

```yaml
- name: Generate HTML report
  run: python manage.py benchmark --format html --output report.html

- name: Deploy to GitHub Pages
  uses: peaceiris/actions-gh-pages@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./benchmarks
```

### Track Trends

```python
# scripts/analyze_trends.py
import json
from pathlib import Path
import matplotlib.pyplot as plt

def plot_trends(benchmark_dir=".matt/benchmarks"):
    """Generate trend plots from historical benchmark data."""
    results = {}

    for filepath in sorted(Path(benchmark_dir).glob("benchmark_*.json")):
        with open(filepath) as f:
            data = json.load(f)

        timestamp = data["timestamp"]
        for result in data["results"]:
            name = result["name"]
            if name not in results:
                results[name] = {"timestamps": [], "values": []}
            results[name]["timestamps"].append(timestamp)
            results[name]["values"].append(result["mean_time_ms"])

    # Plot each benchmark
    for name, data in results.items():
        plt.figure(figsize=(10, 6))
        plt.plot(data["timestamps"], data["values"], marker="o")
        plt.title(f"Performance Trend: {name}")
        plt.xlabel("Date")
        plt.ylabel("Mean Time (ms)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f"trends/{name.replace(' ', '_')}.png")
        plt.close()
```

## Troubleshooting

### Flaky Results

If benchmarks show high variance between runs:

1. Increase warmup iterations
2. Use dedicated runners
3. Add multiple runs and average

```yaml
- name: Run benchmarks (3 runs)
  run: |
    for i in 1 2 3; do
      python manage.py benchmark --format json --output "run_$i.json"
    done
    python scripts/average_results.py run_*.json > results.json
```

### Memory Issues

For large benchmark suites:

```yaml
- name: Run scenarios separately
  run: |
    for scenario in json schema routing database caching; do
      python manage.py benchmark --scenario $scenario --output "${scenario}.json"
    done
```

### Baseline Drift

If baseline becomes stale:

```yaml
# Reset baseline periodically
on:
  schedule:
    - cron: '0 0 1 * *'  # First of month

jobs:
  reset-baseline:
    runs-on: [self-hosted, benchmark]
    steps:
      - run: python manage.py benchmark --save
      - run: cp .matt/benchmarks/latest.json .matt/benchmarks/baseline.json
```

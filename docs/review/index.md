# Code Review

Automated code review engine with pluggable analyzers for complexity, SOLID principles, Django best practices, security, performance, async safety, N+1 queries, migration safety, and API design.

## Quick Start

```python
from pathlib import Path
from django_matt.review.engine import ReviewEngine

engine = ReviewEngine()
summary = engine.review_paths([Path("myapp/")])

print(f"Files analyzed: {summary.files_analyzed}")
print(f"Findings: {len(summary.findings)}")
for finding in summary.findings:
    print(f"  [{finding.severity}] {finding.file}:{finding.line} - {finding.message}")
```

## Configuration

```python
from django_matt.review.config import ReviewConfig

config = ReviewConfig(
    analyzers=[
        "complexity",
        "solid",
        "django",
        "security",
        "performance",
        "async_safety",
        "n_plus_one",
        "migration_safety",
        "api_design",
        "ai_friendly",
        "modularity",
    ],
    # Additional config per analyzer...
)

engine = ReviewEngine(config=config)
```

## Key Features

### Built-in Analyzers

| Analyzer | Key | What It Checks |
|----------|-----|----------------|
| ComplexityAnalyzer | `complexity` | Cyclomatic complexity, function length, nesting depth |
| SolidAnalyzer | `solid` | Single responsibility, open/closed, dependency inversion |
| DjangoBestPracticesAnalyzer | `django` | Django-specific patterns and anti-patterns |
| SecurityAnalyzer | `security` | SQL injection, XSS, hardcoded secrets, unsafe deserialization |
| PerformanceAnalyzer | `performance` | N+1 indicators, missing indexes, inefficient queries |
| AsyncSafetyAnalyzer | `async_safety` | Sync ORM in async, blocking calls, missing await |
| NPlusOneAnalyzer | `n_plus_one` | Query patterns that cause N+1 problems |
| MigrationSafetyAnalyzer | `migration_safety` | Dangerous migration operations, missing indexes |
| APIDesignAnalyzer | `api_design` | REST conventions, response consistency, versioning |
| AIFriendlyAnalyzer | `ai_friendly` | Code readability for AI assistants |
| ModularityAnalyzer | `modularity` | Module coupling, circular dependencies |

### ReviewEngine

```python
from django_matt.review.engine import ReviewEngine

engine = ReviewEngine(
    config=config,
    custom_analyzers=[MyCustomAnalyzer()],
)

# Review a single file
summary = engine.review_file(Path("myapp/views.py"))

# Review multiple paths (files or directories)
summary = engine.review_paths([
    Path("myapp/"),
    Path("otherapp/models.py"),
])

# Access results
print(summary.files_analyzed)
print(summary.analyzers_run)
print(summary.duration_seconds)
for finding in summary.findings:
    print(finding.severity, finding.file, finding.line, finding.message)
```

### AI Reviewer

The `ai_reviewer` module integrates with LLMs for deeper code analysis:

```python
from django_matt.review.ai_reviewer import AIReviewer

reviewer = AIReviewer()
# Sends code to configured LLM for analysis
```

### Custom Analyzers

Extend `BaseAnalyzer` to create your own:

```python
from django_matt.review.analyzers.base import BaseAnalyzer
from django_matt.review.findings import Finding, Severity

class MyAnalyzer(BaseAnalyzer):
    name = "my_analyzer"

    def analyze_file(self, file_path, source, tree):
        findings = []
        # tree is an ast.Module
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and len(node.body) > 50:
                findings.append(Finding(
                    file=str(file_path),
                    line=node.lineno,
                    severity=Severity.WARNING,
                    analyzer=self.name,
                    message=f"Function '{node.name}' is too long ({len(node.body)} statements)",
                ))
        return findings

# Use it
engine = ReviewEngine(custom_analyzers=[MyAnalyzer(config)])
```

## Practical Example

Run a review as a management command:

```python
from pathlib import Path
from django_matt.review.engine import ReviewEngine
from django_matt.review.config import ReviewConfig

config = ReviewConfig(
    analyzers=["complexity", "django", "security", "async_safety", "n_plus_one"],
)
engine = ReviewEngine(config=config)

summary = engine.review_paths([Path("myapp/")])

# Print report
print(f"\nReview complete: {summary.files_analyzed} files, "
      f"{len(summary.findings)} findings in {summary.duration_seconds:.1f}s\n")

by_severity = {}
for f in summary.findings:
    by_severity.setdefault(f.severity, []).append(f)

for severity in ["error", "warning", "info"]:
    findings = by_severity.get(severity, [])
    if findings:
        print(f"  {severity.upper()}: {len(findings)}")
        for f in findings[:5]:
            print(f"    {f.file}:{f.line} - {f.message}")
```

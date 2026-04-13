"""
django_matt.review — Automated code review agent.

Static analysis + optional LLM-powered review for Django best practices,
SOLID principles, complexity, security, modularity, and AI-friendliness.

Usage:
    python manage.py matt_review                         # full review
    python manage.py matt_review --analyzers solid,security
    python manage.py matt_review --format json --output review.json
    python manage.py matt_review myapp/ --min-severity warning
    python manage.py matt_review --ai                    # LLM-enhanced review

Programmatic:
    from django_matt.review import ReviewEngine, ReviewConfig

    engine = ReviewEngine(ReviewConfig(analyzers={"complexity", "solid"}))
    summary = engine.review_directory(Path("myapp/"))
    for finding in summary.findings:
        print(finding)
"""

from django_matt.review.config import ReviewConfig
from django_matt.review.engine import ReviewEngine
from django_matt.review.findings import (
    Category,
    Finding,
    Location,
    ReviewSummary,
    Severity,
)

__all__ = [
    "Category",
    "Finding",
    "Location",
    "ReviewConfig",
    "ReviewEngine",
    "ReviewSummary",
    "Severity",
    # Analyzers (lazy)
    "AsyncSafetyAnalyzer",
    "NPlusOneAnalyzer",
    "MigrationSafetyAnalyzer",
    "APIDesignAnalyzer",
]


def __getattr__(name: str) -> type:
    """Lazy imports for analyzer classes."""
    _lazy = {
        "AsyncSafetyAnalyzer": "django_matt.review.analyzers.async_safety",
        "NPlusOneAnalyzer": "django_matt.review.analyzers.n_plus_one",
        "MigrationSafetyAnalyzer": "django_matt.review.analyzers.migration_safety",
        "APIDesignAnalyzer": "django_matt.review.analyzers.api_design",
    }
    if name in _lazy:
        import importlib
        mod = importlib.import_module(_lazy[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

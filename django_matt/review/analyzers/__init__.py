"""Code review analyzers — pluggable static analysis checks."""

from django_matt.review.analyzers.base import BaseAnalyzer

__all__ = [
    "BaseAnalyzer",
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

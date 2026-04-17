"""
Django Matt Smart Testing — affected test detection and failed-only re-runs.

Provides:
- ASTBlockDiffer: block-level source comparison (not line-level)
- TestDependencyTracker: coverage.py-backed test→source dependency tracking
- pytest plugin: --matt-affected, --matt-failed, --matt-rebuild-deps

Usage:
    # Run only tests affected by changes since last commit
    pytest --matt-affected

    # Re-run only tests that failed last time
    pytest --matt-failed

    # Rebuild dependency database
    pytest --matt-rebuild-deps
"""

from django_matt.testing.smart.differ import ASTBlockDiffer
from django_matt.testing.smart.tracker import TestDependencyTracker

__all__ = [
    "ASTBlockDiffer",
    "TestDependencyTracker",
]

"""Migration DX tools — unsafe DDL detection, rewriting, dependency visualization, and acceleration.

This module provides comprehensive migration tooling for large Django codebases:

1. **Safety Analysis** — Detect unsafe DDL patterns and suggest rewrites
2. **Dependency Visualization** — Graph migrations to understand complexity
3. **Squashing** — Smart migration consolidation with preview
4. **Baselines** — SQL dump-based setup to skip hundreds of migrations
5. **Parallel Execution** — Run independent migrations concurrently
6. **Profiling** — Understand why migrations are slow
"""

from django_matt.migration_tools.advisor import MigrationAdvisor, MigrationIssue
from django_matt.migration_tools.baseline import (
    BaselineInfo,
    CreateResult,
    LoadResult,
    MigrationBaseline,
    suggest_baseline_version,
)
from django_matt.migration_tools.graph import MigrationGraphRenderer
from django_matt.migration_tools.parallel import (
    MigrationWavePlanner,
    ParallelMigrateResult,
    ParallelMigrationExecutor,
    format_parallel_result,
)
from django_matt.migration_tools.squash import SmartSquasher, SquashPreview, SquashResult
from django_matt.migration_tools.state_hash import HashVerificationResult, StateHashVerifier
from django_matt.migration_tools.stats import (
    MigrationProfile,
    MigrationProfiler,
    MigrationRunStats,
    MigrationTimer,
    ProjectMigrationStats,
    format_profiles,
    format_project_stats,
)

__all__ = [
    # Advisor
    "MigrationAdvisor",
    "MigrationIssue",
    # Graph
    "MigrationGraphRenderer",
    # Squash
    "SmartSquasher",
    "SquashPreview",
    "SquashResult",
    # State Hash
    "StateHashVerifier",
    "HashVerificationResult",
    # Baseline
    "MigrationBaseline",
    "BaselineInfo",
    "CreateResult",
    "LoadResult",
    "suggest_baseline_version",
    # Parallel
    "ParallelMigrationExecutor",
    "MigrationWavePlanner",
    "ParallelMigrateResult",
    "format_parallel_result",
    # Stats
    "MigrationProfiler",
    "MigrationProfile",
    "MigrationTimer",
    "MigrationRunStats",
    "ProjectMigrationStats",
    "format_project_stats",
    "format_profiles",
]

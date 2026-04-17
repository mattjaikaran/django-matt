"""
Code advisor — health scoring and LLM-ready refactoring prompts.

Builds on the review/ engine to provide actionable, trending code quality metrics.
"""

from django_matt.advisor.health import CodeHealthScorer, FileHealth, HealthTrend, ProjectHealth
from django_matt.advisor.prompts import RefactorPrompt, RefactorPromptGenerator

__all__ = [
    "CodeHealthScorer",
    "FileHealth",
    "HealthTrend",
    "ProjectHealth",
    "RefactorPrompt",
    "RefactorPromptGenerator",
]

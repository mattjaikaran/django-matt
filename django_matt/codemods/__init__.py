"""
Django Matt Codemods - Automated migration from DRF, Django Ninja, and FastAPI.

AST-based source code transformations that convert existing framework code
to django-matt equivalents with confidence scoring and diff previews.

Usage:
    from django_matt.codemods import CodemodEngine

    engine = CodemodEngine()
    results = engine.run_directory("./myapp", framework="auto", dry_run=True)
    for path, result in results.items():
        print(f"{path}: {result.confidence:.0%} confidence")
        for change in result.changes:
            print(f"  - {change}")
"""

from django_matt.codemods.base import Codemod, CodemodResult
from django_matt.codemods.drf import DRFCodemods
from django_matt.codemods.engine import CodemodEngine
from django_matt.codemods.fastapi import FastAPICodemods
from django_matt.codemods.ninja import NinjaCodemods
from django_matt.codemods.ninja_extra import NinjaExtraCodemods

__all__ = [
    "Codemod",
    "CodemodResult",
    "CodemodEngine",
    "DRFCodemods",
    "NinjaCodemods",
    "NinjaExtraCodemods",
    "FastAPICodemods",
]

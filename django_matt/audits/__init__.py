"""
AI-Assisted Codebase Audits.

Provides LLM/AI agent helpers for optimizing django-matt projects with
structured prompts, audit commands, and actionable recommendations.

Example:
    >>> from django_matt.audits import run_audit, AuditLevel
    >>> results = run_audit("security", level=AuditLevel.STRICT)
    >>> for finding in results.findings:
    ...     print(f"[{finding.severity}] {finding.message}")
"""

from .framework import (
    AuditCategory,
    AuditConfig,
    AuditFinding,
    AuditLevel,
    AuditReport,
    AuditResult,
    AuditSeverity,
    BaseAuditor,
    run_audit,
)

__all__ = [
    "AuditCategory",
    "AuditConfig",
    "AuditFinding",
    "AuditLevel",
    "AuditReport",
    "AuditResult",
    "AuditSeverity",
    "BaseAuditor",
    "run_audit",
]

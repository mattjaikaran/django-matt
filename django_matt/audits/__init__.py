"""
AI-Assisted Codebase Quality Audits — static analysis and fix generation.

Provides pluggable auditors for security, performance, scalability,
bundle size, best practices, and maintainability. Includes LLM prompt
helpers, MCP tool definitions, and auto-fix diff generation.

For operational audit logging (model change tracking, user action history),
see the sibling package: django_matt.audit

Disambiguation:
  - django_matt.audits.AuditSeverity = code-quality finding severity (LOW..CRITICAL)
  - django_matt.audit.AuditSeverity = operational log level (DEBUG..CRITICAL)
  - Prefer aliases: FindingSeverity (here), LogSeverity (in audit)

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
    FindingSeverity,
    BaseAuditor,
)

__all__ = [
    "AuditCategory",
    "AuditConfig",
    "AuditFinding",
    "AuditLevel",
    "AuditReport",
    "AuditResult",
    "FindingSeverity",
    "BaseAuditor",
    "run_audit",
]

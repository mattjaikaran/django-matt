"""
Built-in auditors for django-matt.

Each auditor focuses on a specific category of issues.
"""

from .best_practices import BestPracticesAuditor
from .bundle_size import BundleSizeAuditor
from .maintainability import MaintainabilityAuditor
from .performance import PerformanceAuditor
from .scalability import ScalabilityAuditor
from .security import SecurityAuditor

__all__ = [
    "BestPracticesAuditor",
    "BundleSizeAuditor",
    "MaintainabilityAuditor",
    "PerformanceAuditor",
    "ScalabilityAuditor",
    "SecurityAuditor",
]

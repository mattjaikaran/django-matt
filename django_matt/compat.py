"""
Django version detection constants.

Single source of truth for version checks used across the framework.
"""

import django

DJANGO_VERSION = tuple(map(int, django.__version__.split(".")[:2]))
DJANGO_5_1_PLUS = DJANGO_VERSION >= (5, 1)
DJANGO_5_2_PLUS = DJANGO_VERSION >= (5, 2)
DJANGO_6_0_PLUS = DJANGO_VERSION >= (6, 0)

__all__ = [
    "DJANGO_5_1_PLUS",
    "DJANGO_5_2_PLUS",
    "DJANGO_6_0_PLUS",
    "DJANGO_VERSION",
]

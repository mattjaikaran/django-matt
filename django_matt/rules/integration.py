"""
Integration between predicate rules and django-matt's permission system.

Bridges :class:`~django_matt.rules.predicates.Predicate` with
:class:`~django_matt.permissions.base.BasePermission` so predicates
can be used anywhere ``permission_classes`` is accepted.

Usage::

    from django_matt.rules.integration import PredicatePermission
    from django_matt.rules.builtins import is_owner, is_superuser


    class PostController(APIController):
        permission_classes = [PredicatePermission(is_owner | is_superuser)]

Or with the shorthand class attribute::

    class PostController(APIController):
        permission_predicates = [is_owner | is_superuser]
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from django_matt.permissions.base import BasePermission
from django_matt.rules.predicates import Predicate


class PredicatePermission(BasePermission):
    """Wraps a :class:`Predicate` as a django-matt ``BasePermission``.

    Supports both view-level and object-level checks — the predicate
    receives ``(user,)`` for view-level and ``(user, obj)`` for
    object-level.
    """

    def __init__(self, pred: Predicate, *, message: str | None = None) -> None:
        self.pred = pred
        if message is not None:
            self.message = message  # type: ignore[assignment]

    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        user = getattr(request, "user", None)
        return self.pred.test(user)

    def has_object_permission(self, request: HttpRequest, view: Any, obj: Any) -> bool:
        user = getattr(request, "user", None)
        return self.pred.test(user, obj)

    def __repr__(self) -> str:
        return f"PredicatePermission({self.pred!r})"

"""
Built-in predicates for common authorization patterns.

All predicates accept ``(user, *args, **kwargs)`` — the first positional
arg after *user* is typically the object being checked (for object-level
predicates like :data:`is_owner`).
"""

from __future__ import annotations

from typing import Any

from django_matt.rules.predicates import Predicate, predicate


@predicate
def is_authenticated(user: Any) -> bool:
    """True when the user is authenticated."""
    return getattr(user, "is_authenticated", False)


@predicate
def is_superuser(user: Any) -> bool:
    """True when the user is a superuser."""
    if not getattr(user, "is_authenticated", False):
        return False
    return getattr(user, "is_superuser", False)


@predicate
def is_staff(user: Any) -> bool:
    """True when the user is staff."""
    if not getattr(user, "is_authenticated", False):
        return False
    return getattr(user, "is_staff", False)


@predicate
def is_active(user: Any) -> bool:
    """True when the user is active."""
    return getattr(user, "is_active", False)


@predicate
def is_owner(user: Any, obj: Any = None) -> bool:
    """True when *user* owns *obj*.

    Checks ``obj.owner``, ``obj.user``, and ``obj.created_by`` in order.
    Compares by ``pk`` when the field is a model instance.
    """
    if obj is None:
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    for attr in ("owner", "user", "created_by"):
        value = getattr(obj, attr, None)
        if value is not None:
            if hasattr(value, "pk"):
                return value.pk == user.pk
            return value == user
    return False


def is_group_member(group_name: str) -> Predicate:
    """Return a predicate that checks membership in *group_name*."""

    @predicate(name=f"is_group_member:{group_name}")
    def check(user: Any) -> bool:
        if not getattr(user, "is_authenticated", False):
            return False
        groups = getattr(user, "groups", None)
        if groups is None:
            return False
        return groups.filter(name=group_name).exists()

    return check


def has_perm(perm: str) -> Predicate:
    """Return a predicate that checks a Django permission string."""

    @predicate(name=f"has_perm:{perm}")
    def check(user: Any) -> bool:
        if not getattr(user, "is_authenticated", False):
            return False
        return user.has_perm(perm)

    return check

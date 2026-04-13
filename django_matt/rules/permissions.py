"""
Global permission registry backed by predicates.

Register named permission rules and test them by name::

    from django_matt.rules import add_perm, test_rule
    from django_matt.rules.builtins import is_authenticated, is_owner

    add_perm("posts.edit", is_owner | is_authenticated)
    test_rule("posts.edit", request.user, post)
"""

from __future__ import annotations

from typing import Any

from django_matt.rules.predicates import Predicate

_registry: dict[str, Predicate] = {}


def add_perm(name: str, pred: Predicate) -> None:
    """Register *pred* under *name*, replacing any existing entry."""
    if not isinstance(pred, Predicate):
        raise TypeError(f"Expected Predicate, got {type(pred).__name__}")
    _registry[name] = pred


def remove_perm(name: str) -> None:
    """Remove the rule registered under *name*.

    Raises :class:`KeyError` if *name* is not registered.
    """
    del _registry[name]


def has_perm(name: str) -> Predicate | None:
    """Return the predicate registered under *name*, or ``None``."""
    return _registry.get(name)


def perm_exists(name: str) -> bool:
    """Return ``True`` if *name* is registered."""
    return name in _registry


def test_rule(name: str, user: Any, *args: Any, **kwargs: Any) -> bool:
    """Test the named rule against *user*.

    Returns ``False`` when *name* is not registered (fail-closed).
    """
    pred = _registry.get(name)
    if pred is None:
        return False
    return pred.test(user, *args, **kwargs)


def clear() -> None:
    """Remove all registered rules (useful in tests)."""
    _registry.clear()

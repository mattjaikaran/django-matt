"""
Django authentication backend that delegates to the predicate registry.

Add to ``AUTHENTICATION_BACKENDS``::

    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
        "django_matt.rules.backends.RulesBackend",
    ]

Then any ``user.has_perm("app.action")`` call will consult the predicate
registry in addition to Django's built-in permission tables.
"""

from __future__ import annotations

from typing import Any

from django_matt.rules.permissions import _registry, test_rule


class RulesBackend:
    """Authentication backend that resolves permissions via predicates."""

    def authenticate(
        self,
        request: Any = None,
        **kwargs: Any,
    ) -> None:
        """This backend does not handle authentication."""
        return

    def has_perm(
        self,
        user_obj: Any,
        perm: str,
        obj: Any = None,
    ) -> bool:
        """Check *perm* against the predicate registry.

        Returns ``False`` (rather than raising) when the permission is
        not registered — this lets the next backend in the chain decide.
        """
        if obj is not None:
            return test_rule(perm, user_obj, obj)
        return test_rule(perm, user_obj)

    def has_module_perms(self, user_obj: Any, app_label: str) -> bool:
        """Return ``True`` if any rule is registered under *app_label*."""
        prefix = f"{app_label}."
        return any(name.startswith(prefix) for name in _registry)

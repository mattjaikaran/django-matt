"""
Django CBV mixins for predicate-based permission checking.

These integrate predicate rules with standard Django class-based views.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from django_matt.rules.permissions import test_rule
from django_matt.rules.predicates import Predicate


class PermissionRequiredMixin:
    """Check named predicate rules before dispatching a Django CBV.

    Set :attr:`permission_required` to a single rule name or a list of
    rule names.  All rules must pass (AND semantics).  If any rule fails,
    :meth:`handle_no_permission` raises :class:`~django.core.exceptions.PermissionDenied`.

    Example::

        class PostUpdateView(PermissionRequiredMixin, UpdateView):
            permission_required = "posts.change"
    """

    permission_required: str | list[str] = ""
    raise_exception: bool = True

    def get_permission_required(self) -> list[str]:
        if isinstance(self.permission_required, str):
            return [self.permission_required] if self.permission_required else []
        return list(self.permission_required)

    def has_permission(self) -> bool:
        request: HttpRequest = self.request  # type: ignore[attr-defined]
        user = getattr(request, "user", None)
        obj = self._get_permission_object()
        for name in self.get_permission_required():
            if not test_rule(name, user, obj):
                return False
        return True

    def _get_permission_object(self) -> Any:
        """Return the object to pass into the predicate, if any."""
        if hasattr(self, "get_object"):
            try:
                return self.get_object()  # type: ignore[attr-defined]
            except Exception:
                return None
        return None

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        if not self.has_permission():
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]

    def handle_no_permission(self) -> Any:
        if self.raise_exception:
            raise PermissionDenied
        from django.conf import settings
        from django.shortcuts import redirect

        return redirect(getattr(settings, "LOGIN_URL", "/accounts/login/"))


class ObjectPermissionMixin:
    """Per-object predicate checking for Django CBVs.

    Set :attr:`object_permission` to a :class:`Predicate` (or composition).
    The predicate receives ``(user, obj)`` after the object is fetched.

    Example::

        class PostDeleteView(ObjectPermissionMixin, DeleteView):
            object_permission = is_owner | is_superuser
    """

    object_permission: Predicate | None = None
    raise_exception: bool = True

    def get_object(self, *args: Any, **kwargs: Any) -> Any:
        obj = super().get_object(*args, **kwargs)  # type: ignore[misc]
        if self.object_permission is not None:
            request: HttpRequest = self.request  # type: ignore[attr-defined]
            user = getattr(request, "user", None)
            if not self.object_permission.test(user, obj):
                self._handle_object_no_permission()
        return obj

    def _handle_object_no_permission(self) -> None:
        if self.raise_exception:
            raise PermissionDenied
        from django.conf import settings
        from django.shortcuts import redirect

        redirect(getattr(settings, "LOGIN_URL", "/accounts/login/"))

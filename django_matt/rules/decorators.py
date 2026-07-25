"""
Function-view decorators for predicate-based authorization.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

from django_matt.rules.permissions import test_rule
from django_matt.rules.predicates import Predicate


def permission_required(
    perm_name: str,
    *,
    fn: Callable[..., Any] | None = None,
    raise_exception: bool = True,
) -> Callable[..., Any]:
    """Decorator that checks a named rule from the predicate registry.

    Usage::

        @permission_required("posts.change")
        def edit_post(request, pk): ...

    When the rule fails, raises :class:`~django.core.exceptions.PermissionDenied`
    (or returns 403 response if *raise_exception* is ``False``).
    """

    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            user = getattr(request, "user", None)
            if not test_rule(perm_name, user):
                if raise_exception:
                    raise PermissionDenied
                return HttpResponse("Permission denied.", status=403)
            return view_func(request, *args, **kwargs)

        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator


def predicate_required(
    pred: Predicate,
    *,
    raise_exception: bool = True,
) -> Callable[..., Any]:
    """Decorator that checks a predicate directly (no registry lookup).

    Usage::

        @predicate_required(is_owner | is_admin)
        def delete_post(request, pk): ...
    """

    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            user = getattr(request, "user", None)
            if not pred.test(user, *args, **kwargs):
                if raise_exception:
                    raise PermissionDenied
                return HttpResponse("Permission denied.", status=403)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator

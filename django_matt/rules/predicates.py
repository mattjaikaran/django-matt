"""
Predicate-based composable boolean authorization.

Predicates are lightweight callable objects that can be composed with
``&`` (AND), ``|`` (OR), and ``~`` (NOT) operators to build complex
authorization rules declaratively.

Example::

    from django_matt.rules import predicate

    @predicate
    def is_author(user, obj):
        return obj.author == user

    @predicate
    def is_editor(user, obj):
        return user.groups.filter(name="editors").exists()

    can_edit = is_author | is_editor
    can_edit.test(request.user, post)  # True/False
"""

from __future__ import annotations

import functools
from typing import Any, Callable, overload


class Predicate:
    """A composable boolean predicate for authorization checks.

    Predicates wrap a callable ``(user, *args, **kwargs) -> bool`` and
    support composition via ``&``, ``|``, and ``~`` operators.

    When *bind* is ``True`` the predicate instance is passed as the first
    argument to the wrapped function (useful for per-request caching on
    the predicate object).
    """

    __slots__ = ("__dict__", "__wrapped__", "bind", "fn", "name")

    def __init__(
        self,
        fn: Callable[..., bool],
        name: str | None = None,
        *,
        bind: bool = False,
    ) -> None:
        self.fn = fn
        self.name = name or getattr(fn, "__name__", repr(fn))
        self.bind = bind
        functools.update_wrapper(self, fn)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def test(self, user: Any, *args: Any, **kwargs: Any) -> bool:
        """Evaluate the predicate for *user* and optional context."""
        if self.bind:
            return bool(self.fn(self, user, *args, **kwargs))
        return bool(self.fn(user, *args, **kwargs))

    def __call__(self, user: Any, *args: Any, **kwargs: Any) -> bool:
        """Shorthand for :meth:`test`."""
        return self.test(user, *args, **kwargs)

    # ------------------------------------------------------------------
    # Composition operators
    # ------------------------------------------------------------------

    def __and__(self, other: Predicate) -> Predicate:
        if not isinstance(other, Predicate):
            return NotImplemented
        return _AndPredicate(self, other)

    def __or__(self, other: Predicate) -> Predicate:
        if not isinstance(other, Predicate):
            return NotImplemented
        return _OrPredicate(self, other)

    def __invert__(self) -> Predicate:
        return _NotPredicate(self)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<Predicate: {self.name}>"


# ------------------------------------------------------------------
# Composite predicates (internal)
# ------------------------------------------------------------------


class _AndPredicate(Predicate):
    """Short-circuiting AND of two predicates."""

    __slots__ = ("left", "right")

    def __init__(self, left: Predicate, right: Predicate) -> None:
        self.left = left
        self.right = right
        self.fn = self._eval
        self.name = f"({left.name} & {right.name})"
        self.bind = False

    def _eval(self, user: Any, *args: Any, **kwargs: Any) -> bool:
        return self.left.test(user, *args, **kwargs) and self.right.test(
            user, *args, **kwargs
        )

    def test(self, user: Any, *args: Any, **kwargs: Any) -> bool:
        return self._eval(user, *args, **kwargs)

    def __repr__(self) -> str:
        return f"({self.left!r} & {self.right!r})"


class _OrPredicate(Predicate):
    """Short-circuiting OR of two predicates."""

    __slots__ = ("left", "right")

    def __init__(self, left: Predicate, right: Predicate) -> None:
        self.left = left
        self.right = right
        self.fn = self._eval
        self.name = f"({left.name} | {right.name})"
        self.bind = False

    def _eval(self, user: Any, *args: Any, **kwargs: Any) -> bool:
        return self.left.test(user, *args, **kwargs) or self.right.test(
            user, *args, **kwargs
        )

    def test(self, user: Any, *args: Any, **kwargs: Any) -> bool:
        return self._eval(user, *args, **kwargs)

    def __repr__(self) -> str:
        return f"({self.left!r} | {self.right!r})"


class _NotPredicate(Predicate):
    """Negation of a predicate."""

    __slots__ = ("inner",)

    def __init__(self, inner: Predicate) -> None:
        self.inner = inner
        self.fn = self._eval
        self.name = f"~{inner.name}"
        self.bind = False

    def _eval(self, user: Any, *args: Any, **kwargs: Any) -> bool:
        return not self.inner.test(user, *args, **kwargs)

    def test(self, user: Any, *args: Any, **kwargs: Any) -> bool:
        return self._eval(user, *args, **kwargs)

    def __repr__(self) -> str:
        return f"(~{self.inner!r})"


# ------------------------------------------------------------------
# Decorator factory
# ------------------------------------------------------------------


@overload
def predicate(fn: Callable[..., bool], /) -> Predicate: ...


@overload
def predicate(
    *, name: str | None = None, bind: bool = False
) -> Callable[[Callable[..., bool]], Predicate]: ...


def predicate(
    fn: Callable[..., bool] | None = None,
    /,
    *,
    name: str | None = None,
    bind: bool = False,
) -> Predicate | Callable[[Callable[..., bool]], Predicate]:
    """Decorator that turns a function into a :class:`Predicate`.

    Can be used bare or with keyword arguments::

        @predicate
        def is_active(user):
            return user.is_active

        @predicate(name="cached_check", bind=True)
        def expensive_check(self, user, obj):
            # ``self`` is the Predicate instance
            ...
    """
    if fn is not None:
        return Predicate(fn, name=name, bind=bind)

    def wrapper(fn: Callable[..., bool]) -> Predicate:
        return Predicate(fn, name=name, bind=bind)

    return wrapper


# ------------------------------------------------------------------
# Constant predicates
# ------------------------------------------------------------------

always_true = Predicate(lambda user, *a, **kw: True, name="always_true")
always_false = Predicate(lambda user, *a, **kw: False, name="always_false")
always_deny = always_false

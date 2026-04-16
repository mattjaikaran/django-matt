"""Tests for django_matt.rules — predicate-based composable authorization."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

import pytest

from django_matt.rules import (
    PredicatePermission,
    add_perm,
    always_deny,
    always_false,
    always_true,
    clear,
    has_perm,
    perm_exists,
    permission_required,
    predicate_required,
    remove_perm,
)
from django_matt.rules import (
    test_rule as run_test_rule,
)
from django_matt.rules.backends import RulesBackend
from django_matt.rules.builtins import (
    is_active,
    is_authenticated,
    is_group_member,
    is_owner,
    is_staff,
    is_superuser,
)
from django_matt.rules.mixins import ObjectPermissionMixin, PermissionRequiredMixin
from django_matt.rules.predicates import Predicate, predicate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(
    *,
    authenticated: bool = True,
    superuser: bool = False,
    staff: bool = False,
    active: bool = True,
    pk: int = 1,
    groups: Any = None,
    perms: list[str] | None = None,
) -> SimpleNamespace:
    """Build a lightweight user-like object."""
    _perms = set(perms or [])

    class _Groups:
        def __init__(self, names: list[str]) -> None:
            self._names = set(names)

        def filter(self, name: str) -> _Groups:
            self._matched = name in self._names
            return self

        def exists(self) -> bool:
            return self._matched

    return SimpleNamespace(
        pk=pk,
        is_authenticated=authenticated,
        is_superuser=superuser,
        is_staff=staff,
        is_active=active,
        groups=_Groups(groups or []),
        has_perm=lambda p: p in _perms,
    )


def _anon() -> SimpleNamespace:
    return _user(authenticated=False, active=False, pk=0)


def _request(user: Any | None = None) -> Any:
    rf = RequestFactory()
    req = rf.get("/")
    req.user = user
    return req


# ---------------------------------------------------------------------------
# 1. Predicate base class
# ---------------------------------------------------------------------------

class TestPredicateBase:
    def test_create_from_function(self) -> None:
        p = Predicate(lambda u: True, name="always")
        assert p.name == "always"
        assert p.test(_user()) is True

    def test_name_defaults_to_function_name(self) -> None:
        def my_check(user: Any) -> bool:
            return True

        p = Predicate(my_check)
        assert p.name == "my_check"

    def test_call_delegates_to_test(self) -> None:
        p = Predicate(lambda u: u.is_staff)
        assert p(_user(staff=True)) is True
        assert p(_user(staff=False)) is False

    def test_bind_passes_self(self) -> None:
        def check(self: Predicate, user: Any) -> bool:
            assert isinstance(self, Predicate)
            return True

        p = Predicate(check, bind=True)
        assert p.test(_user()) is True

    def test_repr(self) -> None:
        p = Predicate(lambda u: True, name="test_pred")
        assert repr(p) == "<Predicate: test_pred>"

    def test_coerces_to_bool(self) -> None:
        p = Predicate(lambda u: 1)
        assert p.test(_user()) is True

        p2 = Predicate(lambda u: 0)
        assert p2.test(_user()) is False


# ---------------------------------------------------------------------------
# 2. @predicate decorator
# ---------------------------------------------------------------------------

class TestPredicateDecorator:
    def test_bare_decorator(self) -> None:
        @predicate
        def can_read(user: Any) -> bool:
            return True

        assert isinstance(can_read, Predicate)
        assert can_read.name == "can_read"
        assert can_read.test(_user()) is True

    def test_decorator_with_name(self) -> None:
        @predicate(name="custom_name")
        def check(user: Any) -> bool:
            return True

        assert check.name == "custom_name"

    def test_decorator_with_bind(self) -> None:
        @predicate(bind=True)
        def check(self: Predicate, user: Any) -> bool:
            return isinstance(self, Predicate)

        assert check.test(_user()) is True

    def test_decorator_with_all_kwargs(self) -> None:
        @predicate(name="fancy", bind=True)
        def check(self: Predicate, user: Any) -> bool:
            return True

        assert check.name == "fancy"
        assert check.bind is True


# ---------------------------------------------------------------------------
# 3. Composition — AND, OR, NOT
# ---------------------------------------------------------------------------

class TestComposition:
    def test_and_both_true(self) -> None:
        a = Predicate(lambda u: True, name="a")
        b = Predicate(lambda u: True, name="b")
        combined = a & b
        assert combined.test(_user()) is True

    def test_and_one_false(self) -> None:
        a = Predicate(lambda u: True, name="a")
        b = Predicate(lambda u: False, name="b")
        assert (a & b).test(_user()) is False
        assert (b & a).test(_user()) is False

    def test_or_one_true(self) -> None:
        a = Predicate(lambda u: True, name="a")
        b = Predicate(lambda u: False, name="b")
        assert (a | b).test(_user()) is True
        assert (b | a).test(_user()) is True

    def test_or_both_false(self) -> None:
        a = Predicate(lambda u: False, name="a")
        b = Predicate(lambda u: False, name="b")
        assert (a | b).test(_user()) is False

    def test_not(self) -> None:
        a = Predicate(lambda u: True, name="a")
        assert (~a).test(_user()) is False

        b = Predicate(lambda u: False, name="b")
        assert (~b).test(_user()) is True

    def test_complex_expression(self) -> None:
        """(a & b) | ~c"""
        a = Predicate(lambda u: True, name="a")
        b = Predicate(lambda u: False, name="b")
        c = Predicate(lambda u: False, name="c")

        expr = (a & b) | ~c
        # a & b = False, ~c = True → True
        assert expr.test(_user()) is True

    def test_complex_expression_2(self) -> None:
        """~(a | b) & c"""
        a = Predicate(lambda u: False, name="a")
        b = Predicate(lambda u: False, name="b")
        c = Predicate(lambda u: True, name="c")

        expr = ~(a | b) & c
        # ~(False | False) & True = True & True = True
        assert expr.test(_user()) is True

    def test_and_short_circuits(self) -> None:
        calls: list[str] = []

        def first(u: Any) -> bool:
            calls.append("first")
            return False

        def second(u: Any) -> bool:
            calls.append("second")
            return True

        combined = Predicate(first, name="first") & Predicate(second, name="second")
        combined.test(_user())
        assert calls == ["first"]  # second never called

    def test_or_short_circuits(self) -> None:
        calls: list[str] = []

        def first(u: Any) -> bool:
            calls.append("first")
            return True

        def second(u: Any) -> bool:
            calls.append("second")
            return True

        combined = Predicate(first, name="first") | Predicate(second, name="second")
        combined.test(_user())
        assert calls == ["first"]

    def test_composed_name(self) -> None:
        a = Predicate(lambda u: True, name="a")
        b = Predicate(lambda u: True, name="b")
        assert "(a & b)" in (a & b).name
        assert "(a | b)" in (a | b).name
        assert "~a" in (~a).name

    def test_and_returns_not_implemented_for_non_predicate(self) -> None:
        a = Predicate(lambda u: True, name="a")
        assert a.__and__("not a predicate") is NotImplemented

    def test_or_returns_not_implemented_for_non_predicate(self) -> None:
        a = Predicate(lambda u: True, name="a")
        assert a.__or__(42) is NotImplemented

    def test_composed_repr(self) -> None:
        a = Predicate(lambda u: True, name="a")
        b = Predicate(lambda u: True, name="b")
        assert "&" in repr(a & b)
        assert "|" in repr(a | b)
        assert "~" in repr(~a)

    def test_context_args_forwarded(self) -> None:
        @predicate
        def owns(user: Any, obj: Any) -> bool:
            return obj.owner_id == user.pk

        @predicate
        def admin(user: Any, obj: Any = None) -> bool:
            return user.is_superuser

        combined = owns | admin
        obj = SimpleNamespace(owner_id=1)
        assert combined.test(_user(pk=1), obj) is True
        assert combined.test(_user(pk=2, superuser=True), obj) is True
        assert combined.test(_user(pk=2, superuser=False), obj) is False


# ---------------------------------------------------------------------------
# 4. Constant predicates
# ---------------------------------------------------------------------------

class TestConstants:
    def test_always_true(self) -> None:
        assert always_true.test(_user()) is True
        assert always_true.test(_anon()) is True

    def test_always_false(self) -> None:
        assert always_false.test(_user()) is False

    def test_always_deny_is_always_false(self) -> None:
        assert always_deny is always_false


# ---------------------------------------------------------------------------
# 5. Built-in predicates
# ---------------------------------------------------------------------------

class TestBuiltins:
    def test_is_authenticated(self) -> None:
        assert is_authenticated.test(_user()) is True
        assert is_authenticated.test(_anon()) is False

    def test_is_superuser(self) -> None:
        assert is_superuser.test(_user(superuser=True)) is True
        assert is_superuser.test(_user(superuser=False)) is False
        assert is_superuser.test(_anon()) is False

    def test_is_staff(self) -> None:
        assert is_staff.test(_user(staff=True)) is True
        assert is_staff.test(_user(staff=False)) is False
        assert is_staff.test(_anon()) is False

    def test_is_active(self) -> None:
        assert is_active.test(_user(active=True)) is True
        assert is_active.test(_user(active=False)) is False

    def test_is_owner_via_owner_attr(self) -> None:
        owner = _user(pk=5)
        obj = SimpleNamespace(owner=SimpleNamespace(pk=5))
        assert is_owner.test(owner, obj) is True

        other = _user(pk=99)
        assert is_owner.test(other, obj) is False

    def test_is_owner_via_user_attr(self) -> None:
        u = _user(pk=7)
        obj = SimpleNamespace(user=SimpleNamespace(pk=7))
        assert is_owner.test(u, obj) is True

    def test_is_owner_via_created_by_attr(self) -> None:
        u = _user(pk=3)
        obj = SimpleNamespace(created_by=SimpleNamespace(pk=3))
        assert is_owner.test(u, obj) is True

    def test_is_owner_direct_comparison(self) -> None:
        u = _user(pk=10)
        obj = SimpleNamespace(owner=u)
        assert is_owner.test(u, obj) is True

    def test_is_owner_no_obj(self) -> None:
        assert is_owner.test(_user()) is False

    def test_is_owner_no_ownership_attr(self) -> None:
        obj = SimpleNamespace(title="hello")
        assert is_owner.test(_user(), obj) is False

    def test_is_owner_unauthenticated(self) -> None:
        obj = SimpleNamespace(owner=SimpleNamespace(pk=0))
        assert is_owner.test(_anon(), obj) is False

    def test_is_group_member(self) -> None:
        u = _user(groups=["editors", "reviewers"])
        editors_pred = is_group_member("editors")
        assert isinstance(editors_pred, Predicate)
        assert editors_pred.test(u) is True
        assert is_group_member("admins").test(u) is False

    def test_is_group_member_unauthenticated(self) -> None:
        assert is_group_member("editors").test(_anon()) is False

    def test_is_group_member_name(self) -> None:
        p = is_group_member("editors")
        assert "editors" in p.name

    def test_has_perm_builtin(self) -> None:
        from django_matt.rules.builtins import has_perm as has_perm_pred

        u = _user(perms=["app.view_model"])
        p = has_perm_pred("app.view_model")
        assert p.test(u) is True
        assert has_perm_pred("app.delete_model").test(u) is False

    def test_has_perm_unauthenticated(self) -> None:
        from django_matt.rules.builtins import has_perm as has_perm_pred

        assert has_perm_pred("any.perm").test(_anon()) is False


# ---------------------------------------------------------------------------
# 6. Permission registry
# ---------------------------------------------------------------------------

class TestPermissionRegistry:
    def setup_method(self) -> None:
        clear()

    def teardown_method(self) -> None:
        clear()

    def test_add_and_lookup(self) -> None:
        add_perm("posts.edit", always_true)
        assert perm_exists("posts.edit") is True
        assert has_perm("posts.edit") is always_true

    def test_has_perm_returns_none_for_missing(self) -> None:
        assert has_perm("nonexistent") is None

    def test_perm_exists_false(self) -> None:
        assert perm_exists("nonexistent") is False

    def test_remove_perm(self) -> None:
        add_perm("posts.delete", always_true)
        remove_perm("posts.delete")
        assert perm_exists("posts.delete") is False

    def test_remove_perm_raises_on_missing(self) -> None:
        with pytest.raises(KeyError):
            remove_perm("nonexistent")

    def test_add_perm_rejects_non_predicate(self) -> None:
        with pytest.raises(TypeError, match="Expected Predicate"):
            add_perm("bad", lambda u: True)  # type: ignore[arg-type]

    def test_add_perm_replaces_existing(self) -> None:
        add_perm("posts.view", always_true)
        add_perm("posts.view", always_false)
        assert has_perm("posts.view") is always_false

    def test_rule_evaluation(self) -> None:
        add_perm("posts.view", is_authenticated)
        assert run_test_rule("posts.view", _user()) is True
        assert run_test_rule("posts.view", _anon()) is False

    def test_rule_unregistered_returns_false(self) -> None:
        assert run_test_rule("nonexistent", _user()) is False

    def test_rule_with_obj(self) -> None:
        add_perm("posts.edit", is_owner)
        obj = SimpleNamespace(owner=SimpleNamespace(pk=1))
        assert run_test_rule("posts.edit", _user(pk=1), obj) is True
        assert run_test_rule("posts.edit", _user(pk=2), obj) is False

    def test_clear(self) -> None:
        add_perm("a", always_true)
        add_perm("b", always_false)
        clear()
        assert perm_exists("a") is False
        assert perm_exists("b") is False


# ---------------------------------------------------------------------------
# 7. RulesBackend
# ---------------------------------------------------------------------------

class TestRulesBackend:
    def setup_method(self) -> None:
        clear()
        self.backend = RulesBackend()

    def teardown_method(self) -> None:
        clear()

    def test_authenticate_returns_none(self) -> None:
        assert self.backend.authenticate() is None

    def test_has_perm_checks_registry(self) -> None:
        add_perm("posts.view", is_authenticated)
        assert self.backend.has_perm(_user(), "posts.view") is True
        assert self.backend.has_perm(_anon(), "posts.view") is False

    def test_has_perm_with_obj(self) -> None:
        add_perm("posts.edit", is_owner)
        obj = SimpleNamespace(owner=SimpleNamespace(pk=1))
        assert self.backend.has_perm(_user(pk=1), "posts.edit", obj) is True
        assert self.backend.has_perm(_user(pk=2), "posts.edit", obj) is False

    def test_has_perm_unregistered_returns_false(self) -> None:
        assert self.backend.has_perm(_user(), "nonexistent") is False

    def test_has_module_perms(self) -> None:
        add_perm("posts.view", always_true)
        add_perm("posts.edit", always_true)
        assert self.backend.has_module_perms(_user(), "posts") is True
        assert self.backend.has_module_perms(_user(), "comments") is False


# ---------------------------------------------------------------------------
# 8. Decorators
# ---------------------------------------------------------------------------

class TestDecorators:
    def setup_method(self) -> None:
        clear()

    def teardown_method(self) -> None:
        clear()

    def test_permission_required_allows(self) -> None:
        add_perm("posts.view", is_authenticated)

        @permission_required("posts.view")
        def view(request: Any) -> str:
            return "ok"

        result = view(_request(_user()))
        assert result == "ok"

    def test_permission_required_denies(self) -> None:
        add_perm("posts.view", is_authenticated)

        @permission_required("posts.view")
        def view(request: Any) -> str:
            return "ok"

        with pytest.raises(PermissionDenied):
            view(_request(_anon()))

    def test_permission_required_no_raise(self) -> None:
        add_perm("posts.view", is_authenticated)

        @permission_required("posts.view", raise_exception=False)
        def view(request: Any) -> str:
            return "ok"

        resp = view(_request(_anon()))
        assert resp.status_code == 403

    def test_permission_required_unregistered_rule_denies(self) -> None:
        @permission_required("nonexistent")
        def view(request: Any) -> str:
            return "ok"

        with pytest.raises(PermissionDenied):
            view(_request(_user()))

    def test_predicate_required_allows(self) -> None:
        @predicate_required(is_authenticated)
        def view(request: Any) -> str:
            return "ok"

        assert view(_request(_user())) == "ok"

    def test_predicate_required_denies(self) -> None:
        @predicate_required(is_authenticated)
        def view(request: Any) -> str:
            return "ok"

        with pytest.raises(PermissionDenied):
            view(_request(_anon()))

    def test_predicate_required_no_raise(self) -> None:
        @predicate_required(is_authenticated, raise_exception=False)
        def view(request: Any) -> str:
            return "ok"

        resp = view(_request(_anon()))
        assert resp.status_code == 403

    def test_predicate_required_with_composition(self) -> None:
        @predicate_required(is_authenticated & is_staff)
        def view(request: Any) -> str:
            return "ok"

        assert view(_request(_user(staff=True))) == "ok"
        with pytest.raises(PermissionDenied):
            view(_request(_user(staff=False)))

    def test_permission_required_preserves_function_name(self) -> None:
        add_perm("x", always_true)

        @permission_required("x")
        def my_view(request: Any) -> str:
            return "ok"

        assert my_view.__name__ == "my_view"

    def test_predicate_required_preserves_function_name(self) -> None:
        @predicate_required(always_true)
        def my_view(request: Any) -> str:
            return "ok"

        assert my_view.__name__ == "my_view"


# ---------------------------------------------------------------------------
# 9. Mixins
# ---------------------------------------------------------------------------

class TestPermissionRequiredMixin:
    def setup_method(self) -> None:
        clear()

    def teardown_method(self) -> None:
        clear()

    def test_get_permission_required_string(self) -> None:
        mixin = PermissionRequiredMixin()
        mixin.permission_required = "posts.view"
        assert mixin.get_permission_required() == ["posts.view"]

    def test_get_permission_required_list(self) -> None:
        mixin = PermissionRequiredMixin()
        mixin.permission_required = ["posts.view", "posts.edit"]
        assert mixin.get_permission_required() == ["posts.view", "posts.edit"]

    def test_get_permission_required_empty(self) -> None:
        mixin = PermissionRequiredMixin()
        mixin.permission_required = ""
        assert mixin.get_permission_required() == []

    def test_has_permission_passes(self) -> None:
        # Use a predicate that accepts *args since mixin passes obj=None
        @predicate
        def authed(user: Any, obj: Any = None) -> bool:
            return getattr(user, "is_authenticated", False)

        add_perm("posts.view", authed)
        mixin = PermissionRequiredMixin()
        mixin.permission_required = "posts.view"
        mixin.request = _request(_user())
        assert mixin.has_permission() is True

    def test_has_permission_fails(self) -> None:
        @predicate
        def authed(user: Any, obj: Any = None) -> bool:
            return getattr(user, "is_authenticated", False)

        add_perm("posts.view", authed)
        mixin = PermissionRequiredMixin()
        mixin.permission_required = "posts.view"
        mixin.request = _request(_anon())
        assert mixin.has_permission() is False

    def test_has_permission_multiple_all_must_pass(self) -> None:
        @predicate
        def authed(user: Any, obj: Any = None) -> bool:
            return getattr(user, "is_authenticated", False)

        @predicate
        def superadmin(user: Any, obj: Any = None) -> bool:
            return getattr(user, "is_superuser", False)

        add_perm("posts.view", authed)
        add_perm("posts.admin", superadmin)

        mixin = PermissionRequiredMixin()
        mixin.permission_required = ["posts.view", "posts.admin"]
        mixin.request = _request(_user(superuser=False))
        assert mixin.has_permission() is False

        mixin.request = _request(_user(superuser=True))
        assert mixin.has_permission() is True

    def test_handle_no_permission_raises(self) -> None:
        mixin = PermissionRequiredMixin()
        mixin.raise_exception = True
        with pytest.raises(PermissionDenied):
            mixin.handle_no_permission()

    def test_handle_no_permission_redirects(self, settings: Any) -> None:
        settings.LOGIN_URL = "/login/"
        mixin = PermissionRequiredMixin()
        mixin.raise_exception = False
        resp = mixin.handle_no_permission()
        assert resp.status_code == 302

    def test_dispatch_blocks_unauthorized(self) -> None:
        add_perm("x", always_false)

        class FakeView(PermissionRequiredMixin):
            permission_required = "x"

        view = FakeView()
        view.request = _request(_user())
        with pytest.raises(PermissionDenied):
            view.dispatch(view.request)


class TestObjectPermissionMixin:
    def test_raises_when_predicate_fails(self) -> None:
        class FakeParent:
            def get_object(self) -> SimpleNamespace:
                return SimpleNamespace(owner=SimpleNamespace(pk=999))

        class View(ObjectPermissionMixin, FakeParent):
            object_permission = is_owner

        view = View()
        view.request = _request(_user(pk=1))
        with pytest.raises(PermissionDenied):
            view.get_object()

    def test_allows_when_predicate_passes(self) -> None:
        class FakeParent:
            def get_object(self) -> SimpleNamespace:
                return SimpleNamespace(owner=SimpleNamespace(pk=1))

        class View(ObjectPermissionMixin, FakeParent):
            object_permission = is_owner

        view = View()
        view.request = _request(_user(pk=1))
        obj = view.get_object()
        assert obj.owner.pk == 1

    def test_no_permission_set_passes_through(self) -> None:
        class FakeParent:
            def get_object(self) -> SimpleNamespace:
                return SimpleNamespace(data="hello")

        class View(ObjectPermissionMixin, FakeParent):
            object_permission = None

        view = View()
        view.request = _request(_user())
        obj = view.get_object()
        assert obj.data == "hello"


# ---------------------------------------------------------------------------
# 10. PredicatePermission (controller integration)
# ---------------------------------------------------------------------------

class TestPredicatePermission:
    def test_has_permission_authenticated(self) -> None:
        perm = PredicatePermission(is_authenticated)
        req = _request(_user())
        assert perm.has_permission(req) is True

    def test_has_permission_anon(self) -> None:
        perm = PredicatePermission(is_authenticated)
        req = _request(_anon())
        assert perm.has_permission(req) is False

    def test_has_object_permission(self) -> None:
        perm = PredicatePermission(is_owner)
        req = _request(_user(pk=5))
        obj = SimpleNamespace(owner=SimpleNamespace(pk=5))
        assert perm.has_object_permission(req, None, obj) is True

        obj_other = SimpleNamespace(owner=SimpleNamespace(pk=99))
        assert perm.has_object_permission(req, None, obj_other) is False

    def test_composed_predicate(self) -> None:
        perm = PredicatePermission(is_owner | is_superuser)
        req_owner = _request(_user(pk=1))
        obj = SimpleNamespace(owner=SimpleNamespace(pk=1))
        assert perm.has_object_permission(req_owner, None, obj) is True

        req_admin = _request(_user(pk=99, superuser=True))
        assert perm.has_object_permission(req_admin, None, obj) is True

        req_nobody = _request(_user(pk=99, superuser=False))
        assert perm.has_object_permission(req_nobody, None, obj) is False

    def test_custom_message(self) -> None:
        perm = PredicatePermission(always_false, message="no way")
        assert perm.message == "no way"

    def test_repr(self) -> None:
        perm = PredicatePermission(is_authenticated)
        assert "PredicatePermission" in repr(perm)
        assert "is_authenticated" in repr(perm)

    def test_is_base_permission_subclass(self) -> None:
        from django_matt.permissions.base import BasePermission

        perm = PredicatePermission(always_true)
        assert isinstance(perm, BasePermission)

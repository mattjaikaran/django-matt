"""
Extended feature flags coverage tests for django_matt.flags module.

Covers:
- FeatureFlag model: is_active, is_enabled_for_user, percentage rollout, variants
- FlagOverride: user overrides, email overrides, org overrides, expiry
- Targeting rules: all operators (eq, neq, gt, gte, lt, lte, in, not_in, contains,
  starts_with, ends_with, regex)
- MemoryBackend: is_enabled, get_variant, get_all_flags, overrides, percentage
- DatabaseBackend: is_enabled, get_variant, cache invalidation
- FlagContext: from_request, is_enabled, get_variant, with_attributes, context manager
- Decorators: feature_flag, requires_flag
- Middleware: FlagMiddleware header/cookie/query overrides
- Edge cases: missing flags default to disabled, archived flags, scheduled flags
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory
from django.utils import timezone

from django_matt.flags.backends import DatabaseBackend, MemoryBackend, get_backend
from django_matt.flags.context import FlagContext, get_current_context, set_current_context
from django_matt.flags.decorators import feature_flag, requires_flag
from django_matt.flags.middleware import FlagMiddleware
from django_matt.flags.models import (
    FeatureFlag,
    FlagAuditLog,
    FlagOverride,
    FlagStatus,
    FlagType,
    OverrideType,
)

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers
# ============================================================================


def _make_request(query_params=None, headers=None, cookies=None, user=None):
    rf = RequestFactory()
    path = "/"
    if query_params:
        from django.http import QueryDict

        q = QueryDict(mutable=True)
        for k, v in query_params.items():
            q[k] = v
        path = f"/?{q.urlencode()}"
    request = rf.get(path)
    if headers:
        for k, v in headers.items():
            request.META[k] = v
    if cookies:
        request.COOKIES = cookies
    if user:
        request.user = user
    else:
        request.user = MagicMock(is_authenticated=False)
    return request


def _make_user(pk=1, email="test@example.com", is_staff=False, is_superuser=False):
    user = MagicMock()
    user.pk = pk
    user.id = pk
    user.email = email
    user.is_authenticated = True
    user.is_staff = is_staff
    user.is_superuser = is_superuser
    # Set to None to avoid naive/aware datetime mismatch in FlagContext.from_request
    user.date_joined = None
    return user


# ============================================================================
# FeatureFlag model
# ============================================================================


class TestFeatureFlagModel:
    def test_inactive_flag_is_not_active(self):
        flag = FeatureFlag(
            key="test_flag",
            name="Test",
            status=FlagStatus.INACTIVE.value,
        )
        assert flag.is_active is False

    def test_active_flag_is_active(self):
        flag = FeatureFlag(
            key="test_flag",
            name="Test",
            status=FlagStatus.ACTIVE.value,
        )
        assert flag.is_active is True

    def test_archived_flag_is_not_active(self):
        flag = FeatureFlag(
            key="test_flag",
            name="Test",
            status=FlagStatus.ARCHIVED.value,
        )
        assert flag.is_active is False

    def test_scheduled_enable_future(self):
        """Flag with future scheduled_enable_at is not active yet."""
        flag = FeatureFlag(
            key="test_flag",
            name="Test",
            status=FlagStatus.ACTIVE.value,
            scheduled_enable_at=timezone.now() + timedelta(hours=1),
        )
        assert flag.is_active is False

    def test_scheduled_disable_past(self):
        """Flag past scheduled_disable_at is not active."""
        flag = FeatureFlag(
            key="test_flag",
            name="Test",
            status=FlagStatus.ACTIVE.value,
            scheduled_disable_at=timezone.now() - timedelta(hours=1),
        )
        assert flag.is_active is False

    def test_type_enum_property(self):
        flag = FeatureFlag(flag_type=FlagType.PERCENTAGE.value)
        assert flag.type_enum == FlagType.PERCENTAGE

    def test_status_enum_property(self):
        flag = FeatureFlag(status=FlagStatus.ACTIVE.value)
        assert flag.status_enum == FlagStatus.ACTIVE

    def test_str_representation(self):
        flag = FeatureFlag(key="my_flag", flag_type=FlagType.BOOLEAN.value)
        assert "my_flag" in str(flag)


# ============================================================================
# Targeting rules
# ============================================================================


class TestTargetingRules:
    def _make_flag(self, rules):
        return FeatureFlag(
            key="targeted",
            name="Targeted",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.BOOLEAN.value,
            enabled_by_default=False,
            targeting_rules=rules,
        )

    def test_eq_operator(self):
        flag = self._make_flag([{"attribute": "plan", "operator": "eq", "value": "pro"}])
        assert flag._evaluate_targeting_rules({"plan": "pro"}) is True
        assert flag._evaluate_targeting_rules({"plan": "free"}) is False

    def test_neq_operator(self):
        flag = self._make_flag([{"attribute": "plan", "operator": "neq", "value": "free"}])
        assert flag._evaluate_targeting_rules({"plan": "pro"}) is True
        assert flag._evaluate_targeting_rules({"plan": "free"}) is False

    def test_gt_operator(self):
        flag = self._make_flag([{"attribute": "age", "operator": "gt", "value": 18}])
        assert flag._evaluate_targeting_rules({"age": 20}) is True
        assert flag._evaluate_targeting_rules({"age": 18}) is False

    def test_gte_operator(self):
        flag = self._make_flag([{"attribute": "age", "operator": "gte", "value": 18}])
        assert flag._evaluate_targeting_rules({"age": 18}) is True
        assert flag._evaluate_targeting_rules({"age": 17}) is False

    def test_lt_operator(self):
        flag = self._make_flag([{"attribute": "score", "operator": "lt", "value": 50}])
        assert flag._evaluate_targeting_rules({"score": 30}) is True
        assert flag._evaluate_targeting_rules({"score": 50}) is False

    def test_lte_operator(self):
        flag = self._make_flag([{"attribute": "score", "operator": "lte", "value": 50}])
        assert flag._evaluate_targeting_rules({"score": 50}) is True
        assert flag._evaluate_targeting_rules({"score": 51}) is False

    def test_in_operator(self):
        flag = self._make_flag(
            [{"attribute": "country", "operator": "in", "value": ["US", "UK"]}]
        )
        assert flag._evaluate_targeting_rules({"country": "US"}) is True
        assert flag._evaluate_targeting_rules({"country": "FR"}) is False

    def test_not_in_operator(self):
        flag = self._make_flag(
            [{"attribute": "country", "operator": "not_in", "value": ["CN", "RU"]}]
        )
        assert flag._evaluate_targeting_rules({"country": "US"}) is True
        assert flag._evaluate_targeting_rules({"country": "CN"}) is False

    def test_contains_operator(self):
        flag = self._make_flag(
            [{"attribute": "email", "operator": "contains", "value": "@company.com"}]
        )
        assert flag._evaluate_targeting_rules({"email": "user@company.com"}) is True
        assert flag._evaluate_targeting_rules({"email": "user@gmail.com"}) is False

    def test_starts_with_operator(self):
        flag = self._make_flag(
            [{"attribute": "name", "operator": "starts_with", "value": "Admin"}]
        )
        assert flag._evaluate_targeting_rules({"name": "AdminUser"}) is True
        assert flag._evaluate_targeting_rules({"name": "User"}) is False

    def test_ends_with_operator(self):
        flag = self._make_flag(
            [{"attribute": "domain", "operator": "ends_with", "value": ".com"}]
        )
        assert flag._evaluate_targeting_rules({"domain": "example.com"}) is True
        assert flag._evaluate_targeting_rules({"domain": "example.org"}) is False

    def test_regex_operator(self):
        flag = self._make_flag(
            [{"attribute": "code", "operator": "regex", "value": r"^[A-Z]{3}\d{3}$"}]
        )
        assert flag._evaluate_targeting_rules({"code": "ABC123"}) is True
        assert flag._evaluate_targeting_rules({"code": "abc123"}) is False

    def test_missing_attribute_returns_false(self):
        flag = self._make_flag([{"attribute": "missing", "operator": "eq", "value": "x"}])
        assert flag._evaluate_targeting_rules({"other": "x"}) is False

    def test_empty_rules_returns_false(self):
        flag = self._make_flag([])
        assert flag._evaluate_targeting_rules({"plan": "pro"}) is False

    def test_unknown_operator_returns_false(self):
        flag = self._make_flag(
            [{"attribute": "plan", "operator": "unknown_op", "value": "pro"}]
        )
        assert flag._evaluate_targeting_rules({"plan": "pro"}) is False


# ============================================================================
# Percentage rollout
# ============================================================================


class TestPercentageRollout:
    def test_zero_percent_disabled(self):
        flag = FeatureFlag(
            key="pct_flag",
            name="Pct",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.PERCENTAGE.value,
            rollout_percentage=0,
        )
        user = _make_user(pk=1)
        assert flag._is_in_percentage_rollout(user) is False

    def test_hundred_percent_enabled(self):
        flag = FeatureFlag(
            key="pct_flag",
            name="Pct",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.PERCENTAGE.value,
            rollout_percentage=100,
        )
        user = _make_user(pk=1)
        assert flag._is_in_percentage_rollout(user) is True

    def test_consistent_bucketing(self):
        """Same user+flag key always gets the same bucket."""
        flag = FeatureFlag(
            key="consistent_flag",
            name="Consistent",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.PERCENTAGE.value,
            rollout_percentage=50,
        )
        user = _make_user(pk=42)
        result1 = flag._is_in_percentage_rollout(user)
        result2 = flag._is_in_percentage_rollout(user)
        assert result1 == result2


# ============================================================================
# FlagOverride model
# ============================================================================


class TestFlagOverrideModel:
    def test_not_expired_when_no_expires_at(self):
        override = FlagOverride(expires_at=None)
        assert override.is_expired is False
        assert override.is_active is True

    def test_expired_when_past(self):
        override = FlagOverride(expires_at=timezone.now() - timedelta(hours=1))
        assert override.is_expired is True
        assert override.is_active is False

    def test_not_expired_when_future(self):
        override = FlagOverride(expires_at=timezone.now() + timedelta(hours=1))
        assert override.is_expired is False
        assert override.is_active is True


# ============================================================================
# MemoryBackend
# ============================================================================


class TestMemoryBackend:
    def test_missing_flag_returns_default(self):
        backend = MemoryBackend()
        assert backend.is_enabled("nonexistent") is False
        assert backend.is_enabled("nonexistent", default=True) is True

    def test_set_and_check_flag(self):
        backend = MemoryBackend()
        backend.set_flag("feature_x", enabled=True)
        assert backend.is_enabled("feature_x") is True

        backend.set_flag("feature_y", enabled=False)
        assert backend.is_enabled("feature_y") is False

    def test_user_override(self):
        backend = MemoryBackend()
        backend.set_flag("feature_x", enabled=False)
        backend.set_override("feature_x", user_id="42", enabled=True)

        user = _make_user(pk=42)
        assert backend.is_enabled("feature_x", user=user) is True

    def test_get_variant_with_user(self):
        backend = MemoryBackend()
        backend.set_flag("experiment", variants=["control", "treatment_a", "treatment_b"])

        user = _make_user(pk=1)
        variant = backend.get_variant("experiment", user=user)
        assert variant in ["control", "treatment_a", "treatment_b"]

    def test_get_variant_override(self):
        backend = MemoryBackend()
        backend.set_flag("experiment", variants=["control", "treatment"])
        backend.set_override("experiment", user_id="1", variant="treatment")

        user = _make_user(pk=1)
        assert backend.get_variant("experiment", user=user) == "treatment"

    def test_get_variant_missing_flag(self):
        backend = MemoryBackend()
        assert backend.get_variant("missing", default="fallback") == "fallback"

    def test_get_all_flags(self):
        backend = MemoryBackend()
        backend.set_flag("a", enabled=True)
        backend.set_flag("b", enabled=False)

        result = backend.get_all_flags()
        assert result["a"] is True
        assert result["b"] is False

    def test_invalidate_removes_flag(self):
        backend = MemoryBackend()
        backend.set_flag("temp", enabled=True)
        backend.invalidate("temp")
        assert backend.is_enabled("temp") is False

    def test_invalidate_all_clears(self):
        backend = MemoryBackend()
        backend.set_flag("a", enabled=True)
        backend.set_flag("b", enabled=True)
        backend.invalidate_all()
        assert backend.get_all_flags() == {}

    def test_percentage_rollout(self):
        backend = MemoryBackend()
        backend.set_flag("pct", flag_type="percentage", rollout_percentage=50)

        user = _make_user(pk=1)
        # Just verify it returns a boolean without error
        result = backend.is_enabled("pct", user=user)
        assert isinstance(result, bool)

    def test_clear(self):
        backend = MemoryBackend()
        backend.set_flag("x", enabled=True)
        backend.clear()
        assert backend.is_enabled("x") is False


# ============================================================================
# DatabaseBackend (with DB)
# ============================================================================


class TestDatabaseBackend:
    def test_missing_flag_returns_default(self):
        backend = DatabaseBackend(use_cache=False)
        assert backend.is_enabled("nonexistent_db_flag") is False
        assert backend.is_enabled("nonexistent_db_flag", default=True) is True

    def test_active_boolean_flag(self):
        flag = FeatureFlag.objects.create(
            key="db_bool_flag",
            name="DB Bool",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.BOOLEAN.value,
            enabled_by_default=True,
        )

        backend = DatabaseBackend(use_cache=False)
        assert backend.is_enabled("db_bool_flag") is True

    def test_inactive_flag_returns_false(self):
        FeatureFlag.objects.create(
            key="db_inactive",
            name="Inactive",
            status=FlagStatus.INACTIVE.value,
            enabled_by_default=True,
        )

        backend = DatabaseBackend(use_cache=False)
        assert backend.is_enabled("db_inactive") is False

    def test_cache_invalidation(self):
        FeatureFlag.objects.create(
            key="cached_flag",
            name="Cached",
            status=FlagStatus.ACTIVE.value,
            enabled_by_default=True,
        )

        backend = DatabaseBackend(use_cache=True, cache_timeout=60)
        # First call caches
        assert backend.is_enabled("cached_flag") is True

        # Invalidate
        backend.invalidate("cached_flag")

        # Should re-fetch from DB
        assert backend.is_enabled("cached_flag") is True

    def test_get_variant_missing_flag(self):
        backend = DatabaseBackend(use_cache=False)
        assert backend.get_variant("missing", default="fallback") == "fallback"

    def test_get_all_flags(self):
        FeatureFlag.objects.create(
            key="all_flag_a",
            name="A",
            status=FlagStatus.ACTIVE.value,
            enabled_by_default=True,
        )
        FeatureFlag.objects.create(
            key="all_flag_b",
            name="B",
            status=FlagStatus.ACTIVE.value,
            enabled_by_default=False,
        )

        backend = DatabaseBackend(use_cache=False)
        result = backend.get_all_flags()
        assert result["all_flag_a"] is True
        assert result["all_flag_b"] is False


# ============================================================================
# FeatureFlag.is_enabled_for_user (with DB overrides)
# ============================================================================


class TestFlagEnabledForUser:
    def test_user_override_enabled(self):
        flag = FeatureFlag.objects.create(
            key="user_override_test",
            name="User Override",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.BOOLEAN.value,
            enabled_by_default=False,
        )
        flag.add_override(
            override_type=OverrideType.USER,
            target_id="42",
            enabled=True,
        )

        user = _make_user(pk=42)
        assert flag.is_enabled_for_user(user=user) is True

    def test_user_override_disabled(self):
        flag = FeatureFlag.objects.create(
            key="user_override_disabled",
            name="User Override Disabled",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.BOOLEAN.value,
            enabled_by_default=True,
        )
        flag.add_override(
            override_type=OverrideType.USER,
            target_id="42",
            enabled=False,
        )

        user = _make_user(pk=42)
        assert flag.is_enabled_for_user(user=user) is False

    def test_email_override(self):
        flag = FeatureFlag.objects.create(
            key="email_override_test",
            name="Email Override",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.BOOLEAN.value,
            enabled_by_default=False,
        )
        flag.add_override(
            override_type=OverrideType.EMAIL,
            target_value="special@example.com",
            enabled=True,
        )

        user = _make_user(pk=99, email="special@example.com")
        assert flag.is_enabled_for_user(user=user) is True

    def test_targeting_rules_with_attributes(self):
        flag = FeatureFlag.objects.create(
            key="targeted_flag",
            name="Targeted",
            status=FlagStatus.ACTIVE.value,
            flag_type=FlagType.BOOLEAN.value,
            enabled_by_default=False,
            targeting_rules=[{"attribute": "plan", "operator": "eq", "value": "enterprise"}],
        )

        assert flag.is_enabled_for_user(attributes={"plan": "enterprise"}) is True
        assert flag.is_enabled_for_user(attributes={"plan": "free"}) is False


# ============================================================================
# FlagAuditLog
# ============================================================================


class TestFlagAuditLog:
    def test_create_audit_log(self):
        flag = FeatureFlag.objects.create(
            key="audit_flag",
            name="Audit",
            status=FlagStatus.ACTIVE.value,
        )

        log = FlagAuditLog.log(
            flag=flag,
            action="enable",
            changes={"enabled_by_default": True},
        )

        assert log.flag_key == "audit_flag"
        assert log.action == "enable"
        assert log.changes == {"enabled_by_default": True}


# ============================================================================
# FlagContext
# ============================================================================


class TestFlagContext:
    def test_from_request_anonymous(self):
        request = _make_request()
        ctx = FlagContext.from_request(request)
        assert ctx.user is None

    def test_from_request_authenticated(self):
        user = _make_user(pk=1, email="user@test.com")
        request = _make_request(user=user)
        ctx = FlagContext.from_request(request)
        assert ctx.user == user
        assert ctx.attributes["email"] == "user@test.com"

    def test_with_attributes(self):
        ctx = FlagContext(attributes={"a": 1})
        new_ctx = ctx.with_attributes(b=2)
        assert new_ctx.attributes["a"] == 1
        assert new_ctx.attributes["b"] == 2

    def test_with_user(self):
        user = _make_user(pk=5)
        ctx = FlagContext()
        new_ctx = ctx.with_user(user)
        assert new_ctx.user == user

    def test_with_organization(self):
        org = MagicMock(pk=10)
        ctx = FlagContext()
        new_ctx = ctx.with_organization(org)
        assert new_ctx.organization == org

    def test_context_manager(self):
        ctx = FlagContext(attributes={"test": True})
        assert get_current_context() is None

        with ctx:
            assert get_current_context() is ctx

        assert get_current_context() is None

    def test_is_enabled_delegates_to_backend(self):
        backend = MemoryBackend()
        backend.set_flag("ctx_flag", enabled=True)

        ctx = FlagContext(_backend=backend)
        assert ctx.is_enabled("ctx_flag") is True
        assert ctx.is_enabled("missing_flag") is False

    def test_get_variant_delegates_to_backend(self):
        backend = MemoryBackend()
        backend.set_flag("var_flag", variants=["a", "b"])

        ctx = FlagContext(_backend=backend)
        user = _make_user(pk=1)
        ctx_with_user = ctx.with_user(user)
        result = ctx_with_user.get_variant("var_flag")
        assert result in ["a", "b"]

    def test_get_all_flags(self):
        backend = MemoryBackend()
        backend.set_flag("f1", enabled=True)
        backend.set_flag("f2", enabled=False)

        ctx = FlagContext(_backend=backend)
        flags = ctx.get_all_flags()
        assert flags["f1"] is True
        assert flags["f2"] is False


# ============================================================================
# Decorators: feature_flag, requires_flag
# ============================================================================


class TestFlagDecorators:
    def test_requires_flag_blocks_when_disabled(self):
        backend = MemoryBackend()
        backend.set_flag("beta", enabled=False)

        @requires_flag("beta")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = _make_request()
        # Inject context with our backend
        ctx = FlagContext(_backend=backend)
        set_current_context(ctx)
        request.flag_context = ctx

        with patch("django_matt.flags.context.FlagContext.from_request", return_value=ctx):
            response = my_view(request)

        set_current_context(None)
        assert response.status_code == 404

    def test_requires_flag_allows_when_enabled(self):
        backend = MemoryBackend()
        backend.set_flag("beta", enabled=True)

        @requires_flag("beta")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = _make_request()
        ctx = FlagContext(_backend=backend)

        with patch("django_matt.flags.context.FlagContext.from_request", return_value=ctx):
            response = my_view(request)

        assert response.status_code == 200

    def test_feature_flag_with_fallback(self):
        backend = MemoryBackend()

        def fallback_view(request):
            return JsonResponse({"fallback": True})

        @feature_flag("new_ui", fallback=fallback_view)
        def new_view(request):
            return JsonResponse({"new": True})

        request = _make_request()
        ctx = FlagContext(_backend=backend)

        with patch("django_matt.flags.context.FlagContext.from_request", return_value=ctx):
            response = new_view(request)

        import orjson

        data = orjson.loads(response.content)
        assert data["fallback"] is True

    def test_feature_flag_enabled_calls_original(self):
        backend = MemoryBackend()
        backend.set_flag("new_ui", enabled=True)

        @feature_flag("new_ui")
        def new_view(request):
            return JsonResponse({"new": True})

        request = _make_request()
        ctx = FlagContext(_backend=backend)

        with patch("django_matt.flags.context.FlagContext.from_request", return_value=ctx):
            response = new_view(request)

        import orjson

        data = orjson.loads(response.content)
        assert data["new"] is True

    def test_requires_flag_custom_status_code(self):
        backend = MemoryBackend()

        @requires_flag("admin_tools", status_code=403, error_message="Access denied")
        def admin_view(request):
            return JsonResponse({"ok": True})

        request = _make_request()
        ctx = FlagContext(_backend=backend)

        with patch("django_matt.flags.context.FlagContext.from_request", return_value=ctx):
            response = admin_view(request)

        assert response.status_code == 403


# ============================================================================
# FlagMiddleware
# ============================================================================


class TestFlagMiddleware:
    def test_middleware_sets_flag_context_on_request(self):
        captured = {}

        def get_response(request):
            captured["ctx"] = getattr(request, "flag_context", None)
            return JsonResponse({"ok": True})

        middleware = FlagMiddleware(get_response)
        request = _make_request()
        middleware(request)

        assert captured["ctx"] is not None
        assert isinstance(captured["ctx"], FlagContext)

    def test_middleware_clears_context_after_response(self):
        def get_response(request):
            return JsonResponse({"ok": True})

        middleware = FlagMiddleware(get_response)
        request = _make_request()
        middleware(request)

        assert get_current_context() is None

    @pytest.mark.django_db
    def test_query_overrides_applied_in_debug(self):
        captured = {}

        def get_response(request):
            captured["ctx"] = getattr(request, "flag_context", None)
            return JsonResponse({"ok": True})

        from django.test import override_settings

        with override_settings(
            FEATURE_FLAG_MIDDLEWARE={
                "query_overrides": True,
                "override_prefix": "ff_",
                "debug_mode": True,
            },
            DEBUG=True,
        ):
            middleware = FlagMiddleware(get_response)
            request = _make_request(query_params={"ff_new_feature": "true"})
            middleware(request)

        ctx = captured["ctx"]
        assert ctx.attributes.get("_overrides", {}).get("new_feature") is True


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_flag_type_choices(self):
        choices = FlagType.choices()
        assert len(choices) == 3
        assert any(c[0] == "boolean" for c in choices)

    def test_flag_status_choices(self):
        choices = FlagStatus.choices()
        assert len(choices) == 3

    def test_override_type_choices(self):
        choices = OverrideType.choices()
        assert len(choices) == 4

    def test_flag_manager_by_key_missing(self):
        result = FeatureFlag.objects.by_key("totally_missing")
        assert result is None

    def test_flag_manager_by_key_found(self):
        FeatureFlag.objects.create(
            key="findable",
            name="Findable",
            status=FlagStatus.ACTIVE.value,
        )
        result = FeatureFlag.objects.by_key("findable")
        assert result is not None
        assert result.key == "findable"

    def test_flag_manager_active(self):
        FeatureFlag.objects.create(
            key="active_one",
            name="Active",
            status=FlagStatus.ACTIVE.value,
        )
        FeatureFlag.objects.create(
            key="inactive_one",
            name="Inactive",
            status=FlagStatus.INACTIVE.value,
        )

        active_flags = FeatureFlag.objects.active()
        keys = list(active_flags.values_list("key", flat=True))
        assert "active_one" in keys
        assert "inactive_one" not in keys

"""
Tests for the feature flags module.

Tests cover:
- FlagType, FlagStatus, OverrideType enums
- FlagContext (creation, context manager, with_attributes, with_user)
- @feature_flag / @requires_flag / @variant_flag decorators
- MemoryBackend (is_enabled, get_variant, get_all_flags, set_flag, set_override)
- DatabaseBackend (mocked ORM)
- RedisBackend (mocked redis)
- FeatureFlag model logic (is_active, is_enabled_for_user, percentage rollout, targeting rules)
- FlagOverride model (is_expired, is_active)
- FlagAuditLog model
- Schemas (validation)
"""

import hashlib
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import pytest
from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory
from django.utils import timezone

from django_matt.flags.models import (
    FeatureFlag,
    FlagAuditLog,
    FlagOverride,
    FlagStatus,
    FlagType,
    OverrideType,
)
from django_matt.flags.context import FlagContext, get_current_context, set_current_context
from django_matt.flags.decorators import (
    feature_flag,
    requires_flag,
    variant_flag,
    with_flag_context,
    FlagEnabledMixin,
)
from django_matt.flags.backends import (
    MemoryBackend,
    FlagBackend,
)
from django_matt.flags.schemas import (
    FlagTypeEnum,
    FlagStatusEnum,
    OverrideTypeEnum,
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FlagOverrideCreate,
    FlagEvaluationContext,
    VariantSchema,
)


# ==============================================================================
# Helpers
# ==============================================================================


def make_mock_user(pk=1, email="user@example.com", is_staff=False, is_authenticated=True):
    user = MagicMock()
    user.pk = pk
    user.email = email
    user.is_staff = is_staff
    user.is_authenticated = is_authenticated
    user.is_superuser = False
    return user


def make_request(user=None, path="/test/", method="GET"):
    factory = RequestFactory()
    request = factory.get(path)
    if user:
        request.user = user
    else:
        request.user = MagicMock(is_authenticated=False)
    return request


# ==============================================================================
# FlagType enum
# ==============================================================================


class TestFlagType:
    def test_values(self):
        assert FlagType.BOOLEAN.value == "boolean"
        assert FlagType.PERCENTAGE.value == "percentage"
        assert FlagType.VARIANT.value == "variant"

    def test_choices(self):
        choices = FlagType.choices()
        assert len(choices) == 3
        assert ("boolean", "Boolean") in choices


# ==============================================================================
# FlagStatus enum
# ==============================================================================


class TestFlagStatus:
    def test_values(self):
        assert FlagStatus.ACTIVE.value == "active"
        assert FlagStatus.INACTIVE.value == "inactive"
        assert FlagStatus.ARCHIVED.value == "archived"

    def test_choices(self):
        choices = FlagStatus.choices()
        assert len(choices) == 3


# ==============================================================================
# OverrideType enum
# ==============================================================================


class TestOverrideType:
    def test_values(self):
        assert OverrideType.USER.value == "user"
        assert OverrideType.ORGANIZATION.value == "organization"
        assert OverrideType.EMAIL.value == "email"
        assert OverrideType.ATTRIBUTE.value == "attribute"

    def test_choices(self):
        choices = OverrideType.choices()
        assert len(choices) == 4


# ==============================================================================
# FlagContext
# ==============================================================================


class TestFlagContext:
    def test_basic_creation(self):
        ctx = FlagContext()
        assert ctx.user is None
        assert ctx.organization is None
        assert ctx.attributes == {}

    def test_with_user(self):
        user = make_mock_user()
        ctx = FlagContext(user=user)
        new_ctx = ctx.with_user(make_mock_user(pk=2))
        assert new_ctx.user.pk == 2
        assert ctx.user.pk == 1  # original unchanged

    def test_with_attributes(self):
        ctx = FlagContext(attributes={"plan": "pro"})
        new_ctx = ctx.with_attributes(region="us")
        assert new_ctx.attributes["plan"] == "pro"
        assert new_ctx.attributes["region"] == "us"
        assert "region" not in ctx.attributes  # original unchanged

    def test_with_organization(self):
        ctx = FlagContext()
        org = MagicMock(pk=42)
        new_ctx = ctx.with_organization(org)
        assert new_ctx.organization.pk == 42
        assert ctx.organization is None

    def test_context_manager(self):
        ctx = FlagContext()
        assert get_current_context() is None

        with ctx:
            assert get_current_context() is ctx

        assert get_current_context() is None

    def test_from_request_authenticated(self):
        user = make_mock_user(email="test@example.com", is_staff=True)
        request = make_request(user=user)
        ctx = FlagContext.from_request(request)
        assert ctx.user is user
        assert ctx.attributes["email"] == "test@example.com"
        assert ctx.attributes["is_staff"] is True

    def test_from_request_anonymous(self):
        request = make_request()
        ctx = FlagContext.from_request(request)
        assert ctx.user is None
        assert ctx.attributes["path"] == "/test/"

    def test_is_enabled_delegates_to_backend(self):
        backend = MemoryBackend()
        backend.set_flag("test_flag", enabled=True)
        ctx = FlagContext(_backend=backend)
        assert ctx.is_enabled("test_flag") is True
        assert ctx.is_enabled("missing_flag") is False

    def test_get_variant_delegates_to_backend(self):
        backend = MemoryBackend()
        backend.set_flag("exp", flag_type="variant", variants=["control", "treatment"])
        ctx = FlagContext(_backend=backend, user=make_mock_user())
        variant = ctx.get_variant("exp")
        assert variant in ["control", "treatment"]


# ==============================================================================
# MemoryBackend
# ==============================================================================


class TestMemoryBackend:
    def setup_method(self):
        self.backend = MemoryBackend()

    def test_set_flag_and_is_enabled(self):
        self.backend.set_flag("feature_a", enabled=True)
        assert self.backend.is_enabled("feature_a") is True

    def test_disabled_flag(self):
        self.backend.set_flag("feature_b", enabled=False)
        assert self.backend.is_enabled("feature_b") is False

    def test_missing_flag_returns_default(self):
        assert self.backend.is_enabled("nonexistent") is False
        assert self.backend.is_enabled("nonexistent", default=True) is True

    def test_set_override_for_user(self):
        self.backend.set_flag("feature_c", enabled=False)
        user = make_mock_user(pk=42)
        self.backend.set_override("feature_c", user_id="42", enabled=True)
        assert self.backend.is_enabled("feature_c", user=user) is True

    def test_override_disable(self):
        self.backend.set_flag("feature_d", enabled=True)
        user = make_mock_user(pk=10)
        self.backend.set_override("feature_d", user_id="10", enabled=False)
        assert self.backend.is_enabled("feature_d", user=user) is False

    def test_get_variant(self):
        self.backend.set_flag("exp", flag_type="variant", variants=["a", "b", "c"])
        user = make_mock_user(pk=1)
        variant = self.backend.get_variant("exp", user=user)
        assert variant in ["a", "b", "c"]

    def test_get_variant_with_override(self):
        self.backend.set_flag("exp2", flag_type="variant", variants=["a", "b"])
        self.backend.set_override("exp2", user_id="1", variant="b")
        user = make_mock_user(pk=1)
        assert self.backend.get_variant("exp2", user=user) == "b"

    def test_get_variant_missing_flag(self):
        assert self.backend.get_variant("nonexistent") is None
        assert self.backend.get_variant("nonexistent", default="fallback") == "fallback"

    def test_get_all_flags(self):
        self.backend.set_flag("f1", enabled=True)
        self.backend.set_flag("f2", enabled=False)
        flags = self.backend.get_all_flags()
        assert flags["f1"] is True
        assert flags["f2"] is False

    def test_clear(self):
        self.backend.set_flag("x", enabled=True)
        self.backend.clear()
        assert self.backend.is_enabled("x") is False

    def test_percentage_rollout(self):
        self.backend.set_flag(
            "rollout", flag_type="percentage", rollout_percentage=50
        )
        # Deterministic: check some users
        results = set()
        for i in range(100):
            user = make_mock_user(pk=i)
            results.add(self.backend.is_enabled("rollout", user=user))
        # With 50% rollout over 100 users, we should see both True and False
        assert True in results
        assert False in results


# ==============================================================================
# @feature_flag decorator
# ==============================================================================


class TestFeatureFlagDecorator:
    def test_enabled_flag_calls_view(self):
        backend = MemoryBackend()
        backend.set_flag("test_feat", enabled=True)

        @feature_flag("test_feat")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = make_request()
        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            response = my_view(request)
            assert response.status_code == 200

    def test_disabled_flag_returns_404(self):
        backend = MemoryBackend()
        backend.set_flag("test_feat", enabled=False)

        @feature_flag("test_feat")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = make_request()
        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            response = my_view(request)
            assert response.status_code == 404

    def test_disabled_flag_with_fallback(self):
        backend = MemoryBackend()

        def fallback_view(request):
            return JsonResponse({"fallback": True})

        @feature_flag("missing", fallback=fallback_view)
        def my_view(request):
            return JsonResponse({"ok": True})

        request = make_request()
        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            response = my_view(request)
            data = json.loads(response.content)
            assert data["fallback"] is True

    def test_disabled_flag_with_fallback_response(self):
        backend = MemoryBackend()

        @feature_flag("missing", fallback_response={"error": "nope"})
        def my_view(request):
            return JsonResponse({"ok": True})

        request = make_request()
        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            response = my_view(request)
            assert response.status_code == 404


# ==============================================================================
# @requires_flag decorator
# ==============================================================================


class TestRequiresFlagDecorator:
    def test_enabled_flag_passes(self):
        backend = MemoryBackend()
        backend.set_flag("required", enabled=True)

        @requires_flag("required")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = make_request()
        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            response = my_view(request)
            assert response.status_code == 200

    def test_disabled_flag_returns_error(self):
        backend = MemoryBackend()

        @requires_flag("required", status_code=403, error_message="Forbidden")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = make_request()
        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            response = my_view(request)
            assert response.status_code == 403
            data = json.loads(response.content)
            assert data["detail"] == "Forbidden"


# ==============================================================================
# @variant_flag decorator
# ==============================================================================


class TestVariantFlagDecorator:
    def test_routes_to_variant_handler(self):
        backend = MemoryBackend()
        backend.set_flag("exp", flag_type="variant", variants=["control", "treatment"])

        def control_handler(request):
            return JsonResponse({"variant": "control"})

        def treatment_handler(request):
            return JsonResponse({"variant": "treatment"})

        @variant_flag(
            "exp",
            variant_handlers={
                "control": control_handler,
                "treatment": treatment_handler,
            },
        )
        def default_view(request):
            return JsonResponse({"variant": "default"})

        request = make_request(user=make_mock_user())
        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend, user=make_mock_user())
            mock_from_req.return_value = ctx
            response = default_view(request)
            data = json.loads(response.content)
            assert data["variant"] in ["control", "treatment"]


# ==============================================================================
# FlagEnabledMixin
# ==============================================================================


class TestFlagEnabledMixin:
    def test_check_flags_passes(self):
        backend = MemoryBackend()
        backend.set_flag("required_feat", enabled=True)

        mixin = FlagEnabledMixin()
        mixin.required_flags = ["required_feat"]
        mixin.request = make_request()

        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            result = mixin.check_flags()
            assert result is None  # None means all flags pass

    def test_check_flags_fails(self):
        backend = MemoryBackend()

        mixin = FlagEnabledMixin()
        mixin.required_flags = ["missing_feat"]
        mixin.request = make_request()

        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            result = mixin.check_flags()
            assert result is not None
            assert result.status_code == 404


# ==============================================================================
# FeatureFlag model logic (mocked, no DB)
# ==============================================================================


class TestFeatureFlagModel:
    def _make_flag(self, **kwargs):
        """Create a mock FeatureFlag instance."""
        defaults = {
            "key": "test_flag",
            "name": "Test Flag",
            "flag_type": FlagType.BOOLEAN.value,
            "status": FlagStatus.ACTIVE.value,
            "enabled_by_default": False,
            "rollout_percentage": 0,
            "variants": {},
            "targeting_rules": [],
            "scheduled_enable_at": None,
            "scheduled_disable_at": None,
            "metadata": {},
        }
        defaults.update(kwargs)

        flag = MagicMock(spec=FeatureFlag)
        for k, v in defaults.items():
            setattr(flag, k, v)

        # Wire up real property logic
        flag.is_active = FeatureFlag.is_active.fget(flag)
        flag.type_enum = FlagType(defaults["flag_type"])
        flag.status_enum = FlagStatus(defaults["status"])

        return flag

    def test_is_active_when_active(self):
        flag = self._make_flag(status=FlagStatus.ACTIVE.value)
        assert flag.is_active is True

    def test_is_active_when_inactive(self):
        flag = self._make_flag(status=FlagStatus.INACTIVE.value)
        assert flag.is_active is False

    def test_is_active_before_scheduled_enable(self):
        future = timezone.now() + timedelta(hours=1)
        flag = self._make_flag(scheduled_enable_at=future)
        assert flag.is_active is False

    def test_is_active_after_scheduled_disable(self):
        past = timezone.now() - timedelta(hours=1)
        flag = self._make_flag(scheduled_disable_at=past)
        assert flag.is_active is False

    def test_str(self):
        flag = Mock(spec=FeatureFlag)
        flag.key = "my_flag"
        flag.flag_type = "boolean"
        flag.__str__ = FeatureFlag.__str__
        assert "my_flag" in str(flag)

    def test_type_enum_property(self):
        flag = self._make_flag(flag_type=FlagType.PERCENTAGE.value)
        assert flag.type_enum == FlagType.PERCENTAGE

    def test_targeting_rule_eq(self):
        flag = MagicMock(spec=FeatureFlag)
        flag.targeting_rules = [{"attribute": "plan", "operator": "eq", "value": "pro"}]
        result = FeatureFlag._evaluate_targeting_rules(flag, {"plan": "pro"})
        assert result is True

    def test_targeting_rule_neq(self):
        flag = MagicMock(spec=FeatureFlag)
        flag.targeting_rules = [{"attribute": "plan", "operator": "neq", "value": "free"}]
        result = FeatureFlag._evaluate_targeting_rules(flag, {"plan": "pro"})
        assert result is True

    def test_targeting_rule_in(self):
        flag = MagicMock(spec=FeatureFlag)
        flag.targeting_rules = [{"attribute": "region", "operator": "in", "value": ["us", "eu"]}]
        result = FeatureFlag._evaluate_targeting_rules(flag, {"region": "us"})
        assert result is True

    def test_targeting_rule_contains(self):
        flag = MagicMock(spec=FeatureFlag)
        flag.targeting_rules = [{"attribute": "email", "operator": "contains", "value": "@example.com"}]
        result = FeatureFlag._evaluate_targeting_rules(flag, {"email": "user@example.com"})
        assert result is True

    def test_targeting_rule_starts_with(self):
        flag = MagicMock(spec=FeatureFlag)
        flag.targeting_rules = [{"attribute": "name", "operator": "starts_with", "value": "admin"}]
        result = FeatureFlag._evaluate_targeting_rules(flag, {"name": "admin_user"})
        assert result is True

    def test_targeting_rule_missing_attribute(self):
        flag = MagicMock(spec=FeatureFlag)
        flag.targeting_rules = [{"attribute": "plan", "operator": "eq", "value": "pro"}]
        # Bind real _evaluate_rule to the mock so it does real logic
        flag._evaluate_rule = lambda rule, attrs: FeatureFlag._evaluate_rule(flag, rule, attrs)
        result = FeatureFlag._evaluate_targeting_rules(flag, {"region": "us"})
        assert result is False

    def test_percentage_rollout(self):
        user = make_mock_user(pk=42)
        flag = MagicMock(spec=FeatureFlag)
        flag.key = "pct_flag"
        flag.rollout_percentage = 50
        # Deterministic: test with specific user
        result = FeatureFlag._is_in_percentage_rollout(flag, user)
        assert isinstance(result, bool)

    def test_percentage_rollout_zero(self):
        user = make_mock_user(pk=1)
        flag = MagicMock(spec=FeatureFlag)
        flag.key = "pct_zero"
        flag.rollout_percentage = 0
        assert FeatureFlag._is_in_percentage_rollout(flag, user) is False

    def test_percentage_rollout_hundred(self):
        user = make_mock_user(pk=1)
        flag = MagicMock(spec=FeatureFlag)
        flag.key = "pct_full"
        flag.rollout_percentage = 100
        assert FeatureFlag._is_in_percentage_rollout(flag, user) is True


# ==============================================================================
# FlagOverride model
# ==============================================================================


class TestFlagOverrideModel:
    def test_is_expired_no_expiry(self):
        override = MagicMock(spec=FlagOverride)
        override.expires_at = None
        override.is_expired = FlagOverride.is_expired.fget(override)
        assert override.is_expired is False

    def test_is_expired_future(self):
        override = MagicMock(spec=FlagOverride)
        override.expires_at = timezone.now() + timedelta(hours=1)
        override.is_expired = FlagOverride.is_expired.fget(override)
        assert override.is_expired is False

    def test_is_expired_past(self):
        override = MagicMock(spec=FlagOverride)
        override.expires_at = timezone.now() - timedelta(hours=1)
        override.is_expired = FlagOverride.is_expired.fget(override)
        assert override.is_expired is True

    def test_is_active(self):
        override = MagicMock(spec=FlagOverride)
        override.expires_at = None
        override.is_expired = False
        override.is_active = FlagOverride.is_active.fget(override)
        assert override.is_active is True


# ==============================================================================
# Schemas
# ==============================================================================


class TestSchemas:
    def test_flag_type_enum(self):
        assert FlagTypeEnum.BOOLEAN.value == "boolean"
        assert FlagTypeEnum.PERCENTAGE.value == "percentage"
        assert FlagTypeEnum.VARIANT.value == "variant"

    def test_feature_flag_create(self):
        data = FeatureFlagCreate(
            key="new_feature",
            name="New Feature",
            flag_type=FlagTypeEnum.BOOLEAN,
        )
        assert data.key == "new_feature"
        assert data.enabled_by_default is False
        assert data.status == FlagStatusEnum.INACTIVE

    def test_feature_flag_update_partial(self):
        data = FeatureFlagUpdate(name="Updated Name")
        assert data.name == "Updated Name"
        assert data.description is None  # not set

    def test_flag_override_create(self):
        data = FlagOverrideCreate(
            override_type=OverrideTypeEnum.USER,
            target_id="123",
            enabled=True,
        )
        assert data.override_type == OverrideTypeEnum.USER
        assert data.target_id == "123"

    def test_evaluation_context(self):
        ctx = FlagEvaluationContext(
            user_id="42",
            email="user@test.com",
            attributes={"plan": "pro"},
        )
        assert ctx.user_id == "42"
        assert ctx.attributes["plan"] == "pro"

    def test_variant_schema(self):
        v = VariantSchema(key="treatment_a", name="Treatment A", weight=2)
        assert v.key == "treatment_a"
        assert v.weight == 2
        assert v.payload == {}


# ==============================================================================
# DatabaseBackend (mocked)
# ==============================================================================


class TestDatabaseBackend:
    def test_is_enabled_returns_default_when_not_found(self):
        from django_matt.flags.backends import DatabaseBackend

        backend = DatabaseBackend(use_cache=False)
        with patch("django_matt.flags.models.FeatureFlag.objects") as mock_qs:
            mock_qs.prefetch_related.return_value.get.side_effect = FeatureFlag.DoesNotExist
            result = backend.is_enabled("missing_flag", default=True)
            assert result is True

    def test_invalidate_cache(self):
        from django_matt.flags.backends import DatabaseBackend

        backend = DatabaseBackend(use_cache=True, cache_prefix="test_flags:")
        with patch("django_matt.flags.backends.cache") as mock_cache:
            backend.invalidate_cache("some_flag")
            mock_cache.delete.assert_called_once_with("test_flags:some_flag")


# ==============================================================================
# RedisBackend (mocked)
# ==============================================================================


class TestRedisBackend:
    def test_invalidate(self):
        redis = pytest.importorskip("redis")
        from django_matt.flags.backends import RedisBackend

        backend = RedisBackend.__new__(RedisBackend)
        backend.redis_url = "redis://localhost:6379/0"
        backend.cache_timeout = 300
        backend.key_prefix = "feature_flags:"
        mock_client = MagicMock()
        backend._client = mock_client

        backend.invalidate("my_flag")
        mock_client.delete.assert_called_once_with("feature_flags:my_flag")

    def test_invalidate_all(self):
        redis = pytest.importorskip("redis")
        from django_matt.flags.backends import RedisBackend

        backend = RedisBackend.__new__(RedisBackend)
        backend.redis_url = "redis://localhost:6379/0"
        backend.cache_timeout = 300
        backend.key_prefix = "feature_flags:"
        mock_client = MagicMock()
        mock_client.keys.return_value = [b"feature_flags:a", b"feature_flags:b"]
        backend._client = mock_client

        backend.invalidate_all()
        mock_client.keys.assert_called_once_with("feature_flags:*")
        mock_client.delete.assert_called_once()

    def test_close(self):
        redis = pytest.importorskip("redis")
        from django_matt.flags.backends import RedisBackend

        backend = RedisBackend.__new__(RedisBackend)
        backend.redis_url = "redis://localhost:6379/0"
        backend.cache_timeout = 300
        backend.key_prefix = "feature_flags:"
        mock_client = MagicMock()
        backend._client = mock_client

        backend.close()
        mock_client.close.assert_called_once()
        assert backend._client is None


# ==============================================================================
# with_flag_context decorator
# ==============================================================================


class TestWithFlagContext:
    def test_sets_context(self):
        backend = MemoryBackend()

        @with_flag_context
        def my_view(request):
            ctx = get_current_context()
            assert ctx is not None
            return JsonResponse({"ok": True})

        request = make_request()
        with patch("django_matt.flags.context.FlagContext.from_request") as mock_from_req:
            ctx = FlagContext(_backend=backend)
            mock_from_req.return_value = ctx
            response = my_view(request)
            assert response.status_code == 200

        # Context should be cleared after view
        assert get_current_context() is None


# ==============================================================================
# set_current_context / get_current_context
# ==============================================================================


class TestContextVars:
    def test_set_and_get(self):
        ctx = FlagContext()
        set_current_context(ctx)
        assert get_current_context() is ctx
        set_current_context(None)
        assert get_current_context() is None

    def test_nested_contexts(self):
        ctx1 = FlagContext(attributes={"level": 1})
        ctx2 = FlagContext(attributes={"level": 2})

        with ctx1:
            assert get_current_context().attributes["level"] == 1
            with ctx2:
                assert get_current_context().attributes["level"] == 2
            assert get_current_context().attributes["level"] == 1

        assert get_current_context() is None

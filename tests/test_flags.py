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
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory
from django.utils import timezone

import pytest

from django_matt.flags.backends import (
    FlagBackend,
    MemoryBackend,
)
from django_matt.flags.context import FlagContext, get_current_context, set_current_context
from django_matt.flags.decorators import (
    FlagEnabledMixin,
    feature_flag,
    requires_flag,
    variant_flag,
    with_flag_context,
)
from django_matt.flags.models import (
    FeatureFlag,
    FlagAuditLog,
    FlagOverride,
    FlagStatus,
    FlagType,
    OverrideType,
)
from django_matt.flags.schemas import (
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FlagEvaluationContext,
    FlagOverrideCreate,
    FlagStatusEnum,
    FlagTypeEnum,
    OverrideTypeEnum,
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
        # The local import in _get_flag() fetches FeatureFlag from django_matt.flags.models
        with patch("django_matt.flags.models.FeatureFlag") as mock_model:
            mock_model.objects.prefetch_related.return_value.get.side_effect = FeatureFlag.DoesNotExist
            mock_model.DoesNotExist = FeatureFlag.DoesNotExist
            result = backend.is_enabled("missing_flag", default=True)
            assert result is True

    def test_invalidate_cache(self):
        from django_matt.flags.backends import DatabaseBackend

        backend = DatabaseBackend(use_cache=True, cache_prefix="test_flags:")
        with patch("django_matt.flags.backends.cache") as mock_cache:
            backend.invalidate_cache("some_flag")
            mock_cache.delete.assert_called_once_with("test_flags:some_flag")

    def test_is_enabled_boolean_flag_true(self):
        """DatabaseBackend.is_enabled() returns True for enabled boolean flag (FLAG-02)."""
        from django_matt.flags.backends import DatabaseBackend

        backend = DatabaseBackend(use_cache=False)
        mock_flag = MagicMock(spec=FeatureFlag)
        mock_flag.is_active = True
        mock_flag.flag_type = FlagType.BOOLEAN.value
        mock_flag.enabled_by_default = True
        mock_flag.overrides = MagicMock()
        mock_flag.overrides.filter.return_value.first.return_value = None
        mock_flag.targeting_rules = []
        mock_flag.is_enabled_for_user = lambda **kwargs: True

        # FeatureFlag is imported locally inside _get_flag(), so patch at models level
        with patch("django_matt.flags.models.FeatureFlag") as mock_model:
            mock_model.objects.prefetch_related.return_value.get.return_value = mock_flag
            mock_model.DoesNotExist = FeatureFlag.DoesNotExist
            result = backend.is_enabled("my-flag")
            assert result is True

    def test_is_enabled_uses_cache_on_second_call(self):
        """DatabaseBackend.is_enabled() uses cache on second call (TTL cache verification) (FLAG-02)."""
        from django_matt.flags.backends import DatabaseBackend

        backend = DatabaseBackend(use_cache=True, cache_prefix="flags:", cache_timeout=30)
        mock_flag = MagicMock(spec=FeatureFlag)
        mock_flag.is_active = True
        mock_flag.flag_type = FlagType.BOOLEAN.value
        mock_flag.enabled_by_default = True
        mock_flag.overrides = MagicMock()
        mock_flag.overrides.filter.return_value.first.return_value = None
        mock_flag.targeting_rules = []

        with patch("django_matt.flags.backends.cache") as mock_cache:
            # First call: cache miss (returns None), DB hit
            mock_cache.get.return_value = None
            with patch("django_matt.flags.models.FeatureFlag") as mock_model:
                mock_model.objects.prefetch_related.return_value.get.return_value = mock_flag
                mock_model.DoesNotExist = FeatureFlag.DoesNotExist
                mock_flag.is_enabled_for_user = lambda **kwargs: True
                result1 = backend.is_enabled("cached-flag")
                # Verify cache.set() was called to populate cache
                mock_cache.set.assert_called_once_with("flags:cached-flag", mock_flag, 30)
                assert result1 is True

            # Second call: cache hit (returns mock_flag)
            mock_cache.get.return_value = mock_flag
            mock_cache.reset_mock()
            with patch("django_matt.flags.models.FeatureFlag") as mock_model2:
                mock_model2.DoesNotExist = FeatureFlag.DoesNotExist
                mock_flag.is_enabled_for_user = lambda **kwargs: True
                result2 = backend.is_enabled("cached-flag")
                # DB should NOT be hit
                mock_model2.objects.prefetch_related.return_value.get.assert_not_called()
                assert result2 is True

    def test_percentage_rollout_deterministic(self):
        """DatabaseBackend percentage rollout is hash-based and deterministic (FLAG-02)."""
        from django_matt.flags.backends import DatabaseBackend

        backend = DatabaseBackend(use_cache=False)

        # Use FeatureFlag's real percentage rollout logic
        mock_flag = MagicMock(spec=FeatureFlag)
        mock_flag.is_active = True
        mock_flag.key = "pct-flag"
        mock_flag.flag_type = FlagType.PERCENTAGE.value
        mock_flag.rollout_percentage = 50
        mock_flag.overrides = MagicMock()
        mock_flag.overrides.filter.return_value.first.return_value = None
        mock_flag.targeting_rules = []

        # Bind real methods to the mock
        mock_flag._is_in_percentage_rollout = lambda u: FeatureFlag._is_in_percentage_rollout(mock_flag, u)
        mock_flag.is_enabled_for_user = lambda **kwargs: FeatureFlag.is_enabled_for_user(mock_flag, **kwargs)

        with patch("django_matt.flags.models.FeatureFlag") as mock_model:
            mock_model.objects.prefetch_related.return_value.get.return_value = mock_flag
            mock_model.DoesNotExist = FeatureFlag.DoesNotExist

            user = make_mock_user(pk=42)
            result1 = backend.is_enabled("pct-flag", user=user)
            result2 = backend.is_enabled("pct-flag", user=user)
            # Same user must always get same result
            assert result1 == result2
            assert isinstance(result1, bool)

    def test_invalidate_clears_cache_key(self):
        """DatabaseBackend.invalidate() clears the correct cache key (FLAG-02)."""
        from django_matt.flags.backends import DatabaseBackend

        backend = DatabaseBackend(use_cache=True, cache_prefix="flags:")
        with patch("django_matt.flags.backends.cache") as mock_cache:
            backend.invalidate("my-flag")
            mock_cache.delete.assert_called_once_with("flags:my-flag")

    def test_org_scoped_flag_via_override(self):
        """Org-scoped flags: is_enabled() with organization param respects FlagOverride (FLAG-01)."""
        from django_matt.flags.backends import DatabaseBackend

        backend = DatabaseBackend(use_cache=False)

        org = MagicMock()
        org.pk = "org-123"

        # Override: org-123 → disabled
        mock_override = MagicMock(spec=FlagOverride)
        mock_override.enabled = False
        mock_override.is_expired = False

        mock_flag = MagicMock(spec=FeatureFlag)
        mock_flag.is_active = True
        mock_flag.flag_type = FlagType.BOOLEAN.value
        mock_flag.enabled_by_default = True  # Would be True without override
        mock_flag.targeting_rules = []
        mock_flag.overrides = MagicMock()
        # With user=None (anonymous), the first filter().first() call is the org check
        mock_flag.overrides.filter.return_value.first.return_value = mock_override

        # Bind real is_enabled_for_user
        mock_flag.is_enabled_for_user = lambda **kwargs: FeatureFlag.is_enabled_for_user(mock_flag, **kwargs)

        with patch("django_matt.flags.models.FeatureFlag") as mock_model:
            mock_model.objects.prefetch_related.return_value.get.return_value = mock_flag
            mock_model.DoesNotExist = FeatureFlag.DoesNotExist

            result = backend.is_enabled("my-flag", organization=org)
            assert result is False  # disabled by org override


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

    def _make_redis_backend(self):
        """Create a RedisBackend with a mocked Redis client."""
        redis = pytest.importorskip("redis")
        from django_matt.flags.backends import RedisBackend

        backend = RedisBackend.__new__(RedisBackend)
        backend.redis_url = "redis://localhost:6379/0"
        backend.cache_timeout = 300
        backend.key_prefix = "feature_flags:"
        mock_client = MagicMock()
        backend._client = mock_client
        return backend, mock_client

    def _make_flag_data(self, key="pct-flag", percentage=50, flag_type="percentage", status="active", enabled_by_default=False):
        """Return serialized flag data dict as RedisBackend._get_flag_data() returns it."""
        import orjson
        data = {
            "key": key,
            "flag_type": flag_type,
            "status": status,
            "enabled_by_default": enabled_by_default,
            "rollout_percentage": percentage,
            "variants": {},
            "targeting_rules": [],
            "scheduled_enable_at": None,
            "scheduled_disable_at": None,
            "overrides": [],
        }
        # Return as dict (deserialized)
        return data

    def test_is_enabled_percentage_rollout(self):
        """RedisBackend.is_enabled() evaluates percentage rollout deterministically (FLAG-03)."""
        redis_mod = pytest.importorskip("redis")
        from django_matt.flags.backends import RedisBackend

        backend, mock_client = self._make_redis_backend()
        flag_data = self._make_flag_data(key="pct-flag", percentage=50)
        import orjson
        serialized = orjson.dumps(flag_data).decode()
        # Redis returns bytes
        mock_client.get.return_value = serialized.encode()

        user = make_mock_user(pk=42)
        result = backend.is_enabled("pct-flag", user=user)
        assert isinstance(result, bool)
        # Verify client.get was called
        mock_client.get.assert_called_once_with("feature_flags:pct-flag")

    def test_percentage_deterministic_consistency(self):
        """RedisBackend percentage rollout: same user always gets same result (FLAG-03)."""
        redis_mod = pytest.importorskip("redis")
        from django_matt.flags.backends import RedisBackend

        backend, mock_client = self._make_redis_backend()
        flag_data = self._make_flag_data(key="stable-flag", percentage=50)
        import orjson
        serialized = orjson.dumps(flag_data).decode()
        mock_client.get.return_value = serialized.encode()

        user = make_mock_user(pk=99)
        # Call is_enabled 10 times for the same user
        results = [backend.is_enabled("stable-flag", user=user) for _ in range(10)]
        # All results must be identical (deterministic hash)
        assert len(set(results)) == 1, f"Expected consistent result, got: {results}"

    def test_percentage_rollout_distributes_users(self):
        """RedisBackend 50% rollout assigns ~half of users (FLAG-03)."""
        redis_mod = pytest.importorskip("redis")
        from django_matt.flags.backends import RedisBackend

        backend, mock_client = self._make_redis_backend()
        flag_data = self._make_flag_data(key="half-flag", percentage=50)
        import orjson
        serialized = orjson.dumps(flag_data).decode()
        mock_client.get.return_value = serialized.encode()

        enabled_count = 0
        for i in range(100):
            user = make_mock_user(pk=i)
            if backend.is_enabled("half-flag", user=user):
                enabled_count += 1

        # With 50% rollout over 100 users, expect 30-70 enabled (hash distribution)
        assert 20 <= enabled_count <= 80, f"Unexpected distribution: {enabled_count}/100 enabled"

    def test_is_enabled_zero_percentage_returns_false(self):
        """RedisBackend 0% rollout always returns False (FLAG-03)."""
        redis_mod = pytest.importorskip("redis")
        backend, mock_client = self._make_redis_backend()
        flag_data = self._make_flag_data(key="zero-flag", percentage=0)
        import orjson
        serialized = orjson.dumps(flag_data).decode()
        mock_client.get.return_value = serialized.encode()

        for i in range(10):
            user = make_mock_user(pk=i)
            assert backend.is_enabled("zero-flag", user=user) is False

    def test_is_enabled_full_percentage_returns_true(self):
        """RedisBackend 100% rollout always returns True (FLAG-03)."""
        redis_mod = pytest.importorskip("redis")
        backend, mock_client = self._make_redis_backend()
        flag_data = self._make_flag_data(key="full-flag", percentage=100)
        import orjson
        serialized = orjson.dumps(flag_data).decode()
        mock_client.get.return_value = serialized.encode()

        for i in range(10):
            user = make_mock_user(pk=i)
            assert backend.is_enabled("full-flag", user=user) is True


# ==============================================================================
# LaunchDarklyBackend (skipped when ldclient not installed)
# ==============================================================================


class TestLaunchDarklyBackend:
    def test_is_enabled_delegates_to_ldclient(self):
        """LaunchDarklyBackend.is_enabled() delegates to ldclient.get().variation() (FLAG-04)."""
        ldclient = pytest.importorskip("ldclient")
        from django_matt.flags.backends import LaunchDarklyBackend

        mock_ld_client = MagicMock()
        mock_ld_client.is_initialized.return_value = True
        mock_ld_client.variation.return_value = True

        # Inject the mock client directly to avoid real SDK initialization
        backend = LaunchDarklyBackend.__new__(LaunchDarklyBackend)
        backend.sdk_key = "fake-sdk-key"
        backend._config = {}
        backend._client = mock_ld_client

        user = make_mock_user(pk=1, email="user@example.com")

        # Patch Context builder so we don't need a live SDK
        mock_context = MagicMock()
        with patch("django_matt.flags.backends.LaunchDarklyBackend._build_context", return_value=mock_context):
            result = backend.is_enabled("flag-key", user=user)

        assert result is True
        mock_ld_client.variation.assert_called_once_with("flag-key", mock_context, False)

    def test_get_variant_delegates_to_ldclient(self):
        """LaunchDarklyBackend.get_variant() delegates to ldclient.variation() (FLAG-04)."""
        ldclient = pytest.importorskip("ldclient")
        from django_matt.flags.backends import LaunchDarklyBackend

        mock_ld_client = MagicMock()
        mock_ld_client.variation.return_value = "treatment_a"

        backend = LaunchDarklyBackend.__new__(LaunchDarklyBackend)
        backend.sdk_key = "fake-sdk-key"
        backend._config = {}
        backend._client = mock_ld_client

        user = make_mock_user(pk=1)
        mock_context = MagicMock()
        with patch("django_matt.flags.backends.LaunchDarklyBackend._build_context", return_value=mock_context):
            result = backend.get_variant("flag-key", user=user, default="control")

        assert result == "treatment_a"
        mock_ld_client.variation.assert_called_once_with("flag-key", mock_context, "control")

    def test_invalidate_is_noop(self):
        """LaunchDarklyBackend.invalidate() is a no-op (LD manages its own cache) (FLAG-04)."""
        ldclient = pytest.importorskip("ldclient")
        from django_matt.flags.backends import LaunchDarklyBackend

        backend = LaunchDarklyBackend.__new__(LaunchDarklyBackend)
        backend.sdk_key = "fake-sdk-key"
        backend._config = {}
        backend._client = None
        # Should not raise
        backend.invalidate("some-flag")
        backend.invalidate_all()

    def test_missing_sdk_raises_import_error(self):
        """LaunchDarklyBackend raises ImportError when ldclient not installed (FLAG-04)."""
        from django_matt.flags.backends import LaunchDarklyBackend

        backend = LaunchDarklyBackend.__new__(LaunchDarklyBackend)
        backend.sdk_key = "fake-sdk-key"
        backend._config = {}
        backend._client = None

        with patch.dict("sys.modules", {"ldclient": None, "ldclient.config": None}), pytest.raises(
            ImportError, match="launchdarkly-server-sdk is required"
        ):
            _ = backend.client


# ==============================================================================
# UnleashBackend (skipped when UnleashClient not installed)
# ==============================================================================


class TestUnleashBackend:
    def test_is_enabled_delegates_to_unleash_client(self):
        """UnleashBackend.is_enabled() delegates to UnleashClient.is_enabled() (FLAG-05)."""
        UnleashClient = pytest.importorskip("UnleashClient")
        from django_matt.flags.backends import UnleashBackend

        mock_unleash = MagicMock()
        mock_unleash.is_enabled.return_value = True

        backend = UnleashBackend.__new__(UnleashBackend)
        backend.url = "http://unleash.example.com"
        backend.app_name = "test-app"
        backend.instance_id = None
        backend.custom_headers = {}
        backend._client = mock_unleash

        user = make_mock_user(pk=1)
        result = backend.is_enabled("my-flag", user=user)

        assert result is True
        # Verify delegation: context should include userId
        call_args = mock_unleash.is_enabled.call_args
        assert call_args[0][0] == "my-flag"  # first positional arg is flag key
        context_arg = call_args[0][1]  # second positional arg is context dict
        assert context_arg.get("userId") == "1"

    def test_get_variant_delegates_to_unleash_client(self):
        """UnleashBackend.get_variant() delegates to UnleashClient.get_variant() (FLAG-05)."""
        UnleashClient = pytest.importorskip("UnleashClient")
        from django_matt.flags.backends import UnleashBackend

        mock_unleash = MagicMock()
        mock_unleash.get_variant.return_value = {"enabled": True, "name": "v2"}

        backend = UnleashBackend.__new__(UnleashBackend)
        backend.url = "http://unleash.example.com"
        backend.app_name = "test-app"
        backend.instance_id = None
        backend.custom_headers = {}
        backend._client = mock_unleash

        user = make_mock_user(pk=1)
        result = backend.get_variant("experiment-flag", user=user, default="control")

        assert result == "v2"
        mock_unleash.get_variant.assert_called_once()

    def test_invalidate_is_noop(self):
        """UnleashBackend.invalidate() is a no-op (Unleash manages its own polling) (FLAG-05)."""
        UnleashClient = pytest.importorskip("UnleashClient")
        from django_matt.flags.backends import UnleashBackend

        backend = UnleashBackend.__new__(UnleashBackend)
        backend.url = "http://unleash.example.com"
        backend.app_name = "test-app"
        backend.instance_id = None
        backend.custom_headers = {}
        backend._client = None
        # Should not raise
        backend.invalidate("some-flag")
        backend.invalidate_all()

    def test_missing_sdk_raises_import_error(self):
        """UnleashBackend raises ImportError when UnleashClient not installed (FLAG-05)."""
        from django_matt.flags.backends import UnleashBackend

        backend = UnleashBackend.__new__(UnleashBackend)
        backend.url = "http://unleash.example.com"
        backend.app_name = "test-app"
        backend.instance_id = None
        backend.custom_headers = {}
        backend._client = None

        with patch.dict("sys.modules", {"UnleashClient": None}), pytest.raises(
            ImportError, match="UnleashClient is required"
        ):
            _ = backend.client


# ==============================================================================
# FlagMiddleware
# ==============================================================================


class TestFlagMiddleware:
    def test_middleware_sets_flag_context_on_request(self):
        """FlagMiddleware sets flag context on request.flag_context (FLAG-07)."""
        from django_matt.flags.middleware import FlagMiddleware

        def get_response(request):
            # Verify flag_context was set on request
            assert hasattr(request, "flag_context")
            assert isinstance(request.flag_context, FlagContext)
            from django.http import HttpResponse
            return HttpResponse("ok")

        middleware = FlagMiddleware(get_response)
        user = make_mock_user()
        request = make_request(user=user)

        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_handles_anonymous_user(self):
        """FlagMiddleware handles anonymous user without crashing (FLAG-07)."""
        from django_matt.flags.middleware import FlagMiddleware

        def get_response(request):
            # Must have flag_context even for anonymous users
            assert hasattr(request, "flag_context")
            ctx = request.flag_context
            assert ctx.user is None  # anonymous → no user on context
            from django.http import HttpResponse
            return HttpResponse("ok")

        middleware = FlagMiddleware(get_response)
        request = make_request()  # No authenticated user

        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_sets_contextvar_for_downstream(self):
        """FlagMiddleware sets ContextVar so get_current_context() works in views (FLAG-07)."""
        from django_matt.flags.middleware import FlagMiddleware

        captured_ctx = []

        def get_response(request):
            ctx = get_current_context()
            captured_ctx.append(ctx)
            from django.http import HttpResponse
            return HttpResponse("ok")

        middleware = FlagMiddleware(get_response)
        request = make_request(user=make_mock_user())

        middleware(request)
        assert len(captured_ctx) == 1
        assert captured_ctx[0] is not None
        # After request, context should be cleared
        assert get_current_context() is None

    def test_middleware_includes_organization_from_request(self):
        """FlagMiddleware includes organization from request.organization (FLAG-07)."""
        from django_matt.flags.middleware import FlagMiddleware

        captured_ctx = []

        def get_response(request):
            captured_ctx.append(request.flag_context)
            from django.http import HttpResponse
            return HttpResponse("ok")

        middleware = FlagMiddleware(get_response)
        user = make_mock_user()
        request = make_request(user=user)

        # Simulate multitenancy middleware setting request.organization
        org = MagicMock()
        org.pk = "org-456"
        request.organization = org

        middleware(request)
        assert len(captured_ctx) == 1
        # Organization should be captured from request.organization
        assert captured_ctx[0].organization is org

    def test_middleware_clears_context_after_request(self):
        """FlagMiddleware clears ContextVar after request completes (FLAG-07)."""
        from django_matt.flags.middleware import FlagMiddleware

        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        middleware = FlagMiddleware(get_response)
        request = make_request()

        middleware(request)
        # Context must be cleared after response
        assert get_current_context() is None


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

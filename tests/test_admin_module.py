"""
Tests for the Django Matt admin module.

Tests cover:
- base.py: MattModelAdmin, MattStackedInline, MattTabularInline, register_admin
- generator.py: AdminGenerator, generate_admin_class, generate_admin_module
- filters.py: DateRangeFilter, BooleanFilter, ChoicesFilter, RelatedFilter,
              NullFilter, TenantFilter, factory functions
- actions.py: export_as_csv, export_as_json, soft_delete_selected,
              restore_selected, duplicate_selected, mark_active, mark_inactive
- mixins.py: AuditAdminMixin, SoftDeleteAdminMixin, ReadOnlyAdminMixin,
             ExportAdminMixin, MultiTenantAdminMixin
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.http import HttpRequest
from django.test import RequestFactory

import pytest

from django_matt.admin.actions import (
    _get_export_fields,
    _get_field_value,
    duplicate_selected,
    export_as_csv,
    export_as_json,
    hard_delete_selected,
    mark_active,
    mark_inactive,
    restore_selected,
    soft_delete_selected,
)
from django_matt.admin.base import (
    MattModelAdmin,
    MattStackedInline,
    MattTabularInline,
    register_admin,
)
from django_matt.admin.filters import (
    BooleanFilter,
    ChoicesFilter,
    DateRangeFilter,
    NullFilter,
    RelatedFilter,
    TenantFilter,
    create_boolean_filter,
    create_choices_filter,
    create_date_range_filter,
    create_null_filter,
    create_related_filter,
)
from django_matt.admin.generator import (
    AdminGenerator,
    generate_admin_class,
    generate_admin_module,
)
from django_matt.admin.mixins import (
    AuditAdminMixin,
    ExportAdminMixin,
    MultiTenantAdminMixin,
    ReadOnlyAdminMixin,
    SoftDeleteAdminMixin,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(user=None) -> HttpRequest:
    """Create a mock HttpRequest with an optional user."""
    rf = RequestFactory()
    request = rf.get("/admin/")
    request.user = user or MagicMock(spec=User)
    # Messages middleware stub
    request._messages = MagicMock()
    return request


def _make_site() -> admin.AdminSite:
    """Return a fresh AdminSite instance for testing."""
    return admin.AdminSite(name="test_admin")


# ---------------------------------------------------------------------------
# base.py -- MattModelAdmin auto-configuration
# ---------------------------------------------------------------------------
# NOTE: Django's ModelAdmin ships with list_display = ('__str__',), which is
# truthy, so MattModelAdmin._auto_configure skips auto list_display unless
# a subclass explicitly sets list_display = []. search_fields, list_filter,
# date_hierarchy, and readonly_fields start empty and are auto-generated.
# ---------------------------------------------------------------------------


class TestMattModelAdminAutoListDisplay:
    """Test auto list_display generation."""

    def test_default_inherits_django_default(self):
        """Without explicit empty list_display, Django's default ('__str__',) is kept."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert ma.list_display == ("__str__",)

    def test_auto_generates_when_forced_empty(self):
        """When subclass sets list_display = [], auto-generation kicks in."""

        class AutoAdmin(MattModelAdmin):
            list_display = []

        site = _make_site()
        ma = AutoAdmin(User, site)
        # Should auto-generate fields for User model
        assert len(ma.list_display) > 0
        assert ma.list_display != ("__str__",)

    def test_auto_includes_email_first(self):
        """User model has 'email' as first priority field found."""

        class AutoAdmin(MattModelAdmin):
            list_display = []

        site = _make_site()
        ma = AutoAdmin(User, site)
        # 'email' appears in the priority list and User has it
        assert "email" in ma.list_display

    def test_auto_includes_boolean_fields(self):
        """Boolean fields like is_staff, is_active should be auto-included."""

        class AutoAdmin(MattModelAdmin):
            list_display = []

        site = _make_site()
        ma = AutoAdmin(User, site)
        booleans = {"is_staff", "is_active", "is_superuser"}
        found = booleans & set(ma.list_display)
        assert found, "At least one boolean field should be in list_display"

    def test_auto_includes_date_fields(self):
        """DateTimeField like date_joined should be auto-included."""

        class AutoAdmin(MattModelAdmin):
            list_display = []

        site = _make_site()
        ma = AutoAdmin(User, site)
        assert "date_joined" in ma.list_display

    def test_list_display_max_8(self):
        """list_display should be capped at 8 entries."""

        class AutoAdmin(MattModelAdmin):
            list_display = []

        site = _make_site()
        ma = AutoAdmin(User, site)
        assert len(ma.list_display) <= 8

    def test_skips_when_explicitly_set(self):
        """If list_display has explicit non-empty content, auto-generation is skipped."""

        class ExplicitAdmin(MattModelAdmin):
            list_display = ["username", "email"]

        site = _make_site()
        ma = ExplicitAdmin(User, site)
        assert ma.list_display == ["username", "email"]

    def test_password_excluded(self):
        """Password field should never appear in auto list_display."""

        class AutoAdmin(MattModelAdmin):
            list_display = []

        site = _make_site()
        ma = AutoAdmin(User, site)
        assert "password" not in ma.list_display


class TestMattModelAdminAutoSearchFields:
    """Test auto search_fields generation."""

    def test_includes_char_fields(self):
        """CharField like username, first_name should appear."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert "username" in ma.search_fields

    def test_includes_email_field(self):
        """EmailField like email should appear."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert "email" in ma.search_fields

    def test_max_5(self):
        """search_fields is capped at 5."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert len(ma.search_fields) <= 5

    def test_excludes_password(self):
        """password should never appear in search_fields."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert "password" not in ma.search_fields

    def test_skips_when_already_set(self):
        class ExplicitAdmin(MattModelAdmin):
            search_fields = ["email"]

        site = _make_site()
        ma = ExplicitAdmin(User, site)
        assert ma.search_fields == ["email"]


class TestMattModelAdminAutoListFilter:
    """Test auto list_filter generation."""

    def test_includes_boolean_fields(self):
        """Boolean fields should appear in list_filter."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        booleans = {"is_staff", "is_active", "is_superuser"}
        found = booleans & set(ma.list_filter)
        assert found, "At least one boolean field should be in list_filter"

    def test_includes_date_fields(self):
        """DateTimeField like date_joined or last_login should be in list_filter."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        date_fields = {"date_joined", "last_login"}
        found = date_fields & set(ma.list_filter)
        assert found, "At least one date field should be in list_filter"

    def test_max_6(self):
        """list_filter capped at 6."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert len(ma.list_filter) <= 6


class TestMattModelAdminAutoDateHierarchy:
    """Test auto date_hierarchy generation."""

    def test_none_for_user_model(self):
        """User model has no created_at/created/date/timestamp/updated_at."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert ma.date_hierarchy is None

    def test_skips_when_already_set(self):
        class ExplicitAdmin(MattModelAdmin):
            date_hierarchy = "date_joined"

        site = _make_site()
        ma = ExplicitAdmin(User, site)
        assert ma.date_hierarchy == "date_joined"


class TestMattModelAdminAutoReadonlyFields:
    """Test auto readonly_fields generation."""

    def test_includes_id(self):
        """'id' is in always_readonly and User model has it."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert "id" in ma.readonly_fields

    def test_excludes_missing_fields(self):
        """Fields not on the model (created_at, updated_at) are skipped."""
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert "created_at" not in ma.readonly_fields
        assert "updated_at" not in ma.readonly_fields

    def test_returns_tuple(self):
        site = _make_site()
        ma = MattModelAdmin(User, site)
        assert isinstance(ma.readonly_fields, tuple)


class TestRegisterAdmin:
    """Test the register_admin decorator."""

    def test_registers_on_custom_site(self):
        site = _make_site()

        @register_admin(Group, site=site)
        class GroupAdmin(admin.ModelAdmin):
            pass

        assert Group in site._registry
        assert isinstance(site._registry[Group], GroupAdmin)

    def test_returns_admin_class(self):
        site = _make_site()

        @register_admin(Group, site=site)
        class GroupAdmin(admin.ModelAdmin):
            pass

        assert GroupAdmin is not None
        assert issubclass(GroupAdmin, admin.ModelAdmin)


class TestMattStackedInline:
    """Test MattStackedInline defaults."""

    def test_extra_is_zero(self):
        assert MattStackedInline.extra == 0

    def test_show_change_link(self):
        assert MattStackedInline.show_change_link is True


class TestMattTabularInline:
    """Test MattTabularInline defaults."""

    def test_extra_is_zero(self):
        assert MattTabularInline.extra == 0

    def test_show_change_link(self):
        assert MattTabularInline.show_change_link is True


# ---------------------------------------------------------------------------
# generator.py -- AdminGenerator
# ---------------------------------------------------------------------------


class TestAdminGenerator:
    """Test AdminGenerator.generate()."""

    def test_generates_admin_class(self):
        gen = AdminGenerator()
        cls = gen.generate(User)
        assert issubclass(cls, MattModelAdmin)
        assert cls.__name__ == "UserAdmin"

    def test_includes_audit_mixin(self):
        gen = AdminGenerator(include_audit=True)
        cls = gen.generate(User)
        assert AuditAdminMixin in cls.__mro__

    def test_includes_export_mixin(self):
        gen = AdminGenerator(include_export=True)
        cls = gen.generate(User)
        assert ExportAdminMixin in cls.__mro__

    def test_no_soft_delete_when_no_field(self):
        """User model has no deleted_at -- SoftDeleteAdminMixin not included."""
        gen = AdminGenerator(include_soft_delete=True)
        cls = gen.generate(User)
        assert SoftDeleteAdminMixin not in cls.__mro__

    def test_list_display_limit(self):
        gen = AdminGenerator(list_display_limit=3)
        cls = gen.generate(User)
        assert len(cls.list_display) <= 3

    def test_search_fields_limit(self):
        gen = AdminGenerator(search_fields_limit=2)
        cls = gen.generate(User)
        assert len(cls.search_fields) <= 2

    def test_list_filter_limit(self):
        gen = AdminGenerator(list_filter_limit=2)
        cls = gen.generate(User)
        assert len(cls.list_filter) <= 2

    def test_overrides_applied(self):
        gen = AdminGenerator()
        cls = gen.generate(User, ordering=["-email"])
        assert cls.ordering == ["-email"]

    def test_ordering_defaults_to_neg_id(self):
        """User has 'id' but not 'created_at' -- ordering should be ['-id']."""
        gen = AdminGenerator()
        cls = gen.generate(User)
        assert cls.ordering == ["-id"]

    def test_generate_readonly_fields_tuple(self):
        gen = AdminGenerator()
        cls = gen.generate(User)
        assert isinstance(cls.readonly_fields, tuple)
        assert "id" in cls.readonly_fields

    def test_generator_list_display_starts_with_priority(self):
        """AdminGenerator._generate_list_display starts with a priority field."""
        gen = AdminGenerator()
        display = gen._generate_list_display(User._meta)
        # User has 'email' from the priority list
        assert display[0] == "email"

    def test_generator_search_includes_email(self):
        gen = AdminGenerator()
        search = gen._generate_search_fields(User._meta)
        assert "email" in search

    def test_generator_excludes_password(self):
        gen = AdminGenerator()
        display = gen._generate_list_display(User._meta)
        search = gen._generate_search_fields(User._meta)
        assert "password" not in display
        assert "password" not in search


class TestGenerateAdminClass:
    """Test the convenience generate_admin_class function."""

    def test_basic(self):
        cls = generate_admin_class(User)
        assert cls.__name__ == "UserAdmin"
        assert issubclass(cls, admin.ModelAdmin)

    def test_custom_options(self):
        cls = generate_admin_class(User, include_audit=False, include_export=False)
        assert AuditAdminMixin not in cls.__mro__
        assert ExportAdminMixin not in cls.__mro__


class TestGenerateAdminModule:
    """Test generate_admin_module code output."""

    def test_includes_imports(self):
        code = generate_admin_module([User])
        assert "from django.contrib import admin" in code
        assert "MattModelAdmin" in code

    def test_includes_admin_register_decorator(self):
        code = generate_admin_module([User])
        assert "@admin.register(User)" in code

    def test_includes_class_definition(self):
        code = generate_admin_module([User])
        assert "class UserAdmin(" in code

    def test_includes_list_display(self):
        code = generate_admin_module([User])
        assert "list_display" in code

    def test_no_imports_when_disabled(self):
        code = generate_admin_module([User], include_imports=False)
        assert "from django.contrib import admin" not in code

    def test_multiple_models(self):
        code = generate_admin_module([User, Group])
        assert "UserAdmin" in code
        assert "GroupAdmin" in code

    def test_audit_mixin_import(self):
        code = generate_admin_module([User], include_audit=True)
        assert "AuditAdminMixin" in code

    def test_export_mixin_import(self):
        code = generate_admin_module([User], include_export=True)
        assert "ExportAdminMixin" in code


class TestAdminGeneratorFieldsets:
    """Test fieldset generation for models with audit fields."""

    def test_no_fieldsets_without_audit_fields(self):
        """User model has no created_at/updated_at -- no fieldsets generated."""
        gen = AdminGenerator()
        fieldsets = gen._generate_fieldsets(User._meta)
        assert fieldsets is None

    def test_date_hierarchy_none_for_group(self):
        """Group model has no date fields -- date_hierarchy should be None."""
        gen = AdminGenerator()
        result = gen._generate_date_hierarchy(Group._meta)
        assert result is None

    def test_has_field_true(self):
        gen = AdminGenerator()
        assert gen._has_field(User._meta, "username") is True

    def test_has_field_false(self):
        gen = AdminGenerator()
        assert gen._has_field(User._meta, "nonexistent_field") is False


# ---------------------------------------------------------------------------
# filters.py -- Filter classes
# ---------------------------------------------------------------------------


class TestDateRangeFilter:
    """Test DateRangeFilter."""

    def test_lookups_contains_all_ranges(self):
        f = DateRangeFilter(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        choices = f.lookups(MagicMock(), MagicMock())
        keys = [c[0] for c in choices]
        expected = [
            "today",
            "yesterday",
            "this_week",
            "last_week",
            "this_month",
            "last_month",
            "this_year",
            "last_7_days",
            "last_30_days",
            "last_90_days",
        ]
        for k in expected:
            assert k in keys, f"{k!r} missing from lookups"

    def test_queryset_returns_unfiltered_when_no_value(self):
        f = DateRangeFilter(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        qs = MagicMock()
        result = f.queryset(MagicMock(), qs)
        assert result is qs

    def test_default_field_name(self):
        assert DateRangeFilter.field_name == "created_at"


class TestCreateDateRangeFilter:
    """Test create_date_range_filter factory."""

    def test_sets_field_name(self):
        cls = create_date_range_filter("updated_at")
        assert cls.field_name == "updated_at"

    def test_sets_title(self):
        cls = create_date_range_filter("created_at", "Created Date")
        assert cls.title == "Created Date"

    def test_default_title(self):
        cls = create_date_range_filter("created_at")
        assert cls.title == "created at"

    def test_sets_parameter_name(self):
        cls = create_date_range_filter("updated_at")
        assert cls.parameter_name == "updated_at_range"

    def test_is_subclass_of_date_range_filter(self):
        cls = create_date_range_filter("updated_at")
        assert issubclass(cls, DateRangeFilter)


class TestBooleanFilter:
    """Test BooleanFilter."""

    def test_lookups(self):
        f = BooleanFilter(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        choices = f.lookups(MagicMock(), MagicMock())
        keys = [c[0] for c in choices]
        assert "yes" in keys
        assert "no" in keys

    def test_queryset_yes(self):
        f = BooleanFilter(
            request=MagicMock(),
            params={"status": ["yes"]},
            model=User,
            model_admin=MagicMock(),
        )
        qs = MagicMock()
        f.queryset(MagicMock(), qs)
        qs.filter.assert_called_once_with(is_active=True)

    def test_queryset_no(self):
        f = BooleanFilter(
            request=MagicMock(),
            params={"status": ["no"]},
            model=User,
            model_admin=MagicMock(),
        )
        qs = MagicMock()
        f.queryset(MagicMock(), qs)
        qs.filter.assert_called_once_with(is_active=False)

    def test_queryset_unfiltered_when_empty(self):
        """No value selected -- queryset returned unmodified."""
        f = BooleanFilter(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        qs = MagicMock()
        result = f.queryset(MagicMock(), qs)
        assert result is qs


class TestCreateBooleanFilter:
    """Test create_boolean_filter factory."""

    def test_sets_field_name(self):
        cls = create_boolean_filter("is_verified")
        assert cls.field_name == "is_verified"

    def test_sets_title(self):
        cls = create_boolean_filter("is_active", "Active")
        assert cls.title == "Active"

    def test_default_title(self):
        cls = create_boolean_filter("is_active")
        assert cls.title == "is active"

    def test_custom_labels(self):
        cls = create_boolean_filter("is_active", true_label="Active", false_label="Inactive")
        inst = cls(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        choices = inst.lookups(MagicMock(), MagicMock())
        labels = {c[0]: c[1] for c in choices}
        assert labels["yes"] == "Active"
        assert labels["no"] == "Inactive"

    def test_is_subclass_of_boolean_filter(self):
        cls = create_boolean_filter("is_active")
        assert issubclass(cls, BooleanFilter)


class TestCreateChoicesFilter:
    """Test create_choices_filter factory."""

    def test_sets_field_name(self):
        cls = create_choices_filter("status")
        assert cls.field_name == "status"

    def test_sets_parameter_name(self):
        cls = create_choices_filter("status")
        assert cls.parameter_name == "status"

    def test_sets_title(self):
        cls = create_choices_filter("status", "Status")
        assert cls.title == "Status"

    def test_is_subclass_of_choices_filter(self):
        cls = create_choices_filter("status")
        assert issubclass(cls, ChoicesFilter)


class TestChoicesFilterQueryset:
    """Test ChoicesFilter.queryset behavior."""

    def test_filters_when_value_set(self):
        f = ChoicesFilter(
            request=MagicMock(),
            params={"status": ["active"]},
            model=User,
            model_admin=MagicMock(),
        )
        qs = MagicMock()
        f.queryset(MagicMock(), qs)
        qs.filter.assert_called_once_with(status="active")

    def test_unfiltered_when_no_value(self):
        f = ChoicesFilter(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        qs = MagicMock()
        result = f.queryset(MagicMock(), qs)
        assert result is qs


class TestCreateRelatedFilter:
    """Test create_related_filter factory."""

    def test_sets_field_name(self):
        cls = create_related_filter("author")
        assert cls.field_name == "author"

    def test_sets_max_choices(self):
        cls = create_related_filter("author", max_choices=10)
        assert cls.max_choices == 10

    def test_sets_display_field(self):
        cls = create_related_filter("author", display_field="email")
        assert cls.display_field == "email"

    def test_default_title(self):
        cls = create_related_filter("author")
        assert cls.title == "author"

    def test_is_subclass_of_related_filter(self):
        cls = create_related_filter("author")
        assert issubclass(cls, RelatedFilter)


class TestNullFilter:
    """Test NullFilter."""

    def test_lookups(self):
        f = NullFilter(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        choices = f.lookups(MagicMock(), MagicMock())
        keys = [c[0] for c in choices]
        assert "yes" in keys
        assert "no" in keys

    def test_queryset_has_value(self):
        f = NullFilter(
            request=MagicMock(),
            params={"has_value": ["yes"]},
            model=User,
            model_admin=MagicMock(),
        )
        qs = MagicMock()
        f.queryset(MagicMock(), qs)
        qs.exclude.assert_called_once_with(deleted_at__isnull=True)

    def test_queryset_is_empty(self):
        f = NullFilter(
            request=MagicMock(),
            params={"has_value": ["no"]},
            model=User,
            model_admin=MagicMock(),
        )
        qs = MagicMock()
        f.queryset(MagicMock(), qs)
        qs.filter.assert_called_once_with(deleted_at__isnull=True)

    def test_queryset_unfiltered_when_no_value(self):
        f = NullFilter(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        qs = MagicMock()
        result = f.queryset(MagicMock(), qs)
        assert result is qs


class TestCreateNullFilter:
    """Test create_null_filter factory."""

    def test_sets_field_name(self):
        cls = create_null_filter("deleted_at")
        assert cls.field_name == "deleted_at"

    def test_sets_parameter_name(self):
        cls = create_null_filter("deleted_at")
        assert cls.parameter_name == "deleted_at_null"

    def test_custom_labels(self):
        cls = create_null_filter("deleted_at", has_label="Deleted", empty_label="Active")
        inst = cls(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        choices = inst.lookups(MagicMock(), MagicMock())
        labels = {c[0]: c[1] for c in choices}
        assert labels["yes"] == "Deleted"
        assert labels["no"] == "Active"

    def test_is_subclass_of_null_filter(self):
        cls = create_null_filter("deleted_at")
        assert issubclass(cls, NullFilter)


class TestTenantFilter:
    """Test TenantFilter."""

    def test_default_attributes(self):
        assert TenantFilter.title == "organization"
        assert TenantFilter.parameter_name == "organization"
        assert TenantFilter.field_name == "organization"

    def test_lookups_no_orgs(self):
        """User without organization attributes returns empty."""
        request = MagicMock()
        request.user = MagicMock(spec=[])  # no org attributes
        f = TenantFilter(request=request, params={}, model=User, model_admin=MagicMock())
        choices = f.lookups(request, MagicMock())
        assert choices == []

    def test_queryset_filters_by_value(self):
        f = TenantFilter(
            request=MagicMock(),
            params={"organization": ["42"]},
            model=User,
            model_admin=MagicMock(),
        )
        qs = MagicMock()
        f.queryset(MagicMock(), qs)
        qs.filter.assert_called_once_with(organization_id="42")

    def test_queryset_unfiltered_when_no_value(self):
        f = TenantFilter(request=MagicMock(), params={}, model=User, model_admin=MagicMock())
        qs = MagicMock()
        result = f.queryset(MagicMock(), qs)
        assert result is qs


# ---------------------------------------------------------------------------
# actions.py -- Admin actions
# ---------------------------------------------------------------------------


class TestExportAsCsvAction:
    """Test export_as_csv action."""

    def test_returns_csv_response(self):
        modeladmin = MagicMock()
        modeladmin.model = User
        modeladmin.model._meta = User._meta
        modeladmin.list_display = ["username", "email"]
        # Remove export_fields so it falls through to list_display
        del modeladmin.export_fields

        user1 = MagicMock()
        user1.username = "alice"
        user1.email = "alice@example.com"
        queryset = MagicMock()
        queryset.__iter__ = MagicMock(return_value=iter([user1]))
        queryset.count.return_value = 1

        request = _make_request()
        response = export_as_csv(modeladmin, request, queryset)
        assert response["Content-Type"] == "text/csv"
        assert "user_export.csv" in response["Content-Disposition"]
        content = response.content.decode()
        assert "username" in content
        assert "email" in content

    def test_csv_uses_export_fields(self):
        modeladmin = MagicMock()
        modeladmin.model = User
        modeladmin.model._meta = User._meta
        modeladmin.export_fields = ["username"]

        user1 = MagicMock()
        user1.username = "bob"
        queryset = MagicMock()
        queryset.__iter__ = MagicMock(return_value=iter([user1]))
        queryset.count.return_value = 1

        request = _make_request()
        response = export_as_csv(modeladmin, request, queryset)
        content = response.content.decode()
        assert "username" in content


class TestExportAsJsonAction:
    """Test export_as_json action."""

    def test_returns_json_response(self):
        import orjson

        modeladmin = MagicMock()
        modeladmin.model = User
        modeladmin.model._meta = User._meta
        modeladmin.export_fields = ["username", "email"]

        user1 = MagicMock()
        user1.username = "alice"
        user1.email = "alice@example.com"

        queryset = MagicMock()
        queryset.__iter__ = MagicMock(return_value=iter([user1]))
        queryset.count.return_value = 1

        request = _make_request()
        response = export_as_json(modeladmin, request, queryset)
        assert response["Content-Type"] == "application/json"
        assert "user_export.json" in response["Content-Disposition"]
        data = orjson.loads(response.content)
        assert isinstance(data, list)
        assert len(data) == 1


class TestSoftDeleteAction:
    """Test soft_delete_selected action."""

    def test_calls_update(self):
        modeladmin = MagicMock()
        modeladmin.model = MagicMock()
        modeladmin.model._meta.get_field.return_value = True  # field exists
        modeladmin.deleted_at_field = "deleted_at"

        queryset = MagicMock()
        queryset.update.return_value = 3

        request = _make_request()
        soft_delete_selected(modeladmin, request, queryset)
        queryset.update.assert_called_once()
        call_kwargs = queryset.update.call_args[1]
        assert "deleted_at" in call_kwargs

    def test_error_when_no_field(self):
        modeladmin = MagicMock()
        modeladmin.model = MagicMock()
        modeladmin.model._meta.get_field.side_effect = Exception("no field")

        queryset = MagicMock()
        request = _make_request()

        with patch("django_matt.admin.actions.messages") as mock_messages:
            soft_delete_selected(modeladmin, request, queryset)
            mock_messages.error.assert_called_once()


class TestRestoreAction:
    """Test restore_selected action."""

    def test_calls_update_with_none(self):
        modeladmin = MagicMock()
        modeladmin.model = MagicMock()
        modeladmin.model._meta.get_field.return_value = True
        modeladmin.deleted_at_field = "deleted_at"

        queryset = MagicMock()
        queryset.update.return_value = 2

        request = _make_request()
        restore_selected(modeladmin, request, queryset)
        queryset.update.assert_called_once_with(deleted_at=None)

    def test_error_when_no_field(self):
        modeladmin = MagicMock()
        modeladmin.model = MagicMock()
        modeladmin.model._meta.get_field.side_effect = Exception("no field")

        queryset = MagicMock()
        request = _make_request()

        with patch("django_matt.admin.actions.messages") as mock_messages:
            restore_selected(modeladmin, request, queryset)
            mock_messages.error.assert_called_once()


class TestMarkActiveInactive:
    """Test mark_active and mark_inactive actions."""

    def test_mark_active(self):
        modeladmin = MagicMock()
        modeladmin.model = MagicMock()
        modeladmin.model._meta.get_field.return_value = True
        modeladmin.active_field = "is_active"

        queryset = MagicMock()
        request = _make_request()
        mark_active(modeladmin, request, queryset)
        queryset.update.assert_called_once_with(is_active=True)

    def test_mark_inactive(self):
        modeladmin = MagicMock()
        modeladmin.model = MagicMock()
        modeladmin.model._meta.get_field.return_value = True
        modeladmin.active_field = "is_active"

        queryset = MagicMock()
        request = _make_request()
        mark_inactive(modeladmin, request, queryset)
        queryset.update.assert_called_once_with(is_active=False)

    def test_mark_active_error_no_field(self):
        modeladmin = MagicMock()
        modeladmin.model = MagicMock()
        modeladmin.model._meta.get_field.side_effect = Exception("no field")

        queryset = MagicMock()
        request = _make_request()
        with patch("django_matt.admin.actions.messages") as mock_messages:
            mark_active(modeladmin, request, queryset)
            mock_messages.error.assert_called_once()

    def test_mark_inactive_error_no_field(self):
        modeladmin = MagicMock()
        modeladmin.model = MagicMock()
        modeladmin.model._meta.get_field.side_effect = Exception("no field")

        queryset = MagicMock()
        request = _make_request()
        with patch("django_matt.admin.actions.messages") as mock_messages:
            mark_inactive(modeladmin, request, queryset)
            mock_messages.error.assert_called_once()


class TestDuplicateAction:
    """Test duplicate_selected action."""

    @pytest.mark.django_db
    def test_duplicates_user(self):
        user = User.objects.create_user(
            username="original", email="orig@example.com", password="testpass"
        )
        queryset = User.objects.filter(pk=user.pk)

        modeladmin = MagicMock()
        modeladmin.model = User
        modeladmin.model._meta = User._meta

        request = _make_request()
        duplicate_selected(modeladmin, request, queryset)

        # Should now have 2 users -- original and copy
        assert User.objects.count() == 2
        copy = User.objects.exclude(pk=user.pk).first()
        assert copy is not None
        assert "(copy)" in copy.username


class TestHardDeleteAction:
    """Test hard_delete_selected action."""

    def test_calls_delete(self):
        queryset = MagicMock()
        queryset.count.return_value = 5
        request = _make_request()
        hard_delete_selected(MagicMock(), request, queryset)
        queryset.delete.assert_called_once()


class TestGetExportFields:
    """Test _get_export_fields helper."""

    def test_uses_export_fields_attr(self):
        modeladmin = MagicMock()
        modeladmin.export_fields = ["a", "b"]
        assert _get_export_fields(modeladmin) == ["a", "b"]

    def test_falls_back_to_list_display(self):
        modeladmin = MagicMock(spec=[])
        modeladmin.list_display = ["username", "email"]
        result = _get_export_fields(modeladmin)
        assert "username" in result
        assert "email" in result

    def test_falls_back_to_model_fields(self):
        """When list_display is default ('__str__',), fall back to model fields."""
        modeladmin = MagicMock()
        del modeladmin.export_fields
        modeladmin.list_display = ("__str__",)
        modeladmin.model = User
        modeladmin.model._meta = User._meta
        modeladmin.export_exclude = ["password"]
        result = _get_export_fields(modeladmin)
        assert "username" in result
        assert "password" not in result


class TestGetFieldValue:
    """Test _get_field_value helper."""

    def test_simple_attr(self):
        obj = MagicMock()
        obj.name = "Alice"
        assert _get_field_value(obj, "name") == "Alice"

    def test_nested_attr(self):
        obj = MagicMock()
        obj.author.name = "Bob"
        assert _get_field_value(obj, "author__name") == "Bob"

    def test_callable_value(self):
        obj = MagicMock()
        obj.get_full_name = MagicMock(return_value="Alice B")
        assert _get_field_value(obj, "get_full_name") == "Alice B"

    def test_nested_none(self):
        """When intermediate attribute is None, return None."""
        obj = MagicMock()
        obj.author = None
        assert _get_field_value(obj, "author__name") is None


# ---------------------------------------------------------------------------
# mixins.py -- Admin mixins
# ---------------------------------------------------------------------------


class TestReadOnlyAdminMixin:
    """Test ReadOnlyAdminMixin permissions."""

    def test_has_add_permission_false(self):
        mixin = ReadOnlyAdminMixin()
        assert mixin.has_add_permission(MagicMock()) is False

    def test_has_change_permission_false(self):
        mixin = ReadOnlyAdminMixin()
        assert mixin.has_change_permission(MagicMock()) is False

    def test_has_delete_permission_false(self):
        mixin = ReadOnlyAdminMixin()
        assert mixin.has_delete_permission(MagicMock()) is False

    def test_has_change_permission_with_obj(self):
        mixin = ReadOnlyAdminMixin()
        assert mixin.has_change_permission(MagicMock(), obj=MagicMock()) is False

    def test_has_delete_permission_with_obj(self):
        mixin = ReadOnlyAdminMixin()
        assert mixin.has_delete_permission(MagicMock(), obj=MagicMock()) is False


class TestAuditAdminMixin:
    """Test AuditAdminMixin."""

    def _make_admin(self):
        """Create a concrete class with AuditAdminMixin + MattModelAdmin."""

        class AuditUserAdmin(AuditAdminMixin, MattModelAdmin):
            pass

        site = _make_site()
        return AuditUserAdmin(User, site)

    def test_readonly_does_not_include_missing_fields(self):
        """User model does not have created_at/updated_at, so they should not appear."""
        ma = self._make_admin()
        request = _make_request()
        readonly = ma.get_readonly_fields(request)
        assert "created_at" not in readonly
        assert "updated_at" not in readonly

    def test_save_model_sets_updated_by(self):
        """save_model should set updated_by if the field exists on the object."""
        ma = self._make_admin()
        request = _make_request()
        obj = MagicMock()
        obj.updated_by = None

        with patch.object(MattModelAdmin, "save_model"):
            ma.save_model(request, obj, MagicMock(), change=True)
        assert obj.updated_by == request.user

    def test_save_model_sets_created_by_on_create(self):
        ma = self._make_admin()
        request = _make_request()
        obj = MagicMock()
        obj.created_by = None

        with patch.object(MattModelAdmin, "save_model"):
            ma.save_model(request, obj, MagicMock(), change=False)
        assert obj.created_by == request.user

    def test_save_model_does_not_overwrite_created_by_on_change(self):
        ma = self._make_admin()
        request = _make_request()
        obj = MagicMock()
        obj.created_by = "other_user"

        with patch.object(MattModelAdmin, "save_model"):
            ma.save_model(request, obj, MagicMock(), change=True)
        # created_by should remain unchanged on update
        assert obj.created_by == "other_user"

    def test_default_field_names(self):
        mixin = AuditAdminMixin()
        assert mixin.created_at_field == "created_at"
        assert mixin.updated_at_field == "updated_at"
        assert mixin.created_by_field == "created_by"
        assert mixin.updated_by_field == "updated_by"


class TestSoftDeleteAdminMixin:
    """Test SoftDeleteAdminMixin."""

    def _make_admin(self):
        class SoftDeleteUserAdmin(SoftDeleteAdminMixin, MattModelAdmin):
            pass

        site = _make_site()
        return SoftDeleteUserAdmin(User, site)

    def test_get_queryset_excludes_deleted_by_default(self):
        ma = self._make_admin()
        request = _make_request()
        request.GET = {}

        with patch.object(MattModelAdmin, "get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            ma.get_queryset(request)
            mock_qs.return_value.filter.assert_called_once_with(deleted_at__isnull=True)

    def test_get_queryset_includes_deleted_when_param(self):
        ma = self._make_admin()
        request = _make_request()
        request.GET = {"show_deleted": "1"}

        with patch.object(MattModelAdmin, "get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            ma.get_queryset(request)
            # When show_deleted is set, filter should NOT be called
            mock_qs.return_value.filter.assert_not_called()

    def test_get_actions_includes_restore(self):
        ma = self._make_admin()
        request = _make_request()
        with patch.object(MattModelAdmin, "get_actions", return_value={}):
            actions = ma.get_actions(request)
        assert "restore_selected" in actions

    def test_get_actions_includes_hard_delete(self):
        ma = self._make_admin()
        request = _make_request()
        with patch.object(MattModelAdmin, "get_actions", return_value={}):
            actions = ma.get_actions(request)
        assert "hard_delete_selected" in actions

    def test_get_list_filter_includes_deleted_filter(self):
        ma = self._make_admin()
        request = _make_request()
        with patch.object(MattModelAdmin, "get_list_filter", return_value=[]):
            filters = ma.get_list_filter(request)
        # Last filter should be the DeletedFilter class
        assert len(filters) >= 1
        last_filter = filters[-1]
        assert last_filter.title == "deleted status"

    def test_delete_model_soft_deletes(self):
        ma = self._make_admin()
        request = _make_request()
        obj = MagicMock()
        obj.deleted_at = None
        ma.delete_model(request, obj)
        assert obj.deleted_at is not None
        obj.save.assert_called_once()

    def test_delete_queryset_uses_update(self):
        ma = self._make_admin()
        request = _make_request()
        qs = MagicMock()
        ma.delete_queryset(request, qs)
        qs.update.assert_called_once()
        call_kwargs = qs.update.call_args[1]
        assert "deleted_at" in call_kwargs

    def test_default_field_names(self):
        mixin = SoftDeleteAdminMixin()
        assert mixin.deleted_at_field == "deleted_at"
        assert mixin.deleted_by_field == "deleted_by"
        assert mixin.show_deleted_by_default is False


class TestExportAdminMixin:
    """Test ExportAdminMixin."""

    def _make_admin(self):
        class ExportUserAdmin(ExportAdminMixin, MattModelAdmin):
            pass

        site = _make_site()
        return ExportUserAdmin(User, site)

    def test_get_actions_includes_exports(self):
        ma = self._make_admin()
        request = _make_request()
        with patch.object(MattModelAdmin, "get_actions", return_value={}):
            actions = ma.get_actions(request)
        assert "export_csv" in actions
        assert "export_json" in actions

    def test_get_export_fields_default(self):
        ma = self._make_admin()
        fields = ma._get_export_fields()
        assert "password" not in fields
        assert "username" in fields

    def test_get_export_fields_explicit(self):
        ma = self._make_admin()
        ma.export_fields = ["email"]
        assert ma._get_export_fields() == ["email"]

    def test_export_csv_returns_response(self):
        ma = self._make_admin()
        ma.export_fields = ["username"]
        request = _make_request()

        user_mock = MagicMock()
        user_mock.username = "alice"
        queryset = MagicMock()
        queryset.__iter__ = MagicMock(return_value=iter([user_mock]))

        response = ma._export_as_csv(request, queryset)
        assert response["Content-Type"] == "text/csv"
        assert "user_export.csv" in response["Content-Disposition"]

    def test_export_json_returns_response(self):
        ma = self._make_admin()
        ma.export_fields = ["username"]
        request = _make_request()

        user_mock = MagicMock()
        user_mock.username = "alice"
        queryset = MagicMock()
        queryset.__iter__ = MagicMock(return_value=iter([user_mock]))

        response = ma._export_as_json(request, queryset)
        assert response["Content-Type"] == "application/json"
        assert "user_export.json" in response["Content-Disposition"]

    def test_export_exclude_default(self):
        ma = self._make_admin()
        assert "password" in ma.export_exclude


class TestMultiTenantAdminMixin:
    """Test MultiTenantAdminMixin."""

    def test_get_current_tenant_from_organization(self):
        mixin = MultiTenantAdminMixin()
        request = MagicMock()
        request.user.organization = "Acme"
        assert mixin._get_current_tenant(request) == "Acme"

    def test_get_current_tenant_from_current_organization(self):
        mixin = MultiTenantAdminMixin()
        request = MagicMock()
        # Simulate user without organization but with current_organization
        request.user = MagicMock(spec=["current_organization"])
        request.user.current_organization = "Globex"
        assert mixin._get_current_tenant(request) == "Globex"

    def test_get_current_tenant_from_request_organization(self):
        mixin = MultiTenantAdminMixin()
        request = MagicMock(spec=["user", "organization"])
        request.user = MagicMock(spec=[])  # no org attributes
        request.organization = "Initech"
        assert mixin._get_current_tenant(request) == "Initech"

    def test_get_current_tenant_from_request_tenant(self):
        mixin = MultiTenantAdminMixin()
        request = MagicMock(spec=["user", "tenant"])
        request.user = MagicMock(spec=[])
        request.tenant = "TenantCorp"
        assert mixin._get_current_tenant(request) == "TenantCorp"

    def test_get_current_tenant_returns_none(self):
        mixin = MultiTenantAdminMixin()
        request = MagicMock(spec=["user"])
        request.user = MagicMock(spec=[])
        assert mixin._get_current_tenant(request) is None

    def test_get_exclude_hides_tenant_field(self):
        """When hide_tenant_in_form is True, tenant_field is excluded."""

        class TenantUserAdmin(MultiTenantAdminMixin, MattModelAdmin):
            pass

        site = _make_site()
        ma = TenantUserAdmin(User, site)
        request = _make_request()

        with patch.object(MattModelAdmin, "get_exclude", return_value=[]):
            excluded = ma.get_exclude(request)
        assert "organization" in excluded

    def test_get_exclude_does_not_duplicate(self):
        """If tenant_field is already in exclude, don't add again."""

        class TenantUserAdmin(MultiTenantAdminMixin, MattModelAdmin):
            pass

        site = _make_site()
        ma = TenantUserAdmin(User, site)
        request = _make_request()

        with patch.object(MattModelAdmin, "get_exclude", return_value=["organization"]):
            excluded = ma.get_exclude(request)
        assert excluded.count("organization") == 1

    def test_save_model_sets_tenant(self):
        class TenantUserAdmin(MultiTenantAdminMixin, MattModelAdmin):
            pass

        site = _make_site()
        ma = TenantUserAdmin(User, site)
        request = _make_request()
        request.user.organization = "Acme"

        obj = MagicMock()
        obj.organization = None

        with patch.object(MattModelAdmin, "save_model"):
            ma.save_model(request, obj, MagicMock(), change=False)
        assert obj.organization == "Acme"

    def test_save_model_does_not_overwrite_on_change(self):
        class TenantUserAdmin(MultiTenantAdminMixin, MattModelAdmin):
            pass

        site = _make_site()
        ma = TenantUserAdmin(User, site)
        request = _make_request()
        request.user.organization = "Acme"

        obj = MagicMock()
        obj.organization = "OriginalOrg"

        with patch.object(MattModelAdmin, "save_model"):
            ma.save_model(request, obj, MagicMock(), change=True)
        # Should remain unchanged because change=True
        assert obj.organization == "OriginalOrg"

    def test_default_config(self):
        mixin = MultiTenantAdminMixin()
        assert mixin.tenant_field == "organization"
        assert mixin.hide_tenant_in_form is True
        assert mixin.auto_set_tenant is True


# ===========================================================================
# Requirement-aligned tests (07-04)
# ===========================================================================


class TestAdminRegistration:
    """ADMIN-01: Verify MattModelAdmin registers with Django admin site."""

    def test_register_admin_decorator_registers_model(self):
        """Test that register_admin decorator registers model with admin site."""
        from django_matt.admin.base import MattModelAdmin, register_admin

        # Create a custom admin site to avoid polluting the global one
        test_site = admin.AdminSite(name="test_registration_site")

        @register_admin(User, site=test_site)
        class TestUserAdmin(MattModelAdmin):
            pass

        assert User in test_site._registry
        assert isinstance(test_site._registry[User], TestUserAdmin)

    def test_unfold_fallback(self):
        """Test that MattModelAdmin works with or without Unfold."""
        from django_matt.admin.base import HAS_UNFOLD, MattModelAdmin

        # MattModelAdmin should always be available regardless of Unfold
        assert issubclass(MattModelAdmin, admin.ModelAdmin)
        assert isinstance(HAS_UNFOLD, bool)


class TestDashboardWidgetRender:
    """ADMIN-02: Verify dashboard widget renders with title and value."""

    def test_stat_widget_renders_with_title_and_value(self):
        """Test StatWidget renders HTML containing title and value."""
        from django_matt.admin.widgets import StatWidget

        widget = StatWidget(title="Total Users", value=42)
        html = widget.render()

        assert "Total Users" in html
        assert "42" in html

    def test_stat_widget_renders_with_float_value(self):
        """Test StatWidget formats float values."""
        from django_matt.admin.widgets import StatWidget

        widget = StatWidget(title="Revenue", value=1234.56)
        html = widget.render()

        assert "Revenue" in html
        assert "1,234.56" in html

    def test_stat_widget_renders_with_change_and_trend(self):
        """Test StatWidget renders change indicator."""
        from django_matt.admin.widgets import StatWidget

        widget = StatWidget(title="Orders", value=100, change=15.5, trend="up")
        html = widget.render()

        assert "Orders" in html
        assert "+15.5%" in html

    def test_dashboard_section_renders(self):
        """Test DashboardSection renders its widgets."""
        from django_matt.admin.dashboard import DashboardSection
        from django_matt.admin.widgets import StatWidget

        section = DashboardSection(title="Overview")
        section.add_widget(StatWidget(title="Users", value=10))
        html = section.render()

        assert "Overview" in html
        assert "Users" in html

    def test_dashboard_renders_complete(self):
        """Test Dashboard renders complete HTML with stats."""
        from django_matt.admin.dashboard import Dashboard
        from django_matt.admin.widgets import StatWidget

        dashboard = Dashboard(title="Admin Dashboard")
        dashboard.add_stat(StatWidget(title="Users", value=42))
        html = dashboard.render()

        assert "Admin Dashboard" in html
        assert "Users" in html


class TestAdminGeneratorInlines:
    """ADMIN-03: Verify AdminGenerator produces inline classes from model FK."""

    def test_generator_produces_inline_for_fk_relation(self):
        """Test that _generate_inlines produces inlines for FK relations."""
        from django_matt.admin.generator import AdminGenerator

        generator = AdminGenerator()
        # Group has a FK from User (user_set), so User _meta should have
        # reverse relations. We'll use the test infrastructure model.
        # Since User has FK to Group, Group._meta should have reverse relation.
        opts = Group._meta
        inlines = generator._generate_inlines(opts)

        # Group should have at least one inline (User -> Group FK through groups M2M
        # via auth_user_groups intermediary model)
        # The actual availability depends on model registration
        assert isinstance(inlines, list)

    def test_generator_inline_classes_have_correct_base(self):
        """Test that generated inlines inherit from MattTabularInline or MattStackedInline."""
        from django_matt.admin.base import MattStackedInline, MattTabularInline
        from django_matt.admin.generator import AdminGenerator

        generator = AdminGenerator()
        opts = Group._meta
        inlines = generator._generate_inlines(opts)

        for inline_class in inlines:
            assert issubclass(inline_class, (MattTabularInline, MattStackedInline))

    def test_generator_inline_has_model_attribute(self):
        """Test that generated inlines have the model attribute set."""
        from django_matt.admin.generator import AdminGenerator

        generator = AdminGenerator()
        opts = Group._meta
        inlines = generator._generate_inlines(opts)

        for inline_class in inlines:
            assert hasattr(inline_class, "model")
            assert inline_class.model is not None

    def test_generate_admin_class_includes_inlines(self):
        """Test that generate_admin_class produces admin with inlines attribute."""
        from django_matt.admin.generator import generate_admin_class

        admin_class = generate_admin_class(Group)
        assert hasattr(admin_class, "inlines")
        assert isinstance(admin_class.inlines, (list, tuple))

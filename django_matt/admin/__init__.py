"""
Django Unfold Admin Integration.

Provides enhanced admin classes, auto-generation utilities, and theming
for Django Unfold - a modern Django admin theme with Tailwind CSS.

Usage:
    from django_matt.admin import MattModelAdmin, register_admin

    # Simple registration
    @register_admin(User)
    class UserAdmin(MattModelAdmin):
        pass

    # Auto-generate admin for a model
    from django_matt.admin import generate_admin_class
    UserAdmin = generate_admin_class(User)

    # Use with multi-tenancy
    from django_matt.admin import TenantModelAdmin

    @register_admin(Project)
    class ProjectAdmin(TenantModelAdmin):
        tenant_field = "organization"

Installation:
    pip install django-unfold
    # or
    uv add django-unfold

    # In settings.py, add BEFORE django.contrib.admin:
    INSTALLED_APPS = [
        "unfold",
        "unfold.contrib.filters",
        "unfold.contrib.forms",
        "unfold.contrib.import_export",
        "unfold.contrib.guardian",
        "unfold.contrib.simple_history",
        "django.contrib.admin",
        ...
    ]
"""

from django_matt.admin.actions import (
    export_as_csv,
    export_as_json,
    restore_selected,
    soft_delete_selected,
)
from django_matt.admin.base import (
    MattModelAdmin,
    MattStackedInline,
    MattTabularInline,
    register_admin,
)
from django_matt.admin.charts import (
    CHART_COLORS,
    PALETTE,
    ChartDataset,
    ChartWidget,
    SparklineWidget,
    comparison_chart,
    model_distribution_chart,
    model_time_series_chart,
)
from django_matt.admin.config import (
    UnfoldConfig,
    configure_unfold,
    get_unfold_settings,
)
from django_matt.admin.dashboard import (
    Dashboard,
    DashboardAdminSite,
    DashboardSection,
    auto_dashboard,
    create_dashboard_template_file,
    get_dashboard_index_template,
)
from django_matt.admin.filters import (
    BooleanFilter,
    ChoicesFilter,
    DateRangeFilter,
    RelatedFilter,
    TenantFilter,
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
from django_matt.admin.pages import (
    AdminPage,
    AdminPageGroup,
    AdminPageRegistry,
    PageBuilderMixin,
    create_page_template_file,
    get_custom_page_template,
    pages,
)
from django_matt.admin.widgets import (
    ActivityWidget,
    ProgressWidget,
    QuickActionsWidget,
    StatWidget,
    TableWidget,
    model_stat_widget,
)

__all__ = [
    # Base classes
    "MattModelAdmin",
    "MattStackedInline",
    "MattTabularInline",
    "register_admin",
    # Mixins
    "AuditAdminMixin",
    "SoftDeleteAdminMixin",
    "MultiTenantAdminMixin",
    "ReadOnlyAdminMixin",
    "ExportAdminMixin",
    # Generator
    "generate_admin_class",
    "generate_admin_module",
    "AdminGenerator",
    # Filters
    "DateRangeFilter",
    "BooleanFilter",
    "ChoicesFilter",
    "RelatedFilter",
    "TenantFilter",
    # Actions
    "export_as_csv",
    "export_as_json",
    "soft_delete_selected",
    "restore_selected",
    # Configuration
    "UnfoldConfig",
    "configure_unfold",
    "get_unfold_settings",
    # Widgets
    "StatWidget",
    "ActivityWidget",
    "QuickActionsWidget",
    "TableWidget",
    "ProgressWidget",
    "model_stat_widget",
    # Charts
    "ChartWidget",
    "ChartDataset",
    "SparklineWidget",
    "model_time_series_chart",
    "model_distribution_chart",
    "comparison_chart",
    "CHART_COLORS",
    "PALETTE",
    # Dashboard
    "Dashboard",
    "DashboardSection",
    "DashboardAdminSite",
    "auto_dashboard",
    "get_dashboard_index_template",
    "create_dashboard_template_file",
    # Pages
    "AdminPage",
    "AdminPageGroup",
    "AdminPageRegistry",
    "pages",
    "PageBuilderMixin",
    "get_custom_page_template",
    "create_page_template_file",
]

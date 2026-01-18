"""
Admin dashboard builder and auto-generated dashboards.

Provides tools to create custom admin index pages with widgets,
charts, and auto-generated model statistics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.db.models import Model
from django.http import HttpRequest
from django.template.response import TemplateResponse
from django.utils.safestring import mark_safe

from django_matt.admin.charts import (
    ChartWidget,
    model_time_series_chart,
)
from django_matt.admin.widgets import (
    ActivityWidget,
    StatWidget,
    model_stat_widget,
)

LayoutType = Literal["grid", "columns", "rows"]


@dataclass
class DashboardSection:
    """A section of the dashboard with a title and widgets."""

    title: str | None = None
    widgets: list[Any] = field(default_factory=list)
    columns: int = 4  # Grid columns (1-4)
    collapsible: bool = False
    collapsed: bool = False

    def add_widget(self, widget: Any):
        """Add a widget to this section."""
        self.widgets.append(widget)
        return self

    def render(self) -> str:
        """Render the section as HTML."""
        widgets_html = []
        for widget in self.widgets:
            if hasattr(widget, "render"):
                widgets_html.append(widget.render())
            else:
                widgets_html.append(str(widget))

        title_html = ""
        if self.title:
            collapse_btn = ""
            if self.collapsible:
                collapse_btn = """
                <button type="button" class="text-gray-400 hover:text-gray-500" onclick="this.closest('.dashboard-section').classList.toggle('collapsed')">
                    <svg class="w-5 h-5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                    </svg>
                </button>
                """

            title_html = f"""
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold text-gray-900 dark:text-white">{self.title}</h2>
                {collapse_btn}
            </div>
            """

        collapsed_class = "collapsed" if self.collapsed else ""
        grid_cols = f"grid-cols-1 md:grid-cols-2 lg:grid-cols-{self.columns}"

        return f"""
        <section class="dashboard-section mb-8 {collapsed_class}">
            {title_html}
            <div class="grid {grid_cols} gap-4">
                {"".join(widgets_html)}
            </div>
        </section>
        """


@dataclass
class Dashboard:
    """
    Admin dashboard builder.

    Create custom admin index pages with widgets, charts, and
    model statistics.

    Example:
        dashboard = Dashboard(title="My Dashboard")
        dashboard.add_stat(model_stat_widget(User, icon="users"))
        dashboard.add_chart(model_time_series_chart(Order))
        dashboard.add_section("Recent Activity", activity_widget)
    """

    title: str = "Dashboard"
    subtitle: str | None = None
    sections: list[DashboardSection] = field(default_factory=list)
    include_chart_js: bool = True
    chart_js_version: str = "4.4.1"

    def __post_init__(self):
        # Initialize default section for stats
        self._stats_section = DashboardSection(columns=4)
        self._charts_section = DashboardSection(title="Analytics", columns=2)
        self._custom_sections: list[DashboardSection] = []

    def add_stat(self, widget: StatWidget):
        """Add a stat widget to the stats row."""
        self._stats_section.add_widget(widget)
        return self

    def add_chart(self, chart: ChartWidget):
        """Add a chart to the charts section."""
        self._charts_section.add_widget(chart)
        return self

    def add_section(self, title: str | None = None, columns: int = 2) -> DashboardSection:
        """Add a custom section and return it for adding widgets."""
        section = DashboardSection(title=title, columns=columns)
        self._custom_sections.append(section)
        return section

    def add_widget(self, widget: Any, section: DashboardSection | None = None):
        """Add a widget to a section (or create new section)."""
        if section is None:
            section = self.add_section(columns=1)
        section.add_widget(widget)
        return self

    def render(self) -> str:
        """Render the complete dashboard as HTML."""
        # Build all sections
        all_sections = []

        if self._stats_section.widgets:
            all_sections.append(self._stats_section)

        if self._charts_section.widgets:
            all_sections.append(self._charts_section)

        all_sections.extend(self._custom_sections)

        sections_html = "\n".join(s.render() for s in all_sections)

        # Subtitle
        subtitle_html = ""
        if self.subtitle:
            subtitle_html = f'<p class="text-gray-500 dark:text-gray-400 mt-1">{self.subtitle}</p>'

        # Chart.js script
        chart_js_html = ""
        if self.include_chart_js:
            chart_js_html = f'<script src="https://cdn.jsdelivr.net/npm/chart.js@{self.chart_js_version}/dist/chart.umd.min.js"></script>'

        return f"""
        {chart_js_html}
        <style>
            .dashboard-section.collapsed .grid {{
                display: none;
            }}
            .dashboard-section.collapsed svg {{
                transform: rotate(-90deg);
            }}
        </style>
        <div class="dashboard">
            <header class="mb-8">
                <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{self.title}</h1>
                {subtitle_html}
            </header>
            {sections_html}
        </div>
        """


def auto_dashboard(
    site: AdminSite | None = None,
    include_models: list[type[Model]] | None = None,
    exclude_models: list[type[Model]] | None = None,
    title: str = "Dashboard",
    show_charts: bool = True,
    show_recent_actions: bool = True,
    max_stats: int = 8,
) -> Dashboard:
    """
    Auto-generate a dashboard from registered admin models.

    Args:
        site: Admin site (defaults to django.contrib.admin.site)
        include_models: Only include these models
        exclude_models: Exclude these models
        title: Dashboard title
        show_charts: Include time series charts
        show_recent_actions: Include recent actions widget
        max_stats: Maximum number of stat widgets

    Returns:
        Configured Dashboard
    """
    site = site or admin.site
    exclude_models = exclude_models or []

    dashboard = Dashboard(title=title)

    # Get registered models
    models_to_show = []

    for model, model_admin in site._registry.items():
        if include_models and model not in include_models:
            continue
        if model in exclude_models:
            continue
        models_to_show.append((model, model_admin))

    # Add stat widgets for each model
    icon_map = {
        "user": "users",
        "order": "shopping",
        "product": "shopping",
        "post": "document",
        "comment": "document",
        "payment": "currency",
        "invoice": "currency",
        "task": "check",
        "log": "document",
    }

    color_cycle = ["primary", "success", "info", "warning", "purple", "teal", "pink", "danger"]

    for i, (model, model_admin) in enumerate(models_to_show[:max_stats]):
        model_name = model._meta.model_name.lower()

        # Try to find an appropriate icon
        icon = None
        for key, icon_name in icon_map.items():
            if key in model_name:
                icon = icon_name
                break
        icon = icon or "database"

        color = color_cycle[i % len(color_cycle)]

        dashboard.add_stat(
            model_stat_widget(
                model,
                icon=icon,
                color=color,
            )
        )

    # Add time series charts for models with date fields
    if show_charts:
        charts_added = 0
        for model, model_admin in models_to_show:
            # Find a date field
            date_field = None
            for field_obj in model._meta.get_fields():
                if hasattr(field_obj, "auto_now_add") and field_obj.auto_now_add:
                    date_field = field_obj.name
                    break
                if field_obj.name in ("created_at", "created", "date_joined", "timestamp", "date"):
                    date_field = field_obj.name
                    break

            if date_field and charts_added < 2:
                dashboard.add_chart(
                    model_time_series_chart(
                        model,
                        date_field=date_field,
                        days=30,
                        color=color_cycle[charts_added % len(color_cycle)],
                    )
                )
                charts_added += 1

    # Add recent actions
    if show_recent_actions:
        activity = ActivityWidget(
            title="Recent Admin Actions",
            show_all_link="/admin/admin/logentry/",
        )
        dashboard.add_widget(activity, dashboard.add_section("Activity", columns=1))

    return dashboard


class DashboardAdminSite(AdminSite):
    """
    Custom admin site with dashboard support.

    Replaces the default admin index with a customizable dashboard.

    Usage:
        from django_matt.admin.dashboard import DashboardAdminSite, auto_dashboard

        admin_site = DashboardAdminSite(name="myadmin")
        admin_site.dashboard = auto_dashboard()

        # In urls.py
        urlpatterns = [
            path("admin/", admin_site.urls),
        ]
    """

    index_template = None  # We'll render our own
    dashboard: Dashboard | None = None
    dashboard_factory: Callable[[HttpRequest], Dashboard] | None = None

    def index(self, request: HttpRequest, extra_context: dict | None = None) -> TemplateResponse:
        """
        Display the dashboard on the admin index page.
        """
        extra_context = extra_context or {}

        # Get or create dashboard
        if self.dashboard_factory:
            dashboard = self.dashboard_factory(request)
        elif self.dashboard:
            dashboard = self.dashboard
        else:
            dashboard = auto_dashboard(site=self)

        extra_context["dashboard_html"] = mark_safe(dashboard.render())
        extra_context["has_dashboard"] = True

        # Call parent but with our custom template
        return super().index(request, extra_context=extra_context)

    def each_context(self, request: HttpRequest) -> dict[str, Any]:
        """Add dashboard context to all admin pages."""
        context = super().each_context(request)
        context["has_dashboard"] = self.dashboard is not None or self.dashboard_factory is not None
        return context


def get_dashboard_index_template() -> str:
    """
    Get a custom admin index template that supports the dashboard.

    This template extends Unfold's admin/index.html and adds dashboard support.
    """
    return """
{% extends "admin/index.html" %}
{% load i18n %}

{% block content %}
{% if has_dashboard and dashboard_html %}
    {{ dashboard_html }}
{% else %}
    {{ block.super }}
{% endif %}
{% endblock %}
"""


def create_dashboard_template_file(path: str = "templates/admin/index.html"):
    """
    Create the dashboard template file.

    Args:
        path: Path to create the template at
    """
    from pathlib import Path

    template_path = Path(path)
    template_path.parent.mkdir(parents=True, exist_ok=True)

    with open(template_path, "w") as f:
        f.write(get_dashboard_index_template())

    return template_path


__all__ = [
    "Dashboard",
    "DashboardSection",
    "DashboardAdminSite",
    "auto_dashboard",
    "get_dashboard_index_template",
    "create_dashboard_template_file",
]

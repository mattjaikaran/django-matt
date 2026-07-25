# file-length-max: 550
"""
Admin dashboard widgets for Django Unfold.

Provides pre-built widget components that integrate seamlessly with
Django Unfold's design system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from django.db.models import Model
from django.utils import timezone

WidgetSize = Literal["sm", "md", "lg", "xl", "full"]
TrendDirection = Literal["up", "down", "neutral"]


@dataclass
class StatWidget:
    """
    Statistics card widget showing a metric with optional trend.

    Displays a single metric with title, value, optional change indicator,
    and optional icon. Styled to match Unfold's design system.
    """

    title: str
    value: str | int | float
    change: float | None = None
    change_label: str = "vs last period"
    trend: TrendDirection = "neutral"
    icon: str | None = None  # Heroicon name or SVG
    color: str = "primary"  # primary, success, warning, danger, info
    size: WidgetSize = "md"
    link: str | None = None
    footer: str | None = None

    def render(self) -> str:
        """Render the widget as HTML."""
        # Color classes for Unfold
        color_classes = {
            "primary": "bg-primary-50 text-primary-700 dark:bg-primary-500/10 dark:text-primary-400",
            "success": "bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-400",
            "warning": "bg-yellow-50 text-yellow-700 dark:bg-yellow-500/10 dark:text-yellow-400",
            "danger": "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400",
            "info": "bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400",
        }

        trend_colors = {
            "up": "text-green-600 dark:text-green-400",
            "down": "text-red-600 dark:text-red-400",
            "neutral": "text-gray-500 dark:text-gray-400",
        }

        trend_icons = {
            "up": "↑",
            "down": "↓",
            "neutral": "→",
        }

        size_classes = {
            "sm": "p-4",
            "md": "p-5",
            "lg": "p-6",
            "xl": "p-8",
            "full": "p-6",
        }

        # Format value
        if isinstance(self.value, float):
            formatted_value = f"{self.value:,.2f}"
        elif isinstance(self.value, int):
            formatted_value = f"{self.value:,}"
        else:
            formatted_value = str(self.value)

        # Build change indicator
        change_html = ""
        if self.change is not None:
            change_sign = "+" if self.change > 0 else ""
            change_html = f"""
            <div class="flex items-center gap-1 text-sm {trend_colors[self.trend]}">
                <span>{trend_icons[self.trend]}</span>
                <span>{change_sign}{self.change:.1f}%</span>
                <span class="text-gray-400 dark:text-gray-500">{self.change_label}</span>
            </div>
            """

        # Build icon
        icon_html = ""
        if self.icon:
            icon_html = f"""
            <div class="flex-shrink-0 {color_classes[self.color]} p-3 rounded-lg">
                {self._get_icon_svg(self.icon)}
            </div>
            """

        # Build footer
        footer_html = ""
        if self.footer:
            footer_html = f"""
            <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 text-sm text-gray-500 dark:text-gray-400">
                {self.footer}
            </div>
            """

        # Wrap in link if provided
        wrapper_start = (
            f'<a href="{self.link}" class="block hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">'
            if self.link
            else ""
        )
        wrapper_end = "</a>" if self.link else ""

        return f"""
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 {size_classes[self.size]}">
            {wrapper_start}
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <p class="text-sm font-medium text-gray-500 dark:text-gray-400">{self.title}</p>
                    <p class="mt-2 text-3xl font-semibold text-gray-900 dark:text-white">{formatted_value}</p>
                    {change_html}
                </div>
                {icon_html}
            </div>
            {footer_html}
            {wrapper_end}
        </div>
        """

    def _get_icon_svg(self, icon_name: str) -> str:
        """Get SVG for common icons."""
        icons = {
            "users": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>',
            "chart": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>',
            "currency": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
            "shopping": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"></path></svg>',
            "document": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
            "clock": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
            "check": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
            "warning": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>',
            "database": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path></svg>',
            "server": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"></path></svg>',
        }
        return icons.get(icon_name, icon_name)  # Return raw SVG if not found


@dataclass
class ActivityWidget:
    """
    Activity feed widget showing recent actions/events.

    Displays a list of recent activities with timestamps,
    styled to match Unfold's design system.
    """

    title: str = "Recent Activity"
    items: list[dict[str, Any]] = field(default_factory=list)
    max_items: int = 5
    show_all_link: str | None = None
    size: WidgetSize = "md"

    def add_item(
        self,
        text: str,
        timestamp: Any = None,
        icon: str | None = None,
        color: str = "primary",
        link: str | None = None,
        user: str | None = None,
    ):
        """Add an activity item."""
        self.items.append(
            {
                "text": text,
                "timestamp": timestamp or timezone.now(),
                "icon": icon,
                "color": color,
                "link": link,
                "user": user,
            }
        )

    def render(self) -> str:
        """Render the widget as HTML."""
        items_html = []

        for item in self.items[: self.max_items]:
            timestamp = item.get("timestamp")
            if hasattr(timestamp, "strftime"):
                time_str = timestamp.strftime("%b %d, %H:%M")
            else:
                time_str = str(timestamp)

            user_html = ""
            if item.get("user"):
                user_html = f'<span class="font-medium text-gray-900 dark:text-white">{item["user"]}</span> '

            link_start = (
                f'<a href="{item["link"]}" class="hover:text-primary-600 dark:hover:text-primary-400">'
                if item.get("link")
                else ""
            )
            link_end = "</a>" if item.get("link") else ""

            items_html.append(f"""
            <li class="py-3 flex items-start gap-3">
                <div class="flex-shrink-0 w-2 h-2 mt-2 rounded-full bg-{item.get("color", "primary")}-500"></div>
                <div class="flex-1 min-w-0">
                    {link_start}
                    <p class="text-sm text-gray-600 dark:text-gray-300">
                        {user_html}{item["text"]}
                    </p>
                    {link_end}
                    <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{time_str}</p>
                </div>
            </li>
            """)

        show_all_html = ""
        if self.show_all_link:
            show_all_html = f"""
            <div class="pt-4 border-t border-gray-100 dark:border-gray-700">
                <a href="{self.show_all_link}" class="text-sm text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300">
                    View all activity →
                </a>
            </div>
            """

        return f"""
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
            <h3 class="text-base font-semibold text-gray-900 dark:text-white mb-4">{self.title}</h3>
            <ul class="divide-y divide-gray-100 dark:divide-gray-700">
                {"".join(items_html)}
            </ul>
            {show_all_html}
        </div>
        """


@dataclass
class QuickActionsWidget:
    """
    Quick actions widget with action buttons.

    Displays a grid of quick action buttons for common tasks.
    """

    title: str = "Quick Actions"
    actions: list[dict[str, Any]] = field(default_factory=list)
    columns: int = 2

    def add_action(
        self,
        label: str,
        url: str,
        icon: str | None = None,
        color: str = "primary",
        description: str | None = None,
    ):
        """Add a quick action."""
        self.actions.append(
            {
                "label": label,
                "url": url,
                "icon": icon,
                "color": color,
                "description": description,
            }
        )

    def render(self) -> str:
        """Render the widget as HTML."""
        actions_html = []

        for action in self.actions:
            icon_html = ""
            if action.get("icon"):
                icon_html = f"""
                <div class="flex-shrink-0 w-10 h-10 rounded-lg bg-{action["color"]}-50 dark:bg-{action["color"]}-500/10 flex items-center justify-center text-{action["color"]}-600 dark:text-{action["color"]}-400">
                    {StatWidget(title="", value="")._get_icon_svg(action["icon"])}
                </div>
                """

            desc_html = ""
            if action.get("description"):
                desc_html = f'<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{action["description"]}</p>'

            actions_html.append(f"""
            <a href="{action["url"]}" class="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">
                {icon_html}
                <div>
                    <p class="text-sm font-medium text-gray-900 dark:text-white">{action["label"]}</p>
                    {desc_html}
                </div>
            </a>
            """)

        grid_cols = f"grid-cols-{self.columns}"

        return f"""
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
            <h3 class="text-base font-semibold text-gray-900 dark:text-white mb-4">{self.title}</h3>
            <div class="grid {grid_cols} gap-2">
                {"".join(actions_html)}
            </div>
        </div>
        """


@dataclass
class TableWidget:
    """
    Simple table widget for displaying data.

    Displays a table with configurable columns, styled for Unfold.
    """

    title: str
    columns: list[dict[str, str]] = field(default_factory=list)  # [{key, label}]
    rows: list[dict[str, Any]] = field(default_factory=list)
    show_all_link: str | None = None
    max_rows: int = 5

    def render(self) -> str:
        """Render the widget as HTML."""
        # Header
        headers = "".join(
            f'<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{col["label"]}</th>'
            for col in self.columns
        )

        # Rows
        rows_html = []
        for row in self.rows[: self.max_rows]:
            cells = "".join(
                f'<td class="px-4 py-3 text-sm text-gray-900 dark:text-white whitespace-nowrap">{row.get(col["key"], "")}</td>'
                for col in self.columns
            )
            rows_html.append(f"<tr class='hover:bg-gray-50 dark:hover:bg-white/5'>{cells}</tr>")

        show_all_html = ""
        if self.show_all_link:
            show_all_html = f"""
            <div class="px-4 py-3 border-t border-gray-100 dark:border-gray-700">
                <a href="{self.show_all_link}" class="text-sm text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300">
                    View all →
                </a>
            </div>
            """

        return f"""
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div class="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
                <h3 class="text-base font-semibold text-gray-900 dark:text-white">{self.title}</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead class="bg-gray-50 dark:bg-gray-800">
                        <tr>{headers}</tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
                        {"".join(rows_html)}
                    </tbody>
                </table>
            </div>
            {show_all_html}
        </div>
        """


@dataclass
class ProgressWidget:
    """
    Progress/goal widget showing completion status.
    """

    title: str
    current: int | float
    target: int | float
    label: str = ""
    color: str = "primary"
    show_percentage: bool = True

    def render(self) -> str:
        """Render the widget as HTML."""
        percentage = min(100, (self.current / self.target) * 100) if self.target > 0 else 0

        percentage_html = ""
        if self.show_percentage:
            percentage_html = f'<span class="text-sm font-medium text-gray-900 dark:text-white">{percentage:.0f}%</span>'

        return f"""
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
            <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400">{self.title}</h3>
                {percentage_html}
            </div>
            <div class="flex items-baseline gap-2 mb-3">
                <span class="text-2xl font-semibold text-gray-900 dark:text-white">{self.current:,.0f}</span>
                <span class="text-sm text-gray-500 dark:text-gray-400">/ {self.target:,.0f} {self.label}</span>
            </div>
            <div class="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div class="h-full bg-{self.color}-500 rounded-full transition-all duration-500" style="width: {percentage}%"></div>
            </div>
        </div>
        """


def model_stat_widget(
    model: type[Model],
    title: str | None = None,
    icon: str | None = None,
    color: str = "primary",
    filter_kwargs: dict | None = None,
    link: str | None = None,
    compare_days: int = 7,
) -> StatWidget:
    """
    Create a stat widget from a Django model.

    Args:
        model: Django model class
        title: Widget title (defaults to model verbose name plural)
        icon: Icon name
        color: Widget color
        filter_kwargs: Filter queryset
        link: Link to admin changelist
        compare_days: Days to compare for trend

    Returns:
        Configured StatWidget
    """
    from django.contrib.admin.sites import site

    filter_kwargs = filter_kwargs or {}
    title = title or model._meta.verbose_name_plural.title()

    # Get current count
    current_count = model.objects.filter(**filter_kwargs).count()

    # Get previous period count for comparison
    now = timezone.now()
    cutoff = now - timezone.timedelta(days=compare_days)

    # Try to find a date field for comparison
    date_field = None
    for field in model._meta.get_fields():
        if hasattr(field, "auto_now_add") and field.auto_now_add:
            date_field = field.name
            break
        if field.name in ("created_at", "created", "date_joined", "timestamp"):
            date_field = field.name
            break

    change = None
    trend = "neutral"

    if date_field:
        recent_count = model.objects.filter(
            **filter_kwargs, **{f"{date_field}__gte": cutoff}
        ).count()

        prev_cutoff = cutoff - timezone.timedelta(days=compare_days)
        prev_count = model.objects.filter(
            **filter_kwargs, **{f"{date_field}__gte": prev_cutoff, f"{date_field}__lt": cutoff}
        ).count()

        if prev_count > 0:
            change = ((recent_count - prev_count) / prev_count) * 100
            trend = "up" if change > 0 else "down" if change < 0 else "neutral"

    # Auto-generate admin link
    if link is None:
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        if site.is_registered(model):
            link = f"/admin/{app_label}/{model_name}/"

    return StatWidget(
        title=title,
        value=current_count,
        change=change,
        change_label=f"vs last {compare_days} days",
        trend=trend,
        icon=icon,
        color=color,
        link=link,
    )


__all__ = [
    "StatWidget",
    "ActivityWidget",
    "QuickActionsWidget",
    "TableWidget",
    "ProgressWidget",
    "model_stat_widget",
]

"""
Chart components for Django Unfold admin dashboards.

Provides Chart.js-based chart widgets that integrate with Unfold's design system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal
from uuid import uuid4

from django.db.models import Avg, Count, Model, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

import orjson

ChartType = Literal["line", "bar", "doughnut", "pie", "area", "radar"]


# Unfold-compatible color palette
CHART_COLORS = {
    "primary": {
        "bg": "rgba(79, 70, 229, 0.1)",
        "border": "rgb(79, 70, 229)",
    },
    "success": {
        "bg": "rgba(34, 197, 94, 0.1)",
        "border": "rgb(34, 197, 94)",
    },
    "warning": {
        "bg": "rgba(234, 179, 8, 0.1)",
        "border": "rgb(234, 179, 8)",
    },
    "danger": {
        "bg": "rgba(239, 68, 68, 0.1)",
        "border": "rgb(239, 68, 68)",
    },
    "info": {
        "bg": "rgba(59, 130, 246, 0.1)",
        "border": "rgb(59, 130, 246)",
    },
    "purple": {
        "bg": "rgba(168, 85, 247, 0.1)",
        "border": "rgb(168, 85, 247)",
    },
    "pink": {
        "bg": "rgba(236, 72, 153, 0.1)",
        "border": "rgb(236, 72, 153)",
    },
    "teal": {
        "bg": "rgba(20, 184, 166, 0.1)",
        "border": "rgb(20, 184, 166)",
    },
}

# Extended palette for multiple datasets
PALETTE = ["primary", "success", "warning", "danger", "info", "purple", "pink", "teal"]


@dataclass
class ChartDataset:
    """A single dataset for a chart."""

    label: str
    data: list[int | float]
    color: str = "primary"
    fill: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to Chart.js dataset format."""
        colors = CHART_COLORS.get(self.color, CHART_COLORS["primary"])
        return {
            "label": self.label,
            "data": self.data,
            "backgroundColor": colors["bg"] if self.fill else colors["border"],
            "borderColor": colors["border"],
            "borderWidth": 2,
            "fill": self.fill,
            "tension": 0.4,
        }


@dataclass
class ChartWidget:
    """
    Chart widget using Chart.js.

    Renders a chart that integrates with Unfold's design system,
    with automatic dark mode support.
    """

    title: str
    chart_type: ChartType = "line"
    labels: list[str] = field(default_factory=list)
    datasets: list[ChartDataset] = field(default_factory=list)
    height: int = 300
    show_legend: bool = True
    show_grid: bool = True
    stacked: bool = False
    subtitle: str | None = None

    def __post_init__(self):
        self._id = f"chart-{uuid4().hex[:8]}"

    def add_dataset(
        self,
        label: str,
        data: list[int | float],
        color: str = "primary",
        fill: bool = False,
    ):
        """Add a dataset to the chart."""
        self.datasets.append(
            ChartDataset(
                label=label,
                data=data,
                color=color,
                fill=fill,
            )
        )

    def _get_chart_config(self) -> dict[str, Any]:
        """Generate Chart.js configuration."""
        # Determine if this is a pie/doughnut chart
        is_radial = self.chart_type in ("pie", "doughnut")

        # For radial charts, use full colors for backgrounds
        if is_radial and self.datasets:
            colors = [
                CHART_COLORS[PALETTE[i % len(PALETTE)]]["border"] for i in range(len(self.labels))
            ]
            datasets = [
                {
                    "data": self.datasets[0].data,
                    "backgroundColor": colors,
                    "borderColor": colors,
                    "borderWidth": 2,
                }
            ]
        else:
            datasets = [ds.to_dict() for ds in self.datasets]

        # Chart type mapping
        chart_type = self.chart_type
        if chart_type == "area":
            chart_type = "line"
            for ds in datasets:
                ds["fill"] = True

        config = {
            "type": chart_type,
            "data": {
                "labels": self.labels,
                "datasets": datasets,
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "legend": {
                        "display": self.show_legend,
                        "position": "bottom" if is_radial else "top",
                        "labels": {
                            "usePointStyle": True,
                            "padding": 15,
                        },
                    },
                    "tooltip": {
                        "mode": "index",
                        "intersect": False,
                    },
                },
            },
        }

        # Add scales for non-radial charts
        if not is_radial:
            config["options"]["scales"] = {
                "x": {
                    "stacked": self.stacked,
                    "grid": {
                        "display": self.show_grid,
                        "color": "rgba(156, 163, 175, 0.1)",
                    },
                    "ticks": {
                        "color": "rgb(156, 163, 175)",
                    },
                },
                "y": {
                    "stacked": self.stacked,
                    "beginAtZero": True,
                    "grid": {
                        "display": self.show_grid,
                        "color": "rgba(156, 163, 175, 0.1)",
                    },
                    "ticks": {
                        "color": "rgb(156, 163, 175)",
                    },
                },
            }

        return config

    def render(self) -> str:
        """Render the chart widget as HTML."""
        config_json = orjson.dumps(self._get_chart_config()).decode()

        subtitle_html = ""
        if self.subtitle:
            subtitle_html = (
                f'<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{self.subtitle}</p>'
            )

        return f"""
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
            <div class="mb-4">
                <h3 class="text-base font-semibold text-gray-900 dark:text-white">{self.title}</h3>
                {subtitle_html}
            </div>
            <div style="height: {self.height}px;">
                <canvas id="{self._id}"></canvas>
            </div>
            <script>
                (function() {{
                    const ctx = document.getElementById('{self._id}');
                    if (ctx) {{
                        new Chart(ctx, {config_json});
                    }}
                }})();
            </script>
        </div>
        """


@dataclass
class SparklineWidget:
    """
    Compact sparkline chart for inline display.

    Useful for showing trends in stat cards or tables.
    """

    data: list[int | float]
    color: str = "primary"
    width: int = 100
    height: int = 30
    fill: bool = True

    def __post_init__(self):
        self._id = f"sparkline-{uuid4().hex[:8]}"

    def render(self) -> str:
        """Render the sparkline as HTML."""
        colors = CHART_COLORS.get(self.color, CHART_COLORS["primary"])

        config = {
            "type": "line",
            "data": {
                "labels": [""] * len(self.data),
                "datasets": [
                    {
                        "data": self.data,
                        "backgroundColor": colors["bg"],
                        "borderColor": colors["border"],
                        "borderWidth": 2,
                        "fill": self.fill,
                        "tension": 0.4,
                        "pointRadius": 0,
                    }
                ],
            },
            "options": {
                "responsive": False,
                "maintainAspectRatio": False,
                "plugins": {
                    "legend": {"display": False},
                    "tooltip": {"enabled": False},
                },
                "scales": {
                    "x": {"display": False},
                    "y": {"display": False},
                },
            },
        }

        config_json = orjson.dumps(config).decode()

        return f"""
        <div style="width: {self.width}px; height: {self.height}px; display: inline-block;">
            <canvas id="{self._id}"></canvas>
        </div>
        <script>
            (function() {{
                const ctx = document.getElementById('{self._id}');
                if (ctx) {{
                    new Chart(ctx, {config_json});
                }}
            }})();
        </script>
        """


def model_time_series_chart(
    model: type[Model],
    date_field: str = "created_at",
    title: str | None = None,
    days: int = 30,
    group_by: Literal["day", "week", "month"] = "day",
    aggregate: Literal["count", "sum", "avg"] = "count",
    value_field: str | None = None,
    filter_kwargs: dict | None = None,
    color: str = "primary",
    chart_type: ChartType = "line",
    fill: bool = True,
) -> ChartWidget:
    """
    Create a time series chart from a Django model.

    Args:
        model: Django model class
        date_field: Field to use for date grouping
        title: Chart title
        days: Number of days to include
        group_by: Grouping period (day, week, month)
        aggregate: Aggregation function
        value_field: Field to aggregate (for sum/avg)
        filter_kwargs: Additional queryset filters
        color: Chart color
        chart_type: Type of chart
        fill: Whether to fill the area under the line

    Returns:
        Configured ChartWidget
    """
    filter_kwargs = filter_kwargs or {}
    title = title or f"{model._meta.verbose_name_plural.title()} Over Time"

    # Calculate date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    # Choose truncation function
    trunc_func = {
        "day": TruncDate,
        "week": TruncWeek,
        "month": TruncMonth,
    }.get(group_by, TruncDate)

    # Build queryset
    queryset = (
        model.objects.filter(**filter_kwargs, **{f"{date_field}__gte": start_date})
        .annotate(period=trunc_func(date_field))
        .values("period")
    )

    # Apply aggregation
    if aggregate == "count":
        queryset = queryset.annotate(value=Count("id"))
    elif aggregate == "sum" and value_field:
        queryset = queryset.annotate(value=Sum(value_field))
    elif aggregate == "avg" and value_field:
        queryset = queryset.annotate(value=Avg(value_field))
    else:
        queryset = queryset.annotate(value=Count("id"))

    queryset = queryset.order_by("period")

    # Convert to dict for easy lookup
    data_dict = {row["period"]: row["value"] for row in queryset}

    # Generate all periods
    labels = []
    data = []
    current = start_date

    while current <= end_date:
        if group_by == "day":
            labels.append(current.strftime("%b %d"))
            data.append(float(data_dict.get(current, 0)))
            current += timedelta(days=1)
        elif group_by == "week":
            week_start = current - timedelta(days=current.weekday())
            labels.append(week_start.strftime("%b %d"))
            data.append(float(data_dict.get(week_start, 0)))
            current += timedelta(weeks=1)
        else:  # month
            labels.append(current.strftime("%b %Y"))
            # Find month start
            month_start = current.replace(day=1)
            data.append(float(data_dict.get(month_start, 0)))
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

    chart = ChartWidget(
        title=title,
        chart_type=chart_type,
        labels=labels,
        subtitle=f"Last {days} days",
    )
    chart.add_dataset(
        label=model._meta.verbose_name_plural.title(),
        data=data,
        color=color,
        fill=fill,
    )

    return chart


def model_distribution_chart(
    model: type[Model],
    field: str,
    title: str | None = None,
    chart_type: ChartType = "doughnut",
    filter_kwargs: dict | None = None,
    limit: int = 8,
) -> ChartWidget:
    """
    Create a distribution chart (pie/doughnut) from a Django model field.

    Args:
        model: Django model class
        field: Field to group by
        title: Chart title
        chart_type: pie or doughnut
        filter_kwargs: Additional queryset filters
        limit: Maximum number of categories

    Returns:
        Configured ChartWidget
    """
    filter_kwargs = filter_kwargs or {}
    title = (
        title or f"{model._meta.verbose_name_plural.title()} by {field.replace('_', ' ').title()}"
    )

    # Get distribution
    queryset = (
        model.objects.filter(**filter_kwargs)
        .values(field)
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )

    labels = []
    data = []

    for row in queryset:
        value = row[field]
        # Handle choices fields
        model_field = model._meta.get_field(field)
        if hasattr(model_field, "choices") and model_field.choices:
            choices_dict = dict(model_field.choices)
            label = choices_dict.get(value, str(value))
        else:
            label = str(value) if value is not None else "None"

        labels.append(label)
        data.append(row["count"])

    chart = ChartWidget(
        title=title,
        chart_type=chart_type,
        labels=labels,
        height=250,
    )
    chart.add_dataset(
        label="Count",
        data=data,
    )

    return chart


def comparison_chart(
    title: str,
    series: list[dict[str, Any]],
    labels: list[str],
    chart_type: ChartType = "bar",
    stacked: bool = False,
) -> ChartWidget:
    """
    Create a comparison chart with multiple series.

    Args:
        title: Chart title
        series: List of {label, data, color} dicts
        labels: X-axis labels
        chart_type: bar or line
        stacked: Whether to stack bars

    Returns:
        Configured ChartWidget
    """
    chart = ChartWidget(
        title=title,
        chart_type=chart_type,
        labels=labels,
        stacked=stacked,
    )

    for i, s in enumerate(series):
        chart.add_dataset(
            label=s["label"],
            data=s["data"],
            color=s.get("color", PALETTE[i % len(PALETTE)]),
        )

    return chart


__all__ = [
    "ChartWidget",
    "ChartDataset",
    "SparklineWidget",
    "model_time_series_chart",
    "model_distribution_chart",
    "comparison_chart",
    "CHART_COLORS",
    "PALETTE",
]

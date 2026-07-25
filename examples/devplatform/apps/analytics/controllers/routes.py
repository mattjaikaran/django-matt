from django_matt import DjangoMattAPI

from .analytics_controller import AnalyticsController


def register_analytics_routes(api: DjangoMattAPI) -> None:
    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/analytics/summary",
        tags=["Analytics"],
    )(AnalyticsController.get_usage_summary)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/analytics/daily",
        tags=["Analytics"],
    )(AnalyticsController.get_daily_metrics)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/analytics/timeseries",
        tags=["Analytics"],
    )(AnalyticsController.get_time_series)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/analytics/stream",
        tags=["Analytics"],
    )(AnalyticsController.stream_metrics)

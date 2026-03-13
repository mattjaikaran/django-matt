from django_matt import MattAPI

from .dashboard_controller import DashboardController


def register_dashboard_routes(api: MattAPI) -> None:
    api.get(
        "organizations/<str:org_id>/dashboard",
        tags=["Dashboard"],
    )(DashboardController.get_dashboard)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/dashboard",
        tags=["Dashboard"],
    )(DashboardController.get_project_dashboard)

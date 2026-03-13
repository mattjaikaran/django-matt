from django_matt import MattAPI

from .gateway_controller import GatewayController


def register_gateway_routes(api: MattAPI) -> None:
    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/logs",
        tags=["Gateway"],
    )(GatewayController.list_request_logs)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/logs/errors",
        tags=["Gateway"],
    )(GatewayController.get_error_logs)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/logs/<str:log_id>",
        tags=["Gateway"],
    )(GatewayController.get_request_log)

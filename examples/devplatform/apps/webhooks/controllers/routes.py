from django_matt import MattAPI

from apps.webhooks.schemas import WebhookSchema

from .webhook_controller import WebhookController


def register_webhook_routes(api: MattAPI) -> None:
    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/webhooks",
        tags=["Webhooks"],
    )(WebhookController.list_webhooks)

    api.post(
        "organizations/<str:org_id>/projects/<str:project_id>/webhooks",
        response_model=WebhookSchema,
        status_code=201,
        tags=["Webhooks"],
    )(WebhookController.create_webhook)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/webhooks/<str:webhook_id>",
        response_model=WebhookSchema,
        tags=["Webhooks"],
    )(WebhookController.get_webhook)

    api.patch(
        "organizations/<str:org_id>/projects/<str:project_id>/webhooks/<str:webhook_id>",
        response_model=WebhookSchema,
        tags=["Webhooks"],
    )(WebhookController.update_webhook)

    api.delete(
        "organizations/<str:org_id>/projects/<str:project_id>/webhooks/<str:webhook_id>",
        tags=["Webhooks"],
    )(WebhookController.delete_webhook)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/webhooks/<str:webhook_id>/deliveries",
        tags=["Webhooks"],
    )(WebhookController.list_deliveries)

    api.post(
        "organizations/<str:org_id>/projects/<str:project_id>/webhooks/<str:webhook_id>/deliveries/<str:delivery_id>/retry",
        tags=["Webhooks"],
    )(WebhookController.retry_delivery)

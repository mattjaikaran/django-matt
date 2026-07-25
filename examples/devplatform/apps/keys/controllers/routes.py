from django_matt import DjangoMattAPI

from apps.keys.schemas import APIKeyCreatedSchema

from .api_key_controller import APIKeyController


def register_key_routes(api: DjangoMattAPI) -> None:
    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>/keys",
        tags=["API Keys"],
    )(APIKeyController.list_keys)

    api.post(
        "organizations/<str:org_id>/projects/<str:project_id>/keys",
        response_model=APIKeyCreatedSchema,
        status_code=201,
        tags=["API Keys"],
    )(APIKeyController.create_key)

    api.post(
        "organizations/<str:org_id>/projects/<str:project_id>/keys/<str:key_id>/rotate",
        response_model=APIKeyCreatedSchema,
        tags=["API Keys"],
    )(APIKeyController.rotate_key)

    api.delete(
        "organizations/<str:org_id>/projects/<str:project_id>/keys/<str:key_id>",
        tags=["API Keys"],
    )(APIKeyController.revoke_key)

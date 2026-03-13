from django_matt import MattAPI

from apps.stores.schemas import StoreSchema

from .store_controller import StoreController


def register_store_routes(api: MattAPI) -> None:
    api.get(
        "stores",
        tags=["Stores"],
    )(StoreController.list_stores)

    api.post(
        "stores",
        response_model=StoreSchema,
        status_code=201,
        tags=["Stores"],
    )(StoreController.create_store)

    api.get(
        "stores/<str:store_id>",
        response_model=StoreSchema,
        tags=["Stores"],
    )(StoreController.get_store)

    api.patch(
        "stores/<str:store_id>",
        response_model=StoreSchema,
        tags=["Stores"],
    )(StoreController.update_store)

    api.delete(
        "stores/<str:store_id>",
        tags=["Stores"],
    )(StoreController.delete_store)

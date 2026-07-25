from django_matt import DjangoMattAPI

from apps.search.schemas import SearchResponseSchema

from .search_controller import SearchController


def register_search_routes(api: DjangoMattAPI) -> None:
    api.get(
        "search",
        response_model=SearchResponseSchema,
        tags=["Search"],
    )(SearchController.search)

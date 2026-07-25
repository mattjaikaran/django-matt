from django_matt import DjangoMattAPI

from apps.reviews.schemas import ReviewSchema, ReviewSummarySchema

from .review_controller import ReviewController


def register_review_routes(api: DjangoMattAPI) -> None:
    api.get(
        "products/<str:product_id>/reviews",
        tags=["Reviews"],
    )(ReviewController.list_reviews)

    api.get(
        "products/<str:product_id>/reviews/summary",
        response_model=ReviewSummarySchema,
        tags=["Reviews"],
    )(ReviewController.get_review_summary)

    api.post(
        "products/<str:product_id>/reviews",
        response_model=ReviewSchema,
        status_code=201,
        tags=["Reviews"],
    )(ReviewController.create_review)

    api.patch(
        "reviews/<str:review_id>",
        response_model=ReviewSchema,
        tags=["Reviews"],
    )(ReviewController.update_review)

    api.delete(
        "reviews/<str:review_id>",
        tags=["Reviews"],
    )(ReviewController.delete_review)

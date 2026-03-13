from django.db.models import Avg, Count
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError

from apps.catalog.models import Product
from apps.orders.models import Order
from apps.reviews.models import Review
from apps.reviews.schemas import (
    ReviewCreateSchema,
    ReviewSchema,
    ReviewSummarySchema,
    ReviewUpdateSchema,
)


class ReviewController(APIController):
    prefix = "/reviews"
    tags = ["Reviews"]

    @staticmethod
    async def list_reviews(request, product_id: str) -> dict:
        """List reviews for a product, paginated, ordered by -created_at."""
        params = request.GET
        limit = min(int(params.get("limit", "20")), 100)
        offset = int(params.get("offset", "0"))

        # Verify product exists
        if not await Product.objects.filter(id=product_id).aexists():
            raise NotFoundAPIError("Product not found")

        qs = Review.objects.filter(product_id=product_id).order_by("-created_at")
        total = await qs.acount()
        reviews_qs = qs[offset : offset + limit]

        items = []
        async for review in reviews_qs:
            items.append(
                ReviewSchema(
                    id=str(review.id),
                    user_id=review.user_id,
                    product_id=str(review.product_id),
                    rating=review.rating,
                    title=review.title,
                    body=review.body,
                    is_verified_purchase=review.is_verified_purchase,
                    created_at=review.created_at,
                    updated_at=review.updated_at,
                ).model_dump(mode="json")
            )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def get_review_summary(request, product_id: str) -> dict:
        """Get review summary stats for a product."""
        if not await Product.objects.filter(id=product_id).aexists():
            raise NotFoundAPIError("Product not found")

        qs = Review.objects.filter(product_id=product_id)

        stats = await qs.aaggregate(
            avg_rating=Avg("rating"),
            total=Count("id"),
        )

        # Build rating distribution
        distribution: dict[str, int] = {}
        for i in range(1, 6):
            count = await qs.filter(rating=i).acount()
            distribution[str(i)] = count

        return ReviewSummarySchema(
            average_rating=float(stats.get("avg_rating") or 0),
            total_reviews=stats.get("total", 0),
            rating_distribution=distribution,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def create_review(request, product_id: str) -> dict:
        """Create a review for a product."""
        body = request.json
        data = ReviewCreateSchema(**body)

        # Verify product exists
        product = await Product.objects.filter(id=product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        # Check user hasn't already reviewed this product
        existing = await Review.objects.filter(
            user=request.user, product_id=product_id
        ).aexists()
        if existing:
            raise ValidationAPIError("You have already reviewed this product")

        # Check if user has a completed order containing this product
        is_verified = await Order.objects.filter(
            user=request.user,
            status__in=["delivered", "confirmed"],
            items__product_id=product_id,
        ).aexists()

        review = await Review.objects.acreate(
            user=request.user,
            product_id=product_id,
            rating=data.rating,
            title=data.title,
            body=data.body,
            is_verified_purchase=is_verified,
        )

        return ReviewSchema(
            id=str(review.id),
            user_id=review.user_id,
            product_id=str(review.product_id),
            rating=review.rating,
            title=review.title,
            body=review.body,
            is_verified_purchase=review.is_verified_purchase,
            created_at=review.created_at,
            updated_at=review.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_review(request, review_id: str) -> dict:
        """Update a review. Must be author."""
        review = await Review.objects.filter(
            id=review_id, user=request.user
        ).afirst()
        if not review:
            raise NotFoundAPIError("Review not found")

        body = request.json
        data = ReviewUpdateSchema(**body)
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(review, field, value)
        await review.asave()

        return ReviewSchema(
            id=str(review.id),
            user_id=review.user_id,
            product_id=str(review.product_id),
            rating=review.rating,
            title=review.title,
            body=review.body,
            is_verified_purchase=review.is_verified_purchase,
            created_at=review.created_at,
            updated_at=review.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_review(request, review_id: str) -> dict:
        """Delete a review. Must be author."""
        deleted, _ = await Review.objects.filter(
            id=review_id, user=request.user
        ).adelete()
        if not deleted:
            raise NotFoundAPIError("Review not found")
        return {"message": "Review deleted"}

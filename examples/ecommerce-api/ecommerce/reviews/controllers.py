"""API controllers for reviews app."""

from uuid import UUID

from django.db.models import Avg, Count, Q
from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError

from ecommerce.catalog.models import Product
from ecommerce.orders.models import Order
from ecommerce.reviews.models import Review, ReviewVote
from ecommerce.reviews.schemas import (
    PaginatedReviewsResponse,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
    ReviewStatsResponse,
    ReviewUpdate,
    ReviewVoteRequest,
    ReviewVoteResponse,
)


class ReviewController(APIController):
    """Review management controller."""

    prefix = "/reviews"
    tags = ["Reviews"]

    @staticmethod
    async def get_product_reviews(
        product_id: UUID,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "created_at",  # created_at, rating, helpful
        rating: int | None = None,
        verified_only: bool = False,
    ) -> PaginatedReviewsResponse:
        """Get reviews for a product."""
        queryset = Review.objects.filter(product_id=product_id, status="approved")

        # Filter by rating
        if rating:
            queryset = queryset.filter(rating=rating)

        # Filter verified purchases only
        if verified_only:
            queryset = queryset.filter(verified_purchase=True)

        # Sorting
        if sort_by == "rating":
            queryset = queryset.order_by("-rating", "-created_at")
        elif sort_by == "helpful":
            queryset = queryset.order_by("-helpful_votes", "-created_at")
        else:
            queryset = queryset.order_by("-created_at")

        # Pagination
        total = await queryset.acount()
        pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size

        reviews = queryset.select_related("user")[offset : offset + page_size]

        items = [
            ReviewListResponse(
                id=r.id,
                user_name=r.user.full_name or "Anonymous",
                rating=r.rating,
                title=r.title,
                content=r.content,
                verified_purchase=r.verified_purchase,
                helpful_votes=r.helpful_votes,
                created_at=r.created_at,
            )
            async for r in reviews
        ]

        # Include stats on first page
        stats = None
        if page == 1:
            stats = await ReviewController._get_product_stats(product_id)

        return PaginatedReviewsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
            stats=stats,
        )

    @staticmethod
    async def get_product_review_stats(product_id: UUID) -> ReviewStatsResponse:
        """Get review statistics for a product."""
        return await ReviewController._get_product_stats(product_id)

    @staticmethod
    async def _get_product_stats(product_id: UUID) -> ReviewStatsResponse:
        """Calculate review statistics for a product."""
        reviews = Review.objects.filter(product_id=product_id, status="approved")

        # Aggregate stats
        stats = await reviews.aaggregate(
            avg_rating=Avg("rating"),
            total=Count("id"),
            verified_count=Count("id", filter=Q(verified_purchase=True)),
            with_images=Count("id", filter=Q(images__isnull=False)),
        )

        # Get rating distribution
        distribution = {}
        for i in range(1, 6):
            count = await reviews.filter(rating=i).acount()
            distribution[i] = count

        return ReviewStatsResponse(
            product_id=product_id,
            average_rating=float(stats.get("avg_rating") or 0),
            total_reviews=stats.get("total", 0),
            rating_distribution=distribution,
            verified_purchase_count=stats.get("verified_count", 0),
            with_images_count=stats.get("with_images", 0),
        )

    @staticmethod
    @jwt_required
    async def create_review(request, data: ReviewCreate) -> ReviewResponse:
        """Create a product review."""
        # Check product exists
        product = await Product.objects.filter(id=data.product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        # Check if user already reviewed this product
        existing = await Review.objects.filter(
            product=product, user=request.user
        ).afirst()
        if existing:
            raise ValidationAPIError("You have already reviewed this product")

        # Check if verified purchase
        verified = await Order.objects.filter(
            user=request.user,
            status=Order.Status.DELIVERED,
            items__product=product,
        ).aexists()

        review = await Review.objects.acreate(
            product=product,
            user=request.user,
            rating=data.rating,
            title=data.title,
            content=data.content,
            pros=data.pros,
            cons=data.cons,
            verified_purchase=verified,
            status=Review.Status.PENDING,  # Requires moderation
        )

        return ReviewResponse(
            id=review.id,
            product_id=product.id,
            product_name=product.name,
            user_name=request.user.full_name or "Anonymous",
            user_avatar=request.user.avatar.url if request.user.avatar else None,
            rating=review.rating,
            title=review.title,
            content=review.content,
            pros=review.pros,
            cons=review.cons,
            verified_purchase=review.verified_purchase,
            status=review.status,
            helpful_votes=0,
            not_helpful_votes=0,
            helpfulness_score=0.0,
            images=[],
            created_at=review.created_at,
            updated_at=review.updated_at,
        )

    @staticmethod
    @jwt_required
    async def update_review(
        request, review_id: UUID, data: ReviewUpdate
    ) -> ReviewResponse:
        """Update a review."""
        review = await Review.objects.filter(
            id=review_id, user=request.user
        ).select_related("product").afirst()

        if not review:
            raise NotFoundAPIError("Review not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(review, key, value)

        # Reset to pending for re-moderation
        review.status = Review.Status.PENDING
        await review.asave()

        return ReviewResponse(
            id=review.id,
            product_id=review.product.id,
            product_name=review.product.name,
            user_name=request.user.full_name or "Anonymous",
            user_avatar=request.user.avatar.url if request.user.avatar else None,
            rating=review.rating,
            title=review.title,
            content=review.content,
            pros=review.pros,
            cons=review.cons,
            verified_purchase=review.verified_purchase,
            status=review.status,
            helpful_votes=review.helpful_votes,
            not_helpful_votes=review.not_helpful_votes,
            helpfulness_score=review.helpfulness_score,
            images=[],
            created_at=review.created_at,
            updated_at=review.updated_at,
        )

    @staticmethod
    @jwt_required
    async def delete_review(request, review_id: UUID) -> dict[str, str]:
        """Delete a review."""
        deleted, _ = await Review.objects.filter(
            id=review_id, user=request.user
        ).adelete()

        if not deleted:
            raise NotFoundAPIError("Review not found")

        return {"message": "Review deleted successfully"}

    @staticmethod
    @jwt_required
    async def vote_review(
        request, review_id: UUID, data: ReviewVoteRequest
    ) -> ReviewVoteResponse:
        """Vote on a review's helpfulness."""
        review = await Review.objects.filter(id=review_id).afirst()
        if not review:
            raise NotFoundAPIError("Review not found")

        # Can't vote on own review
        if review.user_id == request.user.id:
            raise ValidationAPIError("Cannot vote on your own review")

        # Check existing vote
        existing = await ReviewVote.objects.filter(
            review=review, user=request.user
        ).afirst()

        if existing:
            # Update vote if different
            if existing.is_helpful != data.is_helpful:
                # Adjust counts
                if existing.is_helpful:
                    review.helpful_votes -= 1
                    review.not_helpful_votes += 1
                else:
                    review.helpful_votes += 1
                    review.not_helpful_votes -= 1

                existing.is_helpful = data.is_helpful
                await existing.asave()
                await review.asave()
        else:
            # Create new vote
            await ReviewVote.objects.acreate(
                review=review,
                user=request.user,
                is_helpful=data.is_helpful,
            )

            # Update counts
            if data.is_helpful:
                review.helpful_votes += 1
            else:
                review.not_helpful_votes += 1
            await review.asave()

        return ReviewVoteResponse(
            success=True,
            helpful_votes=review.helpful_votes,
            not_helpful_votes=review.not_helpful_votes,
        )

    @staticmethod
    @jwt_required
    async def get_my_reviews(request) -> list[ReviewResponse]:
        """Get current user's reviews."""
        reviews = Review.objects.filter(user=request.user).select_related(
            "product"
        ).order_by("-created_at")

        result = []
        async for review in reviews:
            result.append(
                ReviewResponse(
                    id=review.id,
                    product_id=review.product.id,
                    product_name=review.product.name,
                    user_name=request.user.full_name or "Anonymous",
                    user_avatar=request.user.avatar.url if request.user.avatar else None,
                    rating=review.rating,
                    title=review.title,
                    content=review.content,
                    pros=review.pros,
                    cons=review.cons,
                    verified_purchase=review.verified_purchase,
                    status=review.status,
                    helpful_votes=review.helpful_votes,
                    not_helpful_votes=review.not_helpful_votes,
                    helpfulness_score=review.helpfulness_score,
                    images=[],
                    created_at=review.created_at,
                    updated_at=review.updated_at,
                )
            )

        return result

    @staticmethod
    @jwt_required
    async def moderate_review(
        request, review_id: UUID, action: str, notes: str = ""
    ) -> ReviewResponse:
        """Moderate a review (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        review = await Review.objects.filter(id=review_id).select_related(
            "product", "user"
        ).afirst()

        if not review:
            raise NotFoundAPIError("Review not found")

        if action == "approve":
            review.status = Review.Status.APPROVED
        elif action == "reject":
            review.status = Review.Status.REJECTED
        else:
            raise ValidationAPIError("Invalid action")

        review.moderation_notes = notes
        review.moderated_by = request.user
        review.moderated_at = timezone.now()
        await review.asave()

        return ReviewResponse(
            id=review.id,
            product_id=review.product.id,
            product_name=review.product.name,
            user_name=review.user.full_name or "Anonymous",
            user_avatar=review.user.avatar.url if review.user.avatar else None,
            rating=review.rating,
            title=review.title,
            content=review.content,
            pros=review.pros,
            cons=review.cons,
            verified_purchase=review.verified_purchase,
            status=review.status,
            helpful_votes=review.helpful_votes,
            not_helpful_votes=review.not_helpful_votes,
            helpfulness_score=review.helpfulness_score,
            images=[],
            created_at=review.created_at,
            updated_at=review.updated_at,
        )

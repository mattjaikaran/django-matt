"""Pydantic schemas for reviews app."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Review Image Schemas
# =============================================================================


class ReviewImageResponse(BaseModel):
    """Review image response schema."""

    id: UUID
    image: str
    caption: str
    display_order: int

    class Config:
        from_attributes = True


# =============================================================================
# Review Schemas
# =============================================================================


class ReviewCreate(BaseModel):
    """Review creation schema."""

    product_id: UUID
    rating: int = Field(ge=1, le=5)
    title: str = ""
    content: str = Field(min_length=10)
    pros: list[str] = []
    cons: list[str] = []


class ReviewUpdate(BaseModel):
    """Review update schema."""

    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = None
    content: str | None = Field(default=None, min_length=10)
    pros: list[str] | None = None
    cons: list[str] | None = None


class ReviewResponse(BaseModel):
    """Review response schema."""

    id: UUID
    product_id: UUID
    product_name: str
    user_name: str
    user_avatar: str | None = None
    rating: int
    title: str
    content: str
    pros: list[str]
    cons: list[str]
    verified_purchase: bool
    status: str
    helpful_votes: int
    not_helpful_votes: int
    helpfulness_score: float
    images: list[ReviewImageResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    """Review list response (minimal)."""

    id: UUID
    user_name: str
    rating: int
    title: str
    content: str
    verified_purchase: bool
    helpful_votes: int
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Review Vote Schemas
# =============================================================================


class ReviewVoteRequest(BaseModel):
    """Review vote request schema."""

    is_helpful: bool


class ReviewVoteResponse(BaseModel):
    """Review vote response schema."""

    success: bool
    helpful_votes: int
    not_helpful_votes: int


# =============================================================================
# Review Aggregation Schemas
# =============================================================================


class ReviewStatsResponse(BaseModel):
    """Review statistics for a product."""

    product_id: UUID
    average_rating: float
    total_reviews: int
    rating_distribution: dict[int, int]  # {5: 100, 4: 50, 3: 20, 2: 5, 1: 2}
    verified_purchase_count: int
    with_images_count: int


# =============================================================================
# Pagination Schemas
# =============================================================================


class PaginatedReviewsResponse(BaseModel):
    """Paginated reviews response."""

    items: list[ReviewListResponse]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_prev: bool
    stats: ReviewStatsResponse | None = None  # Include stats in first page

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    product_id: str
    rating: int
    title: str
    body: str
    is_verified_purchase: bool
    created_at: datetime
    updated_at: datetime


class ReviewCreateSchema(BaseModel):
    product_id: str
    rating: int = Field(ge=1, le=5)
    title: str = Field(max_length=255)
    body: str = ""


class ReviewUpdateSchema(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = Field(default=None, max_length=255)
    body: str | None = None


class ReviewSummarySchema(BaseModel):
    average_rating: float
    total_reviews: int
    rating_distribution: dict[str, int]

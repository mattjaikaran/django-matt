"""Pydantic schemas for comments app."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CommentAuthorSummary(BaseModel):
    id: UUID
    username: str
    full_name: str

    class Config:
        from_attributes = True


class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    author: CommentAuthorSummary | None = None
    display_name: str
    content: str
    parent_id: UUID | None = None
    replies: list["CommentResponse"] = []
    is_approved: bool

    @field_validator("replies", mode="before")
    @classmethod
    def coerce_replies(cls, v):
        if hasattr(v, "all"):
            return list(v.all())
        return v
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


CommentResponse.model_rebuild()


class CommentCreate(BaseModel):
    post_id: UUID
    content: str = Field(min_length=1, max_length=2000)
    parent_id: UUID | None = None
    # For unauthenticated commenters
    author_name: str = Field(default="", max_length=100)
    author_email: str = Field(default="", max_length=254)


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

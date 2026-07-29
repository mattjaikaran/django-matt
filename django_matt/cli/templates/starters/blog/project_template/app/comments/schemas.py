from ninja import Schema
from pydantic import Field, EmailStr


class CommentSchema(Schema):
    id: str
    author_name: str
    body: str
    approved: bool
    created_at: str

    class Config:
        from_attributes = True


class CommentCreateSchema(Schema):
    author_name: str = Field(..., min_length=1, max_length=100)
    author_email: EmailStr
    body: str = Field(..., min_length=1)

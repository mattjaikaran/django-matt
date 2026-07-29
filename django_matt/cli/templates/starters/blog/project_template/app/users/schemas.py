from ninja import Schema
from pydantic import EmailStr, Field


class RegisterSchema(Schema):
    username: str = Field(..., min_length=3, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginSchema(Schema):
    email: EmailStr
    password: str


class UserSchema(Schema):
    id: str
    username: str
    email: str
    bio: str | None = None
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class TokenResponse(Schema):
    access: str
    refresh: str
    user: UserSchema


class RefreshSchema(Schema):
    refresh: str


class RefreshResponse(Schema):
    access: str

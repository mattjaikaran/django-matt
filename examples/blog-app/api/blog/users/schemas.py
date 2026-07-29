"""Pydantic schemas for users app."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class AuthorProfileResponse(BaseModel):
    bio: str = ""
    avatar: str | None = None
    website: str = ""
    twitter: str = ""
    github: str = ""
    linkedin: str = ""
    location: str = ""
class UserPublicResponse(BaseModel):
    id: UUID
    username: str
    full_name: str
    author_profile: AuthorProfileResponse | None = None

    @field_validator("author_profile", mode="before")
    @classmethod
    def coerce_author_profile(cls, v):
        if v is None:
            return None
        if hasattr(v, "user"):
            avatar_url = None
            if v.avatar and getattr(v.avatar, "name", None):
                try:
                    avatar_url = v.avatar.url
                except (ValueError, OSError):
                    pass
            return AuthorProfileResponse(
                bio=v.bio or "",
                avatar=avatar_url,
                website=v.website or "",
                twitter=v.twitter or "",
                github=v.github or "",
                linkedin=v.linkedin or "",
                location=v.location or "",
            )
        return v

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    first_name: str
    last_name: str
    full_name: str
    is_staff: bool
    date_joined: datetime
    author_profile: AuthorProfileResponse | None = None

    @field_validator("author_profile", mode="before")
    @classmethod
    def coerce_author_profile(cls, v):
        if v is None:
            return None
        if hasattr(v, "user"):
            avatar_url = None
            if v.avatar and getattr(v.avatar, "name", None):
                try:
                    avatar_url = v.avatar.url
                except (ValueError, OSError):
                    pass
            return AuthorProfileResponse(
                bio=v.bio or "",
                avatar=avatar_url,
                website=v.website or "",
                twitter=v.twitter or "",
                github=v.github or "",
                linkedin=v.linkedin or "",
                location=v.location or "",
            )
        return v

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=8)
    first_name: str = ""
    last_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access: str
    refresh: str
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh: str


class RefreshResponse(BaseModel):
    access: str


class ProfileUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    bio: str | None = None
    website: str | None = None
    twitter: str | None = None
    github: str | None = None
    linkedin: str | None = None
    location: str | None = None

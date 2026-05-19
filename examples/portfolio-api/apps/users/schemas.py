from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    bio: str
    avatar_url: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    date_joined: datetime


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str


class RegisterResponseSchema(BaseModel):
    user: UserSchema
    access_token: str
    refresh_token: str


class ProfileUpdateSchema(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    bio: str | None = None
    avatar_url: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None

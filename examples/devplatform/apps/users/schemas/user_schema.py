from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    first_name: str = ""
    last_name: str = ""
    avatar_url: str | None = None
    bio: str = ""
    date_joined: datetime


class UserCreateSchema(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8, max_length=128)
    first_name: str = ""
    last_name: str = ""


class UserUpdateSchema(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None

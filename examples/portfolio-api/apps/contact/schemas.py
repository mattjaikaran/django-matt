from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ContactMessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    subject: str
    message: str
    is_read: bool
    created_at: datetime
    updated_at: datetime


class ContactCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    subject: str = Field(default="", max_length=255)
    message: str = Field(min_length=1)

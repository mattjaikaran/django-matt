from ninja import Schema
from pydantic import EmailStr


class ContactMessageSchema(Schema):
    id: str
    name: str
    email: str
    subject: str | None = None
    message: str
    is_read: bool
    created_at: str

    class Config:
        from_attributes = True


class ContactCreateSchema(Schema):
    name: str
    email: EmailStr
    subject: str | None = None
    message: str

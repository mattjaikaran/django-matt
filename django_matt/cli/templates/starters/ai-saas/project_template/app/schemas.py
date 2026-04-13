"""Pydantic schemas for {{ project_name }}."""

from datetime import datetime

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = ""
    model: str = "claude-sonnet-4-20250514"


class ConversationSchema(BaseModel):
    id: int
    title: str
    model: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str


class MessageSchema(BaseModel):
    id: int
    role: str
    content: str
    token_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentCreate(BaseModel):
    title: str
    content: str
    metadata: dict = {}


class DocumentSchema(BaseModel):
    id: int
    title: str
    content: str
    metadata: dict
    embedded: bool
    created_at: datetime

    model_config = {"from_attributes": True}

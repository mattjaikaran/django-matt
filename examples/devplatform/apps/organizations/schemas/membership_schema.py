from datetime import datetime

from pydantic import BaseModel, ConfigDict

from apps.users.schemas import UserSchema


class MembershipSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    is_active: bool
    created_at: datetime
    user: UserSchema


class MembershipUpdateSchema(BaseModel):
    role: str | None = None
    is_active: bool | None = None

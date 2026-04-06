from __future__ import annotations

from typing import Any

from pydantic import Field

from django_matt.events.bus import Event


class UserCreatedEvent(Event):
    __event_type__: str = "user.created"
    event_type: str = "user.created"
    user_id: int | str | None = None
    email: str | None = None


class UserUpdatedEvent(Event):
    __event_type__: str = "user.updated"
    event_type: str = "user.updated"
    user_id: int | str | None = None
    changes: dict[str, Any] = Field(default_factory=dict)


class UserDeletedEvent(Event):
    __event_type__: str = "user.deleted"
    event_type: str = "user.deleted"
    user_id: int | str | None = None


class ModelCreatedEvent(Event):
    __event_type__: str = "model.created"
    event_type: str = "model.created"
    model_name: str = ""
    instance_id: int | str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ModelUpdatedEvent(Event):
    __event_type__: str = "model.updated"
    event_type: str = "model.updated"
    model_name: str = ""
    instance_id: int | str | None = None
    changes: dict[str, Any] = Field(default_factory=dict)


class ModelDeletedEvent(Event):
    __event_type__: str = "model.deleted"
    event_type: str = "model.deleted"
    model_name: str = ""
    instance_id: int | str | None = None


class RequestEvent(Event):
    __event_type__: str = "request"
    event_type: str = "request"
    method: str = ""
    path: str = ""
    status_code: int = 0
    duration_ms: float = 0.0
    user_id: int | str | None = None

"""
Session authentication schemas.

Pydantic schemas for session-based authentication.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class SessionLoginSchema(BaseModel):
    """Schema for session login request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")
    remember_me: bool = Field(
        default=False,
        description="Extend session duration",
    )


class SessionInfoSchema(BaseModel):
    """Schema for session information response."""

    session_key: str = Field(..., description="Session identifier")
    created: Optional[str] = Field(None, description="Session creation time")
    last_activity: Optional[str] = Field(None, description="Last activity time")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    expires: Optional[str] = Field(None, description="Session expiration time")
    is_current: bool = Field(
        default=False,
        description="Whether this is the current session",
    )


class SessionListSchema(BaseModel):
    """Schema for list of user sessions."""

    sessions: List[SessionInfoSchema] = Field(
        default_factory=list,
        description="List of active sessions",
    )
    total: int = Field(..., description="Total number of sessions")


class CSRFTokenSchema(BaseModel):
    """Schema for CSRF token response."""

    csrf_token: str = Field(..., description="CSRF token for form submissions")


class SessionUserSchema(BaseModel):
    """Schema for authenticated user info."""

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    username: Optional[str] = Field(None, description="Username")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    is_active: bool = Field(..., description="Whether user is active")
    is_staff: bool = Field(default=False, description="Whether user is staff")
    date_joined: Optional[datetime] = Field(None, description="Date user joined")
    last_login: Optional[datetime] = Field(None, description="Last login time")


class SessionStatusSchema(BaseModel):
    """Schema for session status response."""

    authenticated: bool = Field(..., description="Whether user is authenticated")
    user: Optional[SessionUserSchema] = Field(
        None,
        description="User info if authenticated",
    )
    session: Optional[SessionInfoSchema] = Field(
        None,
        description="Session info if authenticated",
    )
    csrf_token: str = Field(..., description="CSRF token")


class LogoutResponseSchema(BaseModel):
    """Schema for logout response."""

    success: bool = Field(default=True, description="Logout successful")
    message: str = Field(default="Logged out successfully")


class RevokeSessionSchema(BaseModel):
    """Schema for revoking a session."""

    session_key: str = Field(..., description="Session key to revoke")


class RevokeAllSessionsSchema(BaseModel):
    """Schema for revoking all other sessions."""

    keep_current: bool = Field(
        default=True,
        description="Keep the current session active",
    )


class RevokeSessionsResponseSchema(BaseModel):
    """Schema for revoke sessions response."""

    revoked_count: int = Field(..., description="Number of sessions revoked")
    message: str = Field(..., description="Response message")

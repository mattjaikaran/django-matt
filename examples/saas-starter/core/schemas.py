"""
Pydantic schemas for core app.

Includes:
- User schemas
- Organization schemas
- Membership schemas
- Authentication schemas
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# User Schemas
# =============================================================================

class UserBase(BaseModel):
    email: EmailStr
    first_name: str = ""
    last_name: str = ""


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    notification_preferences: Optional[dict] = None


class UserResponse(UserBase):
    id: UUID
    avatar_url: str = ""
    is_active: bool
    is_verified: bool
    timezone: str
    locale: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(UserResponse):
    """Extended user profile with preferences."""
    notification_preferences: dict = {}
    last_login_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None


class UserMiniResponse(BaseModel):
    """Minimal user info for references."""
    id: UUID
    email: EmailStr
    first_name: str = ""
    last_name: str = ""
    avatar_url: str = ""

    class Config:
        from_attributes = True

    @property
    def display_name(self) -> str:
        if self.first_name:
            return self.first_name
        return self.email.split("@")[0]


# =============================================================================
# Organization Schemas
# =============================================================================

class OrganizationBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class OrganizationCreate(OrganizationBase):
    description: str = ""
    website: str = ""


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    settings: Optional[dict] = None
    allowed_email_domains: Optional[list[str]] = None


class OrganizationResponse(OrganizationBase):
    id: UUID
    description: str = ""
    logo_url: str = ""
    website: str = ""
    plan: str
    is_personal: bool
    member_count: int = 0
    project_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationDetailResponse(OrganizationResponse):
    """Detailed organization with settings."""
    owner: UserMiniResponse
    settings: dict = {}
    plan_limits: dict = {}
    allowed_email_domains: list[str] = []


class OrganizationMiniResponse(BaseModel):
    """Minimal organization info."""
    id: UUID
    name: str
    slug: str
    logo_url: str = ""

    class Config:
        from_attributes = True


# =============================================================================
# Team Schemas
# =============================================================================

class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class TeamCreate(TeamBase):
    description: str = ""


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[dict] = None


class TeamResponse(TeamBase):
    id: UUID
    description: str = ""
    organization_id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TeamDetailResponse(TeamResponse):
    """Team with member count."""
    member_count: int = 0


# =============================================================================
# Membership Schemas
# =============================================================================

class MembershipCreate(BaseModel):
    user_id: Optional[UUID] = None
    email: Optional[EmailStr] = None  # For invitations
    role: str = "member"
    team_ids: list[UUID] = []


class MembershipUpdate(BaseModel):
    role: Optional[str] = None
    team_ids: Optional[list[UUID]] = None


class MembershipResponse(BaseModel):
    id: UUID
    user: UserMiniResponse
    organization_id: UUID
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MembershipDetailResponse(MembershipResponse):
    """Membership with teams."""
    teams: list[TeamResponse] = []
    invited_by: Optional[UserMiniResponse] = None
    invited_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None


# =============================================================================
# Invitation Schemas
# =============================================================================

class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = "member"
    team_ids: list[UUID] = []
    message: str = ""


class InvitationResponse(BaseModel):
    id: UUID
    email: EmailStr
    organization: OrganizationMiniResponse
    role: str
    status: str
    invited_by: Optional[UserMiniResponse] = None
    message: str = ""
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class InvitationAccept(BaseModel):
    token: str


# =============================================================================
# Authentication Schemas
# =============================================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = ""
    last_name: str = ""


class RegisterResponse(BaseModel):
    user: UserResponse
    message: str = "Registration successful. Please verify your email."


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerifyRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


# =============================================================================
# OAuth Schemas
# =============================================================================

class OAuthAuthorizationRequest(BaseModel):
    redirect_uri: Optional[str] = None
    state: Optional[str] = None


class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


class OAuthConnectResponse(BaseModel):
    provider: str
    connected: bool
    email: Optional[str] = None


# =============================================================================
# Audit Log Schemas
# =============================================================================

class AuditLogResponse(BaseModel):
    id: UUID
    user: Optional[UserMiniResponse] = None
    action: str
    resource_type: str = ""
    resource_id: str = ""
    data: dict = {}
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogFilter(BaseModel):
    user_id: Optional[UUID] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None

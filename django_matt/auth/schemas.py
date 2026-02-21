"""
Authentication Pydantic schemas for Django Matt.

All auth request/response validation uses Pydantic v2 schemas,
not DRF serializers.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

# ============================================================================
# Token Schemas
# ============================================================================


class TokenPayload(BaseModel):
    """JWT token payload schema."""

    sub: str = Field(..., description="Subject (user ID)")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(..., description="Issued at time")
    type: str = Field("access", description="Token type (access or refresh)")
    jti: str | None = Field(None, description="JWT ID (for blacklisting)")

    # Optional claims
    email: str | None = None
    username: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    org_id: str | None = Field(None, description="Organization ID for multi-tenant")

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    """Access and refresh token pair response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("Bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    refresh_expires_in: int = Field(..., description="Refresh token expiration in seconds")


class AccessToken(BaseModel):
    """Single access token response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


# ============================================================================
# Login/Registration Schemas
# ============================================================================


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginWithUsernameRequest(BaseModel):
    """Login with username request schema."""

    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="User password")


class RegisterRequest(BaseModel):
    """User registration request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    password_confirm: str = Field(..., description="Password confirmation")
    username: str | None = Field(None, min_length=3, max_length=50, description="Optional username")
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str = Field(..., description="JWT refresh token")


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    new_password_confirm: str = Field(..., description="New password confirmation")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class ResetPasswordRequest(BaseModel):
    """Request password reset schema."""

    email: EmailStr = Field(..., description="User email address")

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class ResetPasswordConfirmRequest(BaseModel):
    """Confirm password reset schema."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    new_password_confirm: str = Field(..., description="New password confirmation")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


# ============================================================================
# User Schemas
# ============================================================================


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class UserCreate(UserBase):
    """Schema for creating a user (internal use)."""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    model_config = {"from_attributes": True}


class UserResponse(UserBase):
    """User response schema (excludes sensitive data)."""

    id: Any = Field(..., description="User ID")
    date_joined: datetime | None = None
    last_login: datetime | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        """Create from Django User model (sync)."""
        roles = []
        permissions = []

        # Get groups as roles
        if hasattr(user, "groups"):
            roles = list(user.groups.values_list("name", flat=True))

        # Get permissions
        if hasattr(user, "get_all_permissions"):
            permissions = list(user.get_all_permissions())

        return cls(
            id=user.pk,
            email=user.email,
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
            is_active=user.is_active,
            date_joined=getattr(user, "date_joined", None),
            last_login=getattr(user, "last_login", None),
            roles=roles,
            permissions=permissions,
        )

    @classmethod
    async def afrom_user(cls, user) -> "UserResponse":
        """Create from Django User model (async-safe)."""
        roles = []
        permissions = []

        # Get groups as roles (async)
        if hasattr(user, "groups"):
            roles = [name async for name in user.groups.values_list("name", flat=True)]

        # Get permissions (sync_to_async since no async API)
        if hasattr(user, "get_all_permissions"):
            from asgiref.sync import sync_to_async

            permissions = list(await sync_to_async(user.get_all_permissions)())

        return cls(
            id=user.pk,
            email=user.email,
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
            is_active=user.is_active,
            date_joined=getattr(user, "date_joined", None),
            last_login=getattr(user, "last_login", None),
            roles=roles,
            permissions=permissions,
        )


class AuthResponse(BaseModel):
    """Full authentication response with user and tokens."""

    user: UserResponse
    tokens: TokenPair


# ============================================================================
# Magic Link / Passwordless Schemas
# ============================================================================


class MagicLinkRequest(BaseModel):
    """Request magic link schema."""

    email: EmailStr = Field(..., description="User email address")

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class MagicLinkVerifyRequest(BaseModel):
    """Verify magic link token schema."""

    token: str = Field(..., description="Magic link token")


class OTPRequest(BaseModel):
    """Request OTP schema."""

    email: EmailStr | None = None
    phone: str | None = None

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str | None) -> str | None:
        if v:
            return v.lower().strip()
        return v


class OTPVerifyRequest(BaseModel):
    """Verify OTP schema."""

    email: EmailStr | None = None
    phone: str | None = None
    code: str = Field(..., min_length=4, max_length=8, description="OTP code")


# ============================================================================
# API Key Schemas
# ============================================================================


class APIKeyCreate(BaseModel):
    """Create API key request schema."""

    name: str = Field(..., min_length=1, max_length=100, description="Key name/description")
    expires_at: datetime | None = Field(None, description="Optional expiration date")
    permissions: list[str] = Field(default_factory=list, description="Scoped permissions")


class APIKeyResponse(BaseModel):
    """API key response (key only shown on creation)."""

    id: str
    name: str
    prefix: str = Field(..., description="Key prefix for identification")
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool = True


class APIKeyCreatedResponse(APIKeyResponse):
    """Response when API key is created (includes full key)."""

    key: str = Field(..., description="Full API key (only shown once)")


# ============================================================================
# Message Schemas
# ============================================================================


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str
    code: str = "error"
    errors: list[dict[str, Any]] | None = None

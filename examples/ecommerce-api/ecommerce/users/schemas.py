"""Pydantic schemas for users app."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# =============================================================================
# User Schemas
# =============================================================================


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    first_name: str = ""
    last_name: str = ""
    phone: str = ""


class UserCreate(UserBase):
    """User creation schema."""

    password: Annotated[str, Field(min_length=8)]


class UserUpdate(BaseModel):
    """User update schema."""

    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    accepts_marketing: bool | None = None


class UserResponse(UserBase):
    """User response schema."""

    id: UUID
    full_name: str
    is_active: bool
    accepts_marketing: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(UserResponse):
    """User profile with additional details."""

    date_of_birth: date | None = None
    avatar: str | None = None


# =============================================================================
# Auth Schemas
# =============================================================================


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    token_type: str = "Bearer"


class PasswordChangeRequest(BaseModel):
    """Password change request schema."""

    current_password: str
    new_password: Annotated[str, Field(min_length=8)]


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""

    token: str
    new_password: Annotated[str, Field(min_length=8)]


# =============================================================================
# Address Schemas
# =============================================================================


class AddressBase(BaseModel):
    """Base address schema."""

    address_type: str = "both"
    is_default: bool = False
    first_name: str
    last_name: str
    company: str = ""
    address_line_1: str
    address_line_2: str = ""
    city: str
    state: str
    postal_code: str
    country: str = "US"
    phone: str = ""


class AddressCreate(AddressBase):
    """Address creation schema."""

    pass


class AddressUpdate(BaseModel):
    """Address update schema."""

    address_type: str | None = None
    is_default: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone: str | None = None


class AddressResponse(AddressBase):
    """Address response schema."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Wishlist Schemas
# =============================================================================


class WishlistItemCreate(BaseModel):
    """Wishlist item creation schema."""

    product_id: UUID
    notes: str = ""
    priority: int = 0


class WishlistItemResponse(BaseModel):
    """Wishlist item response schema."""

    id: UUID
    product_id: UUID
    product_name: str
    product_price: float
    product_image: str | None = None
    notes: str
    priority: int
    added_at: datetime

    class Config:
        from_attributes = True


class WishlistCreate(BaseModel):
    """Wishlist creation schema."""

    name: str = "My Wishlist"
    is_public: bool = False


class WishlistUpdate(BaseModel):
    """Wishlist update schema."""

    name: str | None = None
    is_public: bool | None = None


class WishlistResponse(BaseModel):
    """Wishlist response schema."""

    id: UUID
    name: str
    is_public: bool
    item_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WishlistDetailResponse(WishlistResponse):
    """Wishlist detail with items."""

    items: list[WishlistItemResponse] = []

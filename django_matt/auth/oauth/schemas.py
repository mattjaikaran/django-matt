"""
Pydantic schemas for OAuth flows.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class OAuthProviderInfo(BaseModel):
    """Information about an OAuth provider."""

    name: str = Field(description="Provider name (e.g., 'google')")
    display_name: str = Field(description="Human-readable name (e.g., 'Google')")
    enabled: bool = Field(description="Whether this provider is enabled")
    authorization_url: str | None = Field(
        default=None,
        description="URL to start OAuth flow (only if enabled)",
    )


class OAuthProvidersResponse(BaseModel):
    """List of available OAuth providers."""

    providers: list[OAuthProviderInfo]


class OAuthLoginRequest(BaseModel):
    """Request to start OAuth login flow."""

    redirect_url: str | None = Field(
        default=None,
        description="Optional URL to redirect to after successful login",
    )


class OAuthLoginResponse(BaseModel):
    """Response with authorization URL to redirect user to."""

    authorization_url: str = Field(description="URL to redirect user to")
    state: str = Field(description="State parameter for CSRF protection")
    provider: str = Field(description="Provider name")


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request (from provider redirect)."""

    code: str = Field(description="Authorization code from provider")
    state: str = Field(description="State parameter for verification")
    error: str | None = Field(default=None, description="Error code if auth failed")
    error_description: str | None = Field(
        default=None,
        description="Error description if auth failed",
    )
    # Apple-specific: user data on first login
    user: str | None = Field(
        default=None,
        description="User data (Apple only, first login)",
    )


class OAuthCallbackResponse(BaseModel):
    """Response after successful OAuth callback."""

    success: bool = True
    user_id: int | str = Field(description="User ID")
    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    created: bool = Field(
        default=False,
        description="Whether a new user was created",
    )
    provider: str = Field(description="Provider that authenticated the user")


class OAuthUserInfoResponse(BaseModel):
    """User info from OAuth provider."""

    provider: str
    provider_user_id: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None


class OAuthConnectionResponse(BaseModel):
    """Information about a user's OAuth connection."""

    id: int
    provider: str
    provider_user_id: str
    email: str | None = None
    connected_at: datetime


class OAuthConnectionListResponse(BaseModel):
    """List of user's OAuth connections."""

    connections: list[OAuthConnectionResponse]
    count: int


class OAuthDisconnectRequest(BaseModel):
    """Request to disconnect an OAuth provider."""

    provider: str = Field(description="Provider to disconnect")


class OAuthErrorResponse(BaseModel):
    """OAuth error response."""

    error: str = Field(description="Error code")
    error_description: str | None = Field(
        default=None,
        description="Human-readable error description",
    )
    provider: str | None = Field(default=None, description="Provider if applicable")

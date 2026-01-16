"""
Pydantic schemas for Enterprise SSO flows.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# SSO Connection Configuration
# =============================================================================


class SSOConnectionBase(BaseModel):
    """Base schema for SSO connection."""

    provider_type: Literal["saml", "oidc", "okta", "azure_ad", "google_workspace", "onelogin", "auth0"]
    name: str = Field(default="", max_length=255)
    is_active: bool = True
    is_required: bool = False
    domains: list[str] = Field(default_factory=list)
    default_role: str = "member"


class SSOConnectionSAMLConfig(BaseModel):
    """SAML-specific configuration."""

    idp_entity_id: str = Field(description="Identity Provider Entity ID")
    idp_sso_url: str = Field(description="IdP Single Sign-On URL")
    idp_slo_url: str | None = Field(default=None, description="IdP Single Logout URL")
    idp_certificate: str = Field(description="IdP X.509 certificate (PEM)")


class SSOConnectionOIDCConfig(BaseModel):
    """OIDC-specific configuration."""

    client_id: str = Field(description="OIDC Client ID")
    client_secret: str = Field(description="OIDC Client Secret")
    discovery_url: str | None = Field(
        default=None,
        description="OIDC Discovery URL (.well-known/openid-configuration)",
    )
    authorization_url: str | None = Field(
        default=None,
        description="Authorization URL (if not using discovery)",
    )
    token_url: str | None = Field(
        default=None,
        description="Token URL (if not using discovery)",
    )
    userinfo_url: str | None = Field(
        default=None,
        description="UserInfo URL (if not using discovery)",
    )


class SSOConnectionCreateRequest(SSOConnectionBase):
    """Request to create a new SSO connection."""

    # SAML config (required if provider_type is saml)
    saml_config: SSOConnectionSAMLConfig | None = None

    # OIDC config (required if provider_type is oidc/okta/azure_ad/google_workspace/auth0)
    oidc_config: SSOConnectionOIDCConfig | None = None

    # Attribute mapping
    attribute_mapping: dict[str, str] = Field(default_factory=dict)

    # Extra provider-specific config
    extra_config: dict = Field(default_factory=dict)


class SSOConnectionUpdateRequest(BaseModel):
    """Request to update an SSO connection."""

    name: str | None = None
    is_active: bool | None = None
    is_required: bool | None = None
    domains: list[str] | None = None
    default_role: str | None = None
    saml_config: SSOConnectionSAMLConfig | None = None
    oidc_config: SSOConnectionOIDCConfig | None = None
    attribute_mapping: dict[str, str] | None = None
    extra_config: dict | None = None


class SSOConnectionResponse(SSOConnectionBase):
    """SSO connection response."""

    id: int
    organization_id: str
    created_at: datetime
    updated_at: datetime

    # Don't expose secrets
    has_saml_config: bool = False
    has_oidc_config: bool = False

    @classmethod
    def from_model(cls, connection) -> "SSOConnectionResponse":
        return cls(
            id=connection.id,
            organization_id=connection.organization_id,
            provider_type=connection.provider_type,
            name=connection.name,
            is_active=connection.is_active,
            is_required=connection.is_required,
            domains=connection.domains,
            default_role=connection.default_role,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
            has_saml_config=bool(connection.idp_entity_id),
            has_oidc_config=bool(connection.client_id),
        )


# =============================================================================
# SSO Login Flow
# =============================================================================


class SSOLoginRequest(BaseModel):
    """Request to start SSO login flow."""

    email: str | None = Field(
        default=None,
        description="Email to determine which SSO to use (if multiple orgs)",
    )
    organization_id: str | None = Field(
        default=None,
        description="Organization ID to login to",
    )
    redirect_url: str | None = Field(
        default=None,
        description="URL to redirect to after successful login",
    )


class SSOLoginResponse(BaseModel):
    """Response with SSO login URL."""

    login_url: str = Field(description="URL to redirect user to for SSO")
    organization_id: str = Field(description="Organization ID")
    provider_type: str = Field(description="SSO provider type")


class SSOCallbackResponse(BaseModel):
    """Response after successful SSO callback."""

    success: bool = True
    user_id: int | str = Field(description="User ID")
    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    organization_id: str = Field(description="Organization ID")
    created: bool = Field(default=False, description="Whether user was created")


# =============================================================================
# SP Metadata
# =============================================================================


class SPMetadataResponse(BaseModel):
    """Service Provider metadata response."""

    entity_id: str = Field(description="SP Entity ID")
    acs_url: str = Field(description="Assertion Consumer Service URL")
    metadata_xml: str | None = Field(
        default=None,
        description="Full SAML SP metadata XML (SAML only)",
    )


# =============================================================================
# SSO Status
# =============================================================================


class SSOStatusResponse(BaseModel):
    """SSO status for an organization or email domain."""

    sso_enabled: bool = Field(description="Whether SSO is enabled")
    sso_required: bool = Field(
        default=False,
        description="Whether SSO is required (password disabled)",
    )
    organization_id: str | None = Field(
        default=None,
        description="Organization ID if SSO is enabled",
    )
    provider_type: str | None = Field(
        default=None,
        description="SSO provider type if enabled",
    )
    login_url: str | None = Field(
        default=None,
        description="Direct SSO login URL",
    )


class SSODomainCheckRequest(BaseModel):
    """Request to check if email domain uses SSO."""

    email: str = Field(description="Email address to check")


# =============================================================================
# Error Response
# =============================================================================


class SSOErrorResponse(BaseModel):
    """SSO error response."""

    error: str = Field(description="Error code")
    error_description: str | None = Field(
        default=None,
        description="Human-readable error description",
    )
    organization_id: str | None = Field(
        default=None,
        description="Organization ID if applicable",
    )

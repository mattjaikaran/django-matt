"""
Pydantic schemas for WebAuthn/Passkey flows.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Registration Schemas
# =============================================================================


class RegistrationOptionsRequest(BaseModel):
    """Request to generate registration options."""

    # Optional credential name (e.g., "MacBook Pro", "iPhone")
    credential_name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional name for this credential",
    )


class PublicKeyCredentialUserEntity(BaseModel):
    """User entity for WebAuthn."""

    id: str = Field(description="User ID (base64url encoded)")
    name: str = Field(description="Username or email")
    displayName: str = Field(description="Display name")


class PublicKeyCredentialRpEntity(BaseModel):
    """Relying Party entity for WebAuthn."""

    id: str = Field(description="RP ID (domain)")
    name: str = Field(description="RP name")


class PublicKeyCredentialParameters(BaseModel):
    """Algorithm parameters for credential creation."""

    type: Literal["public-key"] = "public-key"
    alg: int = Field(description="COSE algorithm identifier")


class AuthenticatorSelectionCriteria(BaseModel):
    """Criteria for authenticator selection."""

    authenticatorAttachment: str | None = None
    residentKey: str = "preferred"
    userVerification: str = "preferred"
    requireResidentKey: bool = False


class PublicKeyCredentialDescriptor(BaseModel):
    """Descriptor for an existing credential."""

    type: Literal["public-key"] = "public-key"
    id: str = Field(description="Credential ID (base64url encoded)")
    transports: list[str] | None = None


class RegistrationOptionsResponse(BaseModel):
    """WebAuthn registration options sent to client."""

    challenge: str = Field(description="Challenge (base64url encoded)")
    rp: PublicKeyCredentialRpEntity
    user: PublicKeyCredentialUserEntity
    pubKeyCredParams: list[PublicKeyCredentialParameters]
    timeout: int = Field(description="Timeout in milliseconds")
    excludeCredentials: list[PublicKeyCredentialDescriptor] = Field(default_factory=list)
    authenticatorSelection: AuthenticatorSelectionCriteria
    attestation: str = "none"

    # For storing on server to verify response
    challenge_id: str = Field(description="Server-side challenge identifier")


class AuthenticatorAttestationResponse(BaseModel):
    """Authenticator response for registration."""

    clientDataJSON: str = Field(description="Client data (base64url encoded)")
    attestationObject: str = Field(description="Attestation object (base64url encoded)")
    transports: list[str] | None = None


class RegistrationVerifyRequest(BaseModel):
    """Request to verify registration response from client."""

    challenge_id: str = Field(description="Challenge ID from options")
    credential_id: str = Field(alias="id", description="Credential ID (base64url encoded)")
    raw_id: str = Field(alias="rawId", description="Raw credential ID (base64url encoded)")
    type: Literal["public-key"] = "public-key"
    response: AuthenticatorAttestationResponse
    credential_name: str | None = Field(
        default=None,
        max_length=255,
        description="Name for this credential",
    )

    model_config = {"populate_by_name": True}


class RegistrationVerifyResponse(BaseModel):
    """Response after successful registration verification."""

    success: bool = True
    credential_id: str = Field(description="Stored credential ID")
    message: str = "Passkey registered successfully"


# =============================================================================
# Authentication Schemas
# =============================================================================


class AuthenticationOptionsRequest(BaseModel):
    """Request to generate authentication options."""

    # Email/username for non-discoverable credential flow
    email: str | None = Field(
        default=None,
        description="Email for user identification (optional for discoverable credentials)",
    )


class AuthenticationOptionsResponse(BaseModel):
    """WebAuthn authentication options sent to client."""

    challenge: str = Field(description="Challenge (base64url encoded)")
    timeout: int = Field(description="Timeout in milliseconds")
    rpId: str = Field(description="RP ID (domain)")
    allowCredentials: list[PublicKeyCredentialDescriptor] = Field(default_factory=list)
    userVerification: str = "preferred"

    # For storing on server to verify response
    challenge_id: str = Field(description="Server-side challenge identifier")


class AuthenticatorAssertionResponse(BaseModel):
    """Authenticator response for authentication."""

    clientDataJSON: str = Field(description="Client data (base64url encoded)")
    authenticatorData: str = Field(description="Authenticator data (base64url encoded)")
    signature: str = Field(description="Signature (base64url encoded)")
    userHandle: str | None = Field(
        default=None,
        description="User handle (base64url encoded, for discoverable credentials)",
    )


class AuthenticationVerifyRequest(BaseModel):
    """Request to verify authentication response from client."""

    challenge_id: str = Field(description="Challenge ID from options")
    credential_id: str = Field(alias="id", description="Credential ID (base64url encoded)")
    raw_id: str = Field(alias="rawId", description="Raw credential ID (base64url encoded)")
    type: Literal["public-key"] = "public-key"
    response: AuthenticatorAssertionResponse

    model_config = {"populate_by_name": True}


class AuthenticationVerifyResponse(BaseModel):
    """Response after successful authentication verification."""

    success: bool = True
    user_id: int | str = Field(description="Authenticated user ID")
    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    message: str = "Authentication successful"


# =============================================================================
# Credential Management Schemas
# =============================================================================


class PasskeyCredentialResponse(BaseModel):
    """Single passkey credential response."""

    id: int
    credential_id: str = Field(description="Credential ID (truncated for display)")
    name: str
    device_type: str
    backed_up: bool
    transports: list[str]
    created_at: datetime
    last_used_at: datetime | None

    @classmethod
    def from_model(cls, credential) -> "PasskeyCredentialResponse":
        """Create from a PasskeyCredential model instance."""
        return cls(
            id=credential.id,
            credential_id=credential.credential_id[:16] + "...",
            name=credential.name or f"Credential {credential.id}",
            device_type=credential.device_type,
            backed_up=credential.backed_up,
            transports=credential.transports or [],
            created_at=credential.created_at,
            last_used_at=credential.last_used_at,
        )


class PasskeyCredentialListResponse(BaseModel):
    """List of passkey credentials."""

    credentials: list[PasskeyCredentialResponse]
    count: int


class PasskeyCredentialDeleteRequest(BaseModel):
    """Request to delete a credential."""

    credential_id: int = Field(description="Database ID of credential to delete")


class PasskeyCredentialUpdateRequest(BaseModel):
    """Request to update a credential."""

    name: str = Field(max_length=255, description="New name for credential")

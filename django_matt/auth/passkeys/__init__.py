"""
Django Matt Passkeys/WebAuthn - Passwordless authentication with passkeys.

Provides:
- WebAuthn registration and authentication
- Passkey credential storage and management
- Device-bound and synced passkey support
- Pydantic schemas for WebAuthn flows
- Ready-to-use API controllers

Requires: uv add webauthn

Example:
    from django_matt.auth.passkeys import (
        PasskeyController,
        generate_registration_options,
        verify_registration_response,
    )

    # Add to your API
    api.register_controller(PasskeyController)

    # Or use functions directly
    options = generate_registration_options(user)
    # ... send to client, get response back ...
    credential = verify_registration_response(user, response)
"""

from django_matt.auth.passkeys.config import (
    PasskeyConfig,
    passkey_config,
)
from django_matt.auth.passkeys.controllers import (
    MinimalPasskeyController,
    PasskeyController,
)
from django_matt.auth.passkeys.schemas import (
    # Authentication
    AuthenticationOptionsRequest,
    AuthenticationOptionsResponse,
    AuthenticationVerifyRequest,
    AuthenticationVerifyResponse,
    PasskeyCredentialDeleteRequest,
    PasskeyCredentialListResponse,
    # Credential management
    PasskeyCredentialResponse,
    # Registration
    RegistrationOptionsRequest,
    RegistrationOptionsResponse,
    RegistrationVerifyRequest,
    RegistrationVerifyResponse,
)
from django_matt.auth.passkeys.webauthn import (
    PasskeyAuthenticationError,
    PasskeyCredentialNotFoundError,
    PasskeyError,
    PasskeyRegistrationError,
    agenerate_authentication_options,
    agenerate_registration_options,
    averify_authentication_response,
    averify_registration_response,
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)

__all__ = [
    # Config
    "PasskeyConfig",
    "passkey_config",
    # Core functions (sync)
    "generate_registration_options",
    "verify_registration_response",
    "generate_authentication_options",
    "verify_authentication_response",
    # Core functions (async)
    "agenerate_registration_options",
    "averify_registration_response",
    "agenerate_authentication_options",
    "averify_authentication_response",
    # Errors
    "PasskeyError",
    "PasskeyRegistrationError",
    "PasskeyAuthenticationError",
    "PasskeyCredentialNotFoundError",
    # Schemas - Registration
    "RegistrationOptionsRequest",
    "RegistrationOptionsResponse",
    "RegistrationVerifyRequest",
    "RegistrationVerifyResponse",
    # Schemas - Authentication
    "AuthenticationOptionsRequest",
    "AuthenticationOptionsResponse",
    "AuthenticationVerifyRequest",
    "AuthenticationVerifyResponse",
    # Schemas - Credentials
    "PasskeyCredentialResponse",
    "PasskeyCredentialListResponse",
    "PasskeyCredentialDeleteRequest",
    # Controllers
    "PasskeyController",
    "MinimalPasskeyController",
]

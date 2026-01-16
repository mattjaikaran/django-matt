"""
Django Matt Passkeys/WebAuthn - Passwordless authentication with passkeys.

Provides:
- WebAuthn registration and authentication
- Passkey credential storage and management
- Device-bound and synced passkey support
- Pydantic schemas for WebAuthn flows
- Ready-to-use API controllers

Requires: pip install webauthn

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
from django_matt.auth.passkeys.webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    PasskeyError,
    PasskeyRegistrationError,
    PasskeyAuthenticationError,
    PasskeyCredentialNotFoundError,
)
from django_matt.auth.passkeys.schemas import (
    # Registration
    RegistrationOptionsRequest,
    RegistrationOptionsResponse,
    RegistrationVerifyRequest,
    RegistrationVerifyResponse,
    # Authentication
    AuthenticationOptionsRequest,
    AuthenticationOptionsResponse,
    AuthenticationVerifyRequest,
    AuthenticationVerifyResponse,
    # Credential management
    PasskeyCredentialResponse,
    PasskeyCredentialListResponse,
    PasskeyCredentialDeleteRequest,
)
from django_matt.auth.passkeys.controllers import (
    PasskeyController,
    MinimalPasskeyController,
)

__all__ = [
    # Config
    "PasskeyConfig",
    "passkey_config",
    # Core functions
    "generate_registration_options",
    "verify_registration_response",
    "generate_authentication_options",
    "verify_authentication_response",
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

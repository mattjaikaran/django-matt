"""
API Controllers for WebAuthn/Passkey authentication.

Provides ready-to-use endpoints for:
- Passkey registration (with existing auth)
- Passkey authentication (passwordless login)
- Credential management (list, delete, rename)
"""

from django.http import JsonResponse

from django_matt.auth.jwt import create_token_pair
from django_matt.auth.decorators import jwt_required
from django_matt.auth.passkeys.schemas import (
    RegistrationOptionsRequest,
    RegistrationOptionsResponse,
    RegistrationVerifyRequest,
    RegistrationVerifyResponse,
    AuthenticationOptionsRequest,
    AuthenticationOptionsResponse,
    AuthenticationVerifyRequest,
    AuthenticationVerifyResponse,
    PasskeyCredentialResponse,
    PasskeyCredentialListResponse,
    PasskeyCredentialDeleteRequest,
    PasskeyCredentialUpdateRequest,
)
from django_matt.auth.passkeys.webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    PasskeyError,
)
from django_matt.core.errors import (
    APIError,
    NotFoundAPIError,
    ValidationAPIError,
    PermissionAPIError,
)


class PasskeyController:
    """
    Full-featured passkey controller with all endpoints.

    Endpoints:
        POST /passkeys/register/options - Get registration options (requires auth)
        POST /passkeys/register/verify - Verify registration (requires auth)
        POST /passkeys/authenticate/options - Get authentication options
        POST /passkeys/authenticate/verify - Verify authentication
        GET /passkeys/credentials - List user's credentials (requires auth)
        DELETE /passkeys/credentials/{id} - Delete a credential (requires auth)
        PATCH /passkeys/credentials/{id} - Update credential name (requires auth)

    Usage:
        from django_matt import MattAPI
        from django_matt.auth.passkeys import PasskeyController

        api = MattAPI()
        api.register_controller(PasskeyController, prefix="/auth")
    """

    prefix = "passkeys"
    tags = ["Passkeys"]

    # =========================================================================
    # Registration Endpoints
    # =========================================================================

    @staticmethod
    @jwt_required
    async def register_options(request, data: RegistrationOptionsRequest) -> dict:
        """
        Generate registration options for adding a new passkey.

        Requires authentication - user must be logged in to add a passkey.

        POST /passkeys/register/options
        """
        try:
            options = generate_registration_options(
                user=request.user,
                credential_name=data.credential_name,
            )
            return options
        except PasskeyError as e:
            raise ValidationAPIError(str(e))

    @staticmethod
    @jwt_required
    async def register_verify(request, data: RegistrationVerifyRequest) -> RegistrationVerifyResponse:
        """
        Verify registration response and store the credential.

        POST /passkeys/register/verify
        """
        try:
            credential = verify_registration_response(
                user=request.user,
                credential_id=data.credential_id,
                client_data_json=data.response.clientDataJSON,
                attestation_object=data.response.attestationObject,
                challenge_id=data.challenge_id,
                transports=data.response.transports,
                credential_name=data.credential_name,
            )
            return RegistrationVerifyResponse(
                success=True,
                credential_id=credential.credential_id,
                message="Passkey registered successfully",
            )
        except PasskeyError as e:
            raise ValidationAPIError(str(e))

    # =========================================================================
    # Authentication Endpoints
    # =========================================================================

    @staticmethod
    async def authenticate_options(request, data: AuthenticationOptionsRequest) -> dict:
        """
        Generate authentication options for passkey login.

        Can be called without authentication for passwordless login flow.

        POST /passkeys/authenticate/options
        """
        try:
            options = generate_authentication_options(
                email=data.email,
            )
            return options
        except PasskeyError as e:
            raise ValidationAPIError(str(e))

    @staticmethod
    async def authenticate_verify(request, data: AuthenticationVerifyRequest) -> AuthenticationVerifyResponse:
        """
        Verify authentication response and return tokens.

        POST /passkeys/authenticate/verify
        """
        try:
            user, credential = verify_authentication_response(
                credential_id=data.credential_id,
                client_data_json=data.response.clientDataJSON,
                authenticator_data=data.response.authenticatorData,
                signature=data.response.signature,
                challenge_id=data.challenge_id,
                user_handle=data.response.userHandle,
            )

            # Generate JWT tokens
            tokens = create_token_pair(user)

            return AuthenticationVerifyResponse(
                success=True,
                user_id=user.pk,
                access_token=tokens["access"],
                refresh_token=tokens["refresh"],
                message="Authentication successful",
            )
        except PasskeyError as e:
            raise ValidationAPIError(str(e))

    # =========================================================================
    # Credential Management Endpoints
    # =========================================================================

    @staticmethod
    @jwt_required
    async def list_credentials(request) -> PasskeyCredentialListResponse:
        """
        List all passkey credentials for the current user.

        GET /passkeys/credentials
        """
        from django_matt.auth.passkeys.models import PasskeyCredential

        credentials = PasskeyCredential.objects.filter(user=request.user).order_by("-created_at")

        return PasskeyCredentialListResponse(
            credentials=[
                PasskeyCredentialResponse.from_model(cred) for cred in credentials
            ],
            count=credentials.count(),
        )

    @staticmethod
    @jwt_required
    async def delete_credential(request, credential_id: int) -> dict:
        """
        Delete a passkey credential.

        DELETE /passkeys/credentials/{credential_id}
        """
        from django_matt.auth.passkeys.models import PasskeyCredential

        try:
            credential = PasskeyCredential.objects.get(
                id=credential_id,
                user=request.user,
            )
        except PasskeyCredential.DoesNotExist:
            raise NotFoundAPIError("Credential not found")

        # Prevent deleting last credential if user has no password
        remaining = PasskeyCredential.objects.filter(user=request.user).exclude(id=credential_id).count()
        if remaining == 0 and not request.user.has_usable_password():
            raise ValidationAPIError(
                "Cannot delete last passkey when user has no password set"
            )

        credential.delete()

        return {"success": True, "message": "Credential deleted"}

    @staticmethod
    @jwt_required
    async def update_credential(request, credential_id: int, data: PasskeyCredentialUpdateRequest) -> PasskeyCredentialResponse:
        """
        Update a passkey credential (rename).

        PATCH /passkeys/credentials/{credential_id}
        """
        from django_matt.auth.passkeys.models import PasskeyCredential

        try:
            credential = PasskeyCredential.objects.get(
                id=credential_id,
                user=request.user,
            )
        except PasskeyCredential.DoesNotExist:
            raise NotFoundAPIError("Credential not found")

        credential.name = data.name
        credential.save(update_fields=["name"])

        return PasskeyCredentialResponse.from_model(credential)

    @classmethod
    def get_urls(cls):
        """
        Get URL patterns for this controller.

        Returns list of (path, method, handler, name) tuples.
        """
        return [
            ("register/options", "POST", cls.register_options, "passkey-register-options"),
            ("register/verify", "POST", cls.register_verify, "passkey-register-verify"),
            ("authenticate/options", "POST", cls.authenticate_options, "passkey-auth-options"),
            ("authenticate/verify", "POST", cls.authenticate_verify, "passkey-auth-verify"),
            ("credentials", "GET", cls.list_credentials, "passkey-list-credentials"),
            ("credentials/<int:credential_id>", "DELETE", cls.delete_credential, "passkey-delete-credential"),
            ("credentials/<int:credential_id>", "PATCH", cls.update_credential, "passkey-update-credential"),
        ]


class MinimalPasskeyController:
    """
    Minimal passkey controller with just auth endpoints.

    Use this if you want only authentication and handle registration elsewhere.

    Endpoints:
        POST /passkeys/options - Get authentication options
        POST /passkeys/verify - Verify authentication
    """

    prefix = "passkeys"
    tags = ["Passkeys"]

    @staticmethod
    async def options(request, data: AuthenticationOptionsRequest) -> dict:
        """
        Generate authentication options.

        POST /passkeys/options
        """
        try:
            return generate_authentication_options(email=data.email)
        except PasskeyError as e:
            raise ValidationAPIError(str(e))

    @staticmethod
    async def verify(request, data: AuthenticationVerifyRequest) -> AuthenticationVerifyResponse:
        """
        Verify authentication and return tokens.

        POST /passkeys/verify
        """
        try:
            user, credential = verify_authentication_response(
                credential_id=data.credential_id,
                client_data_json=data.response.clientDataJSON,
                authenticator_data=data.response.authenticatorData,
                signature=data.response.signature,
                challenge_id=data.challenge_id,
                user_handle=data.response.userHandle,
            )

            tokens = create_token_pair(user)

            return AuthenticationVerifyResponse(
                success=True,
                user_id=user.pk,
                access_token=tokens["access"],
                refresh_token=tokens["refresh"],
                message="Authentication successful",
            )
        except PasskeyError as e:
            raise ValidationAPIError(str(e))

    @classmethod
    def get_urls(cls):
        """Get URL patterns for this controller."""
        return [
            ("options", "POST", cls.options, "passkey-options"),
            ("verify", "POST", cls.verify, "passkey-verify"),
        ]

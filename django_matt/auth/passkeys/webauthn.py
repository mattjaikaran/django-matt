# file-length-max: 900
"""
Core WebAuthn/Passkey logic for registration and authentication.

This module provides the core functions for:
- Generating registration options
- Verifying registration responses
- Generating authentication options
- Verifying authentication responses
"""

import secrets
from typing import Any

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from asgiref.sync import sync_to_async

from django_matt.auth.passkeys.config import get_passkey_config

# Try to import webauthn library
try:
    from webauthn import (
        generate_authentication_options as _generate_authentication_options,
    )
    from webauthn import (
        generate_registration_options as _generate_registration_options,
    )
    from webauthn import (
        options_to_json,
    )
    from webauthn import (
        verify_authentication_response as _verify_authentication_response,
    )
    from webauthn import (
        verify_registration_response as _verify_registration_response,
    )
    from webauthn.helpers import (
        base64url_to_bytes,
        bytes_to_base64url,
    )
    from webauthn.helpers.structs import (
        AttestationConveyancePreference,
        AuthenticatorAttachment,
        AuthenticatorSelectionCriteria,
        AuthenticatorTransport,
        PublicKeyCredentialDescriptor,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    HAS_WEBAUTHN = True
except ImportError:
    HAS_WEBAUTHN = False


# =============================================================================
# Exceptions
# =============================================================================


class PasskeyError(Exception):
    """Base exception for passkey errors."""


class PasskeyRegistrationError(PasskeyError):
    """Error during passkey registration."""


class PasskeyAuthenticationError(PasskeyError):
    """Error during passkey authentication."""


class PasskeyCredentialNotFoundError(PasskeyError):
    """Credential not found."""


class PasskeyNotInstalledError(PasskeyError):
    """WebAuthn library not installed."""

    def __init__(self):
        super().__init__("webauthn library is not installed. Install it with: uv add webauthn")


# =============================================================================
# Helper Functions
# =============================================================================


def _ensure_webauthn():
    """Ensure webauthn library is installed."""
    if not HAS_WEBAUTHN:
        raise PasskeyNotInstalledError()


def _generate_challenge() -> bytes:
    """Generate a random challenge."""
    return secrets.token_bytes(32)


def _get_challenge_cache_key(challenge_id: str) -> str:
    """Get cache key for a challenge."""
    config = get_passkey_config()
    return f"{config.challenge_cache_prefix}:{challenge_id}"


def _store_challenge(
    challenge_id: str,
    challenge: bytes,
    challenge_type: str,
    user_id: int | None = None,
    extra_data: dict | None = None,
):
    """Store a challenge in cache."""
    config = get_passkey_config()
    cache_key = _get_challenge_cache_key(challenge_id)

    data = {
        "challenge": bytes_to_base64url(challenge),
        "type": challenge_type,
        "user_id": user_id,
        "created_at": timezone.now().isoformat(),
    }
    if extra_data:
        data.update(extra_data)

    cache.set(cache_key, data, config.challenge_cache_timeout)


def _get_challenge(challenge_id: str) -> dict | None:
    """Retrieve a challenge from cache."""
    cache_key = _get_challenge_cache_key(challenge_id)
    return cache.get(cache_key)


def _delete_challenge(challenge_id: str):
    """Delete a challenge from cache."""
    cache_key = _get_challenge_cache_key(challenge_id)
    cache.delete(cache_key)


def _get_user_credentials(user):
    """Get all passkey credentials for a user."""
    from django_matt.auth.passkeys.models import PasskeyCredential

    return PasskeyCredential.objects.filter(user=user)


def _user_id_to_bytes(user_id: int | str) -> bytes:
    """Convert user ID to bytes for WebAuthn."""
    return str(user_id).encode("utf-8")


def _user_id_from_bytes(user_id_bytes: bytes) -> str:
    """Convert user ID bytes back to string."""
    return user_id_bytes.decode("utf-8")


# =============================================================================
# Registration Functions
# =============================================================================


def generate_registration_options(
    user,
    credential_name: str | None = None,
) -> dict[str, Any]:
    """
    Generate WebAuthn registration options for a user.

    Args:
        user: The Django user object
        credential_name: Optional name for the credential

    Returns:
        Dictionary with registration options and challenge_id
    """
    _ensure_webauthn()
    config = get_passkey_config()

    # Validate config
    errors = config.validate()
    if errors:
        raise PasskeyRegistrationError(f"Invalid passkey config: {'; '.join(errors)}")

    # Check credential limit
    existing_credentials = _get_user_credentials(user)
    if existing_credentials.count() >= config.max_credentials_per_user:
        raise PasskeyRegistrationError(
            f"Maximum number of credentials ({config.max_credentials_per_user}) reached"
        )

    # Build exclude credentials list (prevent re-registration of existing credentials)
    exclude_credentials = []
    for cred in existing_credentials:
        exclude_credentials.append(
            PublicKeyCredentialDescriptor(
                id=base64url_to_bytes(cred.credential_id),
                transports=[AuthenticatorTransport(t) for t in (cred.transports or [])],
            )
        )

    # Build authenticator selection
    authenticator_selection = AuthenticatorSelectionCriteria(
        user_verification=UserVerificationRequirement(config.user_verification),
        resident_key=ResidentKeyRequirement(config.resident_key),
    )
    if config.authenticator_attachment:
        authenticator_selection.authenticator_attachment = AuthenticatorAttachment(
            config.authenticator_attachment
        )

    # Generate options
    options = _generate_registration_options(
        rp_id=config.rp_id,
        rp_name=config.rp_name,
        user_id=_user_id_to_bytes(user.pk),
        user_name=getattr(user, "email", None) or getattr(user, "username", str(user.pk)),
        user_display_name=getattr(user, "get_full_name", lambda: str(user))(),
        exclude_credentials=exclude_credentials,
        authenticator_selection=authenticator_selection,
        attestation=AttestationConveyancePreference(config.attestation),
        challenge=_generate_challenge(),
        timeout=config.challenge_timeout,
    )

    # Generate challenge ID and store
    challenge_id = secrets.token_urlsafe(32)
    _store_challenge(
        challenge_id=challenge_id,
        challenge=options.challenge,
        challenge_type="registration",
        user_id=user.pk,
        extra_data={"credential_name": credential_name},
    )

    # Convert to JSON-serializable dict
    options_json = options_to_json(options)
    import orjson

    options_dict = orjson.loads(options_json)
    options_dict["challenge_id"] = challenge_id

    return options_dict


async def agenerate_registration_options(
    user,
    credential_name: str | None = None,
) -> dict[str, Any]:
    """
    Async version of generate_registration_options.

    Wraps sync webauthn library calls with sync_to_async and uses async ORM.
    """
    _ensure_webauthn()
    config = get_passkey_config()

    # Validate config
    errors = config.validate()
    if errors:
        raise PasskeyRegistrationError(f"Invalid passkey config: {'; '.join(errors)}")

    # Check credential limit (async ORM)
    from django_matt.auth.passkeys.models import PasskeyCredential

    existing_count = await PasskeyCredential.objects.filter(user=user).acount()
    if existing_count >= config.max_credentials_per_user:
        raise PasskeyRegistrationError(
            f"Maximum number of credentials ({config.max_credentials_per_user}) reached"
        )

    # Build exclude credentials list (async iteration)
    exclude_credentials = []
    async for cred in PasskeyCredential.objects.filter(user=user):
        exclude_credentials.append(
            PublicKeyCredentialDescriptor(
                id=base64url_to_bytes(cred.credential_id),
                transports=[AuthenticatorTransport(t) for t in (cred.transports or [])],
            )
        )

    # Build authenticator selection
    authenticator_selection = AuthenticatorSelectionCriteria(
        user_verification=UserVerificationRequirement(config.user_verification),
        resident_key=ResidentKeyRequirement(config.resident_key),
    )
    if config.authenticator_attachment:
        authenticator_selection.authenticator_attachment = AuthenticatorAttachment(
            config.authenticator_attachment
        )

    # Generate options (sync webauthn library call wrapped)
    options = await sync_to_async(_generate_registration_options)(
        rp_id=config.rp_id,
        rp_name=config.rp_name,
        user_id=_user_id_to_bytes(user.pk),
        user_name=getattr(user, "email", None) or getattr(user, "username", str(user.pk)),
        user_display_name=getattr(user, "get_full_name", lambda: str(user))(),
        exclude_credentials=exclude_credentials,
        authenticator_selection=authenticator_selection,
        attestation=AttestationConveyancePreference(config.attestation),
        challenge=_generate_challenge(),
        timeout=config.challenge_timeout,
    )

    # Generate challenge ID and store
    challenge_id = secrets.token_urlsafe(32)
    _store_challenge(
        challenge_id=challenge_id,
        challenge=options.challenge,
        challenge_type="registration",
        user_id=user.pk,
        extra_data={"credential_name": credential_name},
    )

    # Convert to JSON-serializable dict
    options_json = options_to_json(options)
    import orjson

    options_dict = orjson.loads(options_json)
    options_dict["challenge_id"] = challenge_id

    return options_dict


def verify_registration_response(
    user,
    credential_id: str,
    client_data_json: str,
    attestation_object: str,
    challenge_id: str,
    transports: list[str] | None = None,
    credential_name: str | None = None,
):
    """
    Verify a registration response and store the credential.

    Args:
        user: The Django user object
        credential_id: The credential ID from the response
        client_data_json: The clientDataJSON from the response (base64url)
        attestation_object: The attestationObject from the response (base64url)
        challenge_id: The challenge ID from registration options
        transports: Optional list of transports
        credential_name: Optional name for the credential

    Returns:
        The created PasskeyCredential model instance
    """
    _ensure_webauthn()
    config = get_passkey_config()
    from django_matt.auth.passkeys.models import PasskeyCredential

    # Retrieve stored challenge
    challenge_data = _get_challenge(challenge_id)
    if not challenge_data:
        raise PasskeyRegistrationError("Challenge not found or expired")

    if challenge_data["type"] != "registration":
        raise PasskeyRegistrationError("Invalid challenge type")

    if challenge_data["user_id"] != user.pk:
        raise PasskeyRegistrationError("Challenge does not match user")

    # Get stored credential name if not provided
    if not credential_name:
        credential_name = challenge_data.get("credential_name", "")

    try:
        # Verify the registration response
        verification = _verify_registration_response(
            credential=type(
                "Credential",
                (),
                {
                    "id": credential_id,
                    "raw_id": base64url_to_bytes(credential_id),
                    "response": type(
                        "Response",
                        (),
                        {
                            "client_data_json": base64url_to_bytes(client_data_json),
                            "attestation_object": base64url_to_bytes(attestation_object),
                        },
                    )(),
                    "type": "public-key",
                    "authenticator_attachment": None,
                },
            )(),
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_rp_id=config.rp_id,
            expected_origin=config.origin,
            require_user_verification=(config.user_verification == "required"),
        )
    except Exception as e:
        raise PasskeyRegistrationError(f"Verification failed: {e!s}")
    finally:
        # Always delete the challenge
        _delete_challenge(challenge_id)

    # Determine device type
    device_type = "multi_device" if verification.credential_backed_up else "single_device"

    # Create and save the credential
    credential = PasskeyCredential.objects.create(
        user=user,
        credential_id=credential_id,
        public_key=bytes_to_base64url(verification.credential_public_key),
        sign_count=verification.sign_count,
        device_type=device_type,
        backed_up=verification.credential_backed_up,
        transports=transports or [],
        aaguid=str(verification.aaguid) if verification.aaguid else "",
        name=credential_name or "",
    )

    return credential


async def averify_registration_response(
    user,
    credential_id: str,
    client_data_json: str,
    attestation_object: str,
    challenge_id: str,
    transports: list[str] | None = None,
    credential_name: str | None = None,
):
    """
    Async version of verify_registration_response.

    Wraps sync webauthn library calls with sync_to_async and uses async ORM.
    """
    _ensure_webauthn()
    config = get_passkey_config()
    from django_matt.auth.passkeys.models import PasskeyCredential

    # Retrieve stored challenge
    challenge_data = _get_challenge(challenge_id)
    if not challenge_data:
        raise PasskeyRegistrationError("Challenge not found or expired")

    if challenge_data["type"] != "registration":
        raise PasskeyRegistrationError("Invalid challenge type")

    if challenge_data["user_id"] != user.pk:
        raise PasskeyRegistrationError("Challenge does not match user")

    # Get stored credential name if not provided
    if not credential_name:
        credential_name = challenge_data.get("credential_name", "")

    try:
        # Verify the registration response (sync webauthn call wrapped)
        verification = await sync_to_async(_verify_registration_response)(
            credential=type(
                "Credential",
                (),
                {
                    "id": credential_id,
                    "raw_id": base64url_to_bytes(credential_id),
                    "response": type(
                        "Response",
                        (),
                        {
                            "client_data_json": base64url_to_bytes(client_data_json),
                            "attestation_object": base64url_to_bytes(attestation_object),
                        },
                    )(),
                    "type": "public-key",
                    "authenticator_attachment": None,
                },
            )(),
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_rp_id=config.rp_id,
            expected_origin=config.origin,
            require_user_verification=(config.user_verification == "required"),
        )
    except Exception as e:
        raise PasskeyRegistrationError(f"Verification failed: {e!s}")
    finally:
        # Always delete the challenge
        _delete_challenge(challenge_id)

    # Determine device type
    device_type = "multi_device" if verification.credential_backed_up else "single_device"

    # Create and save the credential (async ORM)
    credential = await PasskeyCredential.objects.acreate(
        user=user,
        credential_id=credential_id,
        public_key=bytes_to_base64url(verification.credential_public_key),
        sign_count=verification.sign_count,
        device_type=device_type,
        backed_up=verification.credential_backed_up,
        transports=transports or [],
        aaguid=str(verification.aaguid) if verification.aaguid else "",
        name=credential_name or "",
    )

    return credential


# =============================================================================
# Authentication Functions
# =============================================================================


def generate_authentication_options(
    user=None,
    email: str | None = None,
) -> dict[str, Any]:
    """
    Generate WebAuthn authentication options.

    Args:
        user: Optional Django user object (for non-discoverable flow)
        email: Optional email to look up user (for non-discoverable flow)

    Returns:
        Dictionary with authentication options and challenge_id
    """
    _ensure_webauthn()
    config = get_passkey_config()

    # Validate config
    errors = config.validate()
    if errors:
        raise PasskeyAuthenticationError(f"Invalid passkey config: {'; '.join(errors)}")

    # Build allow credentials list
    allow_credentials = []
    user_id = None

    if user:
        user_id = user.pk
    elif email:
        User = get_user_model()
        try:
            user = User.objects.get(email=email)
            user_id = user.pk
        except User.DoesNotExist:
            # Don't reveal if user exists
            pass

    if user_id:
        credentials = _get_user_credentials(user)
        for cred in credentials:
            transports = []
            for t in cred.transports or []:
                try:
                    transports.append(AuthenticatorTransport(t))
                except ValueError:
                    pass  # Skip invalid transports

            allow_credentials.append(
                PublicKeyCredentialDescriptor(
                    id=base64url_to_bytes(cred.credential_id),
                    transports=transports if transports else None,
                )
            )

    # Generate options
    options = _generate_authentication_options(
        rp_id=config.rp_id,
        allow_credentials=allow_credentials if allow_credentials else None,
        user_verification=UserVerificationRequirement(config.user_verification),
        challenge=_generate_challenge(),
        timeout=config.challenge_timeout,
    )

    # Generate challenge ID and store
    challenge_id = secrets.token_urlsafe(32)
    _store_challenge(
        challenge_id=challenge_id,
        challenge=options.challenge,
        challenge_type="authentication",
        user_id=user_id,
    )

    # Convert to JSON-serializable dict
    options_json = options_to_json(options)
    import orjson

    options_dict = orjson.loads(options_json)
    options_dict["challenge_id"] = challenge_id

    return options_dict


def verify_authentication_response(
    credential_id: str,
    client_data_json: str,
    authenticator_data: str,
    signature: str,
    challenge_id: str,
    user_handle: str | None = None,
):
    """
    Verify an authentication response.

    Args:
        credential_id: The credential ID from the response
        client_data_json: The clientDataJSON from the response (base64url)
        authenticator_data: The authenticatorData from the response (base64url)
        signature: The signature from the response (base64url)
        challenge_id: The challenge ID from authentication options
        user_handle: Optional user handle (for discoverable credentials)

    Returns:
        Tuple of (user, credential) on success
    """
    _ensure_webauthn()
    config = get_passkey_config()
    from django_matt.auth.passkeys.models import PasskeyCredential

    User = get_user_model()

    # Retrieve stored challenge
    challenge_data = _get_challenge(challenge_id)
    if not challenge_data:
        raise PasskeyAuthenticationError("Challenge not found or expired")

    if challenge_data["type"] != "authentication":
        raise PasskeyAuthenticationError("Invalid challenge type")

    # Find the credential
    try:
        credential = PasskeyCredential.objects.select_related("user").get(
            credential_id=credential_id
        )
    except PasskeyCredential.DoesNotExist:
        _delete_challenge(challenge_id)
        raise PasskeyCredentialNotFoundError("Credential not found")

    # For discoverable credentials, verify user handle matches
    if user_handle:
        user_id_from_handle = _user_id_from_bytes(base64url_to_bytes(user_handle))
        if str(credential.user.pk) != user_id_from_handle:
            _delete_challenge(challenge_id)
            raise PasskeyAuthenticationError("User handle mismatch")

    try:
        # Verify the authentication response
        verification = _verify_authentication_response(
            credential=type(
                "Credential",
                (),
                {
                    "id": credential_id,
                    "raw_id": base64url_to_bytes(credential_id),
                    "response": type(
                        "Response",
                        (),
                        {
                            "client_data_json": base64url_to_bytes(client_data_json),
                            "authenticator_data": base64url_to_bytes(authenticator_data),
                            "signature": base64url_to_bytes(signature),
                            "user_handle": base64url_to_bytes(user_handle) if user_handle else None,
                        },
                    )(),
                    "type": "public-key",
                    "authenticator_attachment": None,
                },
            )(),
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_rp_id=config.rp_id,
            expected_origin=config.origin,
            credential_public_key=base64url_to_bytes(credential.public_key),
            credential_current_sign_count=credential.sign_count,
            require_user_verification=(config.user_verification == "required"),
        )
    except Exception as e:
        raise PasskeyAuthenticationError(f"Verification failed: {e!s}")
    finally:
        # Always delete the challenge
        _delete_challenge(challenge_id)

    # Update sign count and last used
    if not credential.update_sign_count(verification.new_sign_count):
        raise PasskeyAuthenticationError(
            "Credential counter did not increase. Possible cloned authenticator."
        )

    credential.last_used_at = timezone.now()
    credential.save(update_fields=["last_used_at"])

    return credential.user, credential


async def agenerate_authentication_options(
    user=None,
    email: str | None = None,
) -> dict[str, Any]:
    """
    Async version of generate_authentication_options.

    Wraps sync webauthn library calls with sync_to_async and uses async ORM.
    """
    _ensure_webauthn()
    config = get_passkey_config()

    # Validate config
    errors = config.validate()
    if errors:
        raise PasskeyAuthenticationError(f"Invalid passkey config: {'; '.join(errors)}")

    # Build allow credentials list
    allow_credentials = []
    user_id = None

    if user:
        user_id = user.pk
    elif email:
        User = get_user_model()
        try:
            user = await User.objects.aget(email=email)
            user_id = user.pk
        except User.DoesNotExist:
            # Don't reveal if user exists
            pass

    if user_id:
        from django_matt.auth.passkeys.models import PasskeyCredential

        async for cred in PasskeyCredential.objects.filter(user=user):
            transports = []
            for t in cred.transports or []:
                try:
                    transports.append(AuthenticatorTransport(t))
                except ValueError:
                    pass  # Skip invalid transports

            allow_credentials.append(
                PublicKeyCredentialDescriptor(
                    id=base64url_to_bytes(cred.credential_id),
                    transports=transports if transports else None,
                )
            )

    # Generate options (sync webauthn library call wrapped)
    options = await sync_to_async(_generate_authentication_options)(
        rp_id=config.rp_id,
        allow_credentials=allow_credentials if allow_credentials else None,
        user_verification=UserVerificationRequirement(config.user_verification),
        challenge=_generate_challenge(),
        timeout=config.challenge_timeout,
    )

    # Generate challenge ID and store
    challenge_id = secrets.token_urlsafe(32)
    _store_challenge(
        challenge_id=challenge_id,
        challenge=options.challenge,
        challenge_type="authentication",
        user_id=user_id,
    )

    # Convert to JSON-serializable dict
    options_json = options_to_json(options)
    import orjson

    options_dict = orjson.loads(options_json)
    options_dict["challenge_id"] = challenge_id

    return options_dict


async def averify_authentication_response(
    credential_id: str,
    client_data_json: str,
    authenticator_data: str,
    signature: str,
    challenge_id: str,
    user_handle: str | None = None,
):
    """
    Async version of verify_authentication_response.

    Wraps sync webauthn library calls with sync_to_async and uses async ORM.
    """
    _ensure_webauthn()
    config = get_passkey_config()
    from django_matt.auth.passkeys.models import PasskeyCredential

    # Retrieve stored challenge
    challenge_data = _get_challenge(challenge_id)
    if not challenge_data:
        raise PasskeyAuthenticationError("Challenge not found or expired")

    if challenge_data["type"] != "authentication":
        raise PasskeyAuthenticationError("Invalid challenge type")

    # Find the credential (async ORM)
    try:
        credential = await PasskeyCredential.objects.select_related("user").aget(
            credential_id=credential_id
        )
    except PasskeyCredential.DoesNotExist:
        _delete_challenge(challenge_id)
        raise PasskeyCredentialNotFoundError("Credential not found")

    # For discoverable credentials, verify user handle matches
    if user_handle:
        user_id_from_handle = _user_id_from_bytes(base64url_to_bytes(user_handle))
        if str(credential.user.pk) != user_id_from_handle:
            _delete_challenge(challenge_id)
            raise PasskeyAuthenticationError("User handle mismatch")

    try:
        # Verify the authentication response (sync webauthn call wrapped)
        verification = await sync_to_async(_verify_authentication_response)(
            credential=type(
                "Credential",
                (),
                {
                    "id": credential_id,
                    "raw_id": base64url_to_bytes(credential_id),
                    "response": type(
                        "Response",
                        (),
                        {
                            "client_data_json": base64url_to_bytes(client_data_json),
                            "authenticator_data": base64url_to_bytes(authenticator_data),
                            "signature": base64url_to_bytes(signature),
                            "user_handle": base64url_to_bytes(user_handle) if user_handle else None,
                        },
                    )(),
                    "type": "public-key",
                    "authenticator_attachment": None,
                },
            )(),
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_rp_id=config.rp_id,
            expected_origin=config.origin,
            credential_public_key=base64url_to_bytes(credential.public_key),
            credential_current_sign_count=credential.sign_count,
            require_user_verification=(config.user_verification == "required"),
        )
    except Exception as e:
        raise PasskeyAuthenticationError(f"Verification failed: {e!s}")
    finally:
        # Always delete the challenge
        _delete_challenge(challenge_id)

    # Update sign count and last used (async ORM)
    if not credential.update_sign_count(verification.new_sign_count):
        raise PasskeyAuthenticationError(
            "Credential counter did not increase. Possible cloned authenticator."
        )

    credential.last_used_at = timezone.now()
    await credential.asave(update_fields=["last_used_at"])

    return credential.user, credential

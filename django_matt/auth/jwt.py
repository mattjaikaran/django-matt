"""
JWT Authentication backend for Django Matt.

Provides JWT token generation, validation, and authentication
using our built-in JWT implementation (no external dependencies).
"""

import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest

from django_matt.auth.jwt_builtin import (
    JWTAlgorithmError,
    JWTDecodeError,
    JWTError,
    JWTExpiredError,
    JWTInvalidClaimError,
    JWTInvalidSignatureError,
    decode_jwt,
    encode_jwt,
)
from django_matt.auth.schemas import TokenPair, TokenPayload

# Backward-compatible exception aliases
InvalidTokenError = JWTError
ExpiredSignatureError = JWTExpiredError


class JWTConfig:
    """
    JWT configuration with sensible defaults.

    Configure in Django settings:
        DJANGO_MATT_JWT = {
            "SECRET_KEY": "your-secret-key",  # defaults to Django SECRET_KEY
            "ALGORITHM": "HS256",
            "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
            "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
            "ROTATE_REFRESH_TOKENS": True,
            "BLACKLIST_AFTER_ROTATION": True,
            "SIGNING_KEY": None,  # Optional separate signing key
            "VERIFYING_KEY": None,  # For asymmetric algorithms
            "AUDIENCE": None,
            "ISSUER": None,
            "USER_ID_FIELD": "id",
            "USER_ID_CLAIM": "sub",
            "TOKEN_TYPE_CLAIM": "type",
            "JTI_CLAIM": "jti",
            "AUTH_HEADER_TYPES": ["Bearer"],
            "AUTH_HEADER_NAME": "Authorization",
        }
    """

    def __init__(self):
        self._config = getattr(settings, "DJANGO_MATT_JWT", {})

    @property
    def secret_key(self) -> str:
        return self._config.get("SECRET_KEY", settings.SECRET_KEY)

    @property
    def algorithm(self) -> str:
        return self._config.get("ALGORITHM", "HS256")

    @property
    def access_token_lifetime(self) -> timedelta:
        return self._config.get("ACCESS_TOKEN_LIFETIME", timedelta(minutes=15))

    @property
    def refresh_token_lifetime(self) -> timedelta:
        return self._config.get("REFRESH_TOKEN_LIFETIME", timedelta(days=7))

    @property
    def rotate_refresh_tokens(self) -> bool:
        return self._config.get("ROTATE_REFRESH_TOKENS", True)

    @property
    def blacklist_after_rotation(self) -> bool:
        return self._config.get("BLACKLIST_AFTER_ROTATION", True)

    @property
    def signing_key(self) -> str:
        return self._config.get("SIGNING_KEY") or self.secret_key

    @property
    def verifying_key(self) -> str | None:
        return self._config.get("VERIFYING_KEY")

    @property
    def audience(self) -> str | None:
        return self._config.get("AUDIENCE")

    @property
    def issuer(self) -> str | None:
        return self._config.get("ISSUER")

    @property
    def user_id_field(self) -> str:
        return self._config.get("USER_ID_FIELD", "id")

    @property
    def user_id_claim(self) -> str:
        return self._config.get("USER_ID_CLAIM", "sub")

    @property
    def auth_header_types(self) -> list[str]:
        return self._config.get("AUTH_HEADER_TYPES", ["Bearer"])

    @property
    def auth_header_name(self) -> str:
        return self._config.get("AUTH_HEADER_NAME", "Authorization")


# Global config instance
jwt_config = JWTConfig()


def generate_jti() -> str:
    """Generate a unique JWT ID."""
    return secrets.token_urlsafe(32)


def create_access_token(
    user,
    extra_claims: dict[str, Any] | None = None,
    lifetime: timedelta | None = None,
) -> str:
    """
    Create a JWT access token for a user.

    Args:
        user: Django user instance
        extra_claims: Additional claims to include in the token
        lifetime: Override token lifetime

    Returns:
        Encoded JWT string
    """
    lifetime = lifetime or jwt_config.access_token_lifetime
    expires_in = int(lifetime.total_seconds())

    # Build payload
    payload = {
        jwt_config.user_id_claim: str(getattr(user, jwt_config.user_id_field)),
        "type": "access",
        "jti": generate_jti(),
    }

    # Add user info
    if hasattr(user, "email"):
        payload["email"] = user.email
    if hasattr(user, "username"):
        payload["username"] = user.username

    # Add roles (from groups)
    if hasattr(user, "groups"):
        payload["roles"] = list(user.groups.values_list("name", flat=True))

    # Add extra claims
    if extra_claims:
        payload.update(extra_claims)

    return encode_jwt(
        payload=payload,
        secret=jwt_config.signing_key,
        algorithm=jwt_config.algorithm,
        expires_in=expires_in,
        issuer=jwt_config.issuer,
        audience=jwt_config.audience,
    )


def create_refresh_token(
    user,
    extra_claims: dict[str, Any] | None = None,
    lifetime: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token for a user.

    Args:
        user: Django user instance
        extra_claims: Additional claims to include in the token
        lifetime: Override token lifetime

    Returns:
        Encoded JWT string
    """
    lifetime = lifetime or jwt_config.refresh_token_lifetime
    expires_in = int(lifetime.total_seconds())

    payload = {
        jwt_config.user_id_claim: str(getattr(user, jwt_config.user_id_field)),
        "type": "refresh",
        "jti": generate_jti(),
    }

    if extra_claims:
        payload.update(extra_claims)

    return encode_jwt(
        payload=payload,
        secret=jwt_config.signing_key,
        algorithm=jwt_config.algorithm,
        expires_in=expires_in,
        issuer=jwt_config.issuer,
        audience=jwt_config.audience,
    )


async def acreate_access_token(
    user,
    extra_claims: dict[str, Any] | None = None,
    lifetime: timedelta | None = None,
) -> str:
    """
    Async version of create_access_token.

    Uses async ORM for user.groups query. Use from async controllers.
    """
    lifetime = lifetime or jwt_config.access_token_lifetime
    expires_in = int(lifetime.total_seconds())

    payload = {
        jwt_config.user_id_claim: str(getattr(user, jwt_config.user_id_field)),
        "type": "access",
        "jti": generate_jti(),
    }

    if hasattr(user, "email"):
        payload["email"] = user.email
    if hasattr(user, "username"):
        payload["username"] = user.username

    # Async groups query
    if hasattr(user, "groups"):
        payload["roles"] = [
            name async for name in user.groups.values_list("name", flat=True)
        ]

    if extra_claims:
        payload.update(extra_claims)

    return encode_jwt(
        payload=payload,
        secret=jwt_config.signing_key,
        algorithm=jwt_config.algorithm,
        expires_in=expires_in,
        issuer=jwt_config.issuer,
        audience=jwt_config.audience,
    )


def create_token_pair(
    user,
    extra_claims: dict[str, Any] | None = None,
) -> TokenPair:
    """
    Create both access and refresh tokens for a user.

    Args:
        user: Django user instance
        extra_claims: Additional claims for both tokens

    Returns:
        TokenPair with access and refresh tokens
    """
    access_token = create_access_token(user, extra_claims)
    refresh_token = create_refresh_token(user, extra_claims)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=int(jwt_config.access_token_lifetime.total_seconds()),
        refresh_expires_in=int(jwt_config.refresh_token_lifetime.total_seconds()),
    )


async def acreate_token_pair(
    user,
    extra_claims: dict[str, Any] | None = None,
) -> TokenPair:
    """
    Async version of create_token_pair.

    Uses async ORM for groups query. Use from async controllers.
    """
    access_token = await acreate_access_token(user, extra_claims)
    refresh_token = create_refresh_token(user, extra_claims)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=int(jwt_config.access_token_lifetime.total_seconds()),
        refresh_expires_in=int(jwt_config.refresh_token_lifetime.total_seconds()),
    )


def decode_token(token: str, verify_type: str | None = None) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT string to decode
        verify_type: Optional token type to verify ("access" or "refresh")

    Returns:
        Decoded token payload

    Raises:
        InvalidTokenError: If token is invalid
        ExpiredSignatureError: If token has expired
    """
    try:
        # Determine verification key
        verify_key = jwt_config.verifying_key or jwt_config.signing_key

        payload = decode_jwt(
            token=token,
            secret=verify_key,
            algorithms=[jwt_config.algorithm],
            verify_iss=jwt_config.issuer,
            verify_aud=jwt_config.audience,
        )

        # Verify token type if specified
        if verify_type and payload.get("type") != verify_type:
            raise InvalidTokenError(f"Expected {verify_type} token")

        return TokenPayload(**payload)

    except JWTExpiredError:
        raise ExpiredSignatureError("Token has expired")
    except JWTError as e:
        raise InvalidTokenError(str(e))


def verify_access_token(token: str) -> TokenPayload:
    """Verify and decode an access token."""
    return decode_token(token, verify_type="access")


def verify_refresh_token(token: str) -> TokenPayload:
    """Verify and decode a refresh token."""
    return decode_token(token, verify_type="refresh")


def refresh_tokens(refresh_token: str) -> TokenPair:
    """
    Use a refresh token to get new access and refresh tokens.

    Args:
        refresh_token: The refresh token

    Returns:
        New TokenPair

    Raises:
        InvalidTokenError: If refresh token is invalid
    """
    # Verify the refresh token
    payload = verify_refresh_token(refresh_token)

    # Get the user
    User = get_user_model()
    try:
        user = User.objects.get(**{jwt_config.user_id_field: payload.sub})
    except User.DoesNotExist:
        raise InvalidTokenError("User not found")

    if not user.is_active:
        raise InvalidTokenError("User is inactive")

    # Create new token pair
    return create_token_pair(user)


async def async_refresh_tokens(refresh_token: str) -> TokenPair:
    """
    Async version of refresh_tokens. Use from async controllers.

    Args:
        refresh_token: The refresh token

    Returns:
        New TokenPair

    Raises:
        InvalidTokenError: If refresh token is invalid
    """
    payload = verify_refresh_token(refresh_token)

    User = get_user_model()
    try:
        user = await User.objects.aget(**{jwt_config.user_id_field: payload.sub})
    except User.DoesNotExist:
        raise InvalidTokenError("User not found")

    if not user.is_active:
        raise InvalidTokenError("User is inactive")

    return create_token_pair(user)


def get_token_from_request(request: HttpRequest) -> str | None:
    """
    Extract JWT token from request headers.

    Looks for Authorization header with Bearer token.

    Args:
        request: Django HttpRequest

    Returns:
        Token string or None if not found
    """
    auth_header = request.headers.get(jwt_config.auth_header_name, "")

    if not auth_header:
        # Also check META for older Django versions
        auth_header = request.META.get(
            f"HTTP_{jwt_config.auth_header_name.upper().replace('-', '_')}", ""
        )

    if not auth_header:
        return None

    parts = auth_header.split()

    if len(parts) != 2:
        return None

    auth_type, token = parts

    if auth_type not in jwt_config.auth_header_types:
        return None

    return token


def get_user_from_token(token: str, *, _payload: "TokenPayload | None" = None):
    """
    Get Django user from a JWT token.

    Args:
        token: JWT access token
        _payload: Pre-verified payload to avoid double-decode (internal optimization)

    Returns:
        Django User instance or None
    """
    try:
        payload = _payload or verify_access_token(token)
        User = get_user_model()
        return User.objects.get(**{jwt_config.user_id_field: payload.sub})
    except (InvalidTokenError, ExpiredSignatureError):
        return None
    except Exception:
        return None


async def aget_user_from_token(token: str, *, _payload: "TokenPayload | None" = None):
    """
    Async version of get_user_from_token.

    Args:
        token: JWT access token
        _payload: Pre-verified payload to avoid double-decode (internal optimization)

    Returns:
        Django User instance or None
    """
    try:
        payload = _payload or verify_access_token(token)
        User = get_user_model()
        return await User.objects.aget(**{jwt_config.user_id_field: payload.sub})
    except (InvalidTokenError, ExpiredSignatureError):
        return None
    except Exception:
        return None


class JWTAuthentication:
    """
    JWT authentication class for use with controllers and views.

    Example:
        class MyController(APIController):
            authentication_classes = [JWTAuthentication]
    """

    def authenticate(self, request: HttpRequest):
        """
        Authenticate the request and return (user, token) or None.
        """
        token = get_token_from_request(request)

        if token is None:
            return None

        try:
            payload = verify_access_token(token)
        except (InvalidTokenError, ExpiredSignatureError):
            return None

        User = get_user_model()
        try:
            user = User.objects.get(**{jwt_config.user_id_field: payload.sub})
        except User.DoesNotExist:
            return None

        if not user.is_active:
            return None

        return (user, token)

    def authenticate_header(self, request: HttpRequest) -> str:
        """
        Return the WWW-Authenticate header value for 401 responses.
        """
        return f'{jwt_config.auth_header_types[0]} realm="api"'


# Export functions, classes, and exceptions
__all__ = [
    # Config
    "JWTConfig",
    "jwt_config",
    # Token creation
    "create_access_token",
    "acreate_access_token",
    "create_refresh_token",
    "create_token_pair",
    "acreate_token_pair",
    # Token verification
    "decode_token",
    "verify_access_token",
    "verify_refresh_token",
    "refresh_tokens",
    # Request helpers
    "get_token_from_request",
    "get_user_from_token",
    "generate_jti",
    # Authentication class
    "JWTAuthentication",
    # Exceptions (backward-compatible aliases)
    "InvalidTokenError",
    "ExpiredSignatureError",
    # Native exception classes
    "JWTError",
    "JWTExpiredError",
    "JWTInvalidSignatureError",
    "JWTInvalidClaimError",
    "JWTDecodeError",
    "JWTAlgorithmError",
]

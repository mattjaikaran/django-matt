"""
Built-in JWT implementation using Python stdlib.

Replaces PyJWT dependency with native Python implementation.
Supports HMAC algorithms (HS256, HS384, HS512).

For RSA/EC algorithms, the optional `cryptography` package is required.

Usage:
    from django_matt.auth.jwt_builtin import (
        encode_jwt,
        decode_jwt,
        JWTError,
    )

    # Create a token
    token = encode_jwt(
        payload={"sub": "user123", "role": "admin"},
        secret="your-secret-key",
        algorithm="HS256",
        expires_in=3600,  # 1 hour
    )

    # Decode and verify a token
    try:
        payload = decode_jwt(token, secret="your-secret-key")
        print(payload["sub"])  # "user123"
    except JWTError as e:
        print(f"Invalid token: {e}")
"""

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import orjson

from django_matt._accel import HAS_RUST, jwt_decode_rust, jwt_encode_rust


class JWTError(Exception):
    """Base exception for JWT errors."""


class JWTDecodeError(JWTError):
    """Token could not be decoded."""


class JWTExpiredError(JWTError):
    """Token has expired."""


class JWTNotYetValidError(JWTError):
    """Token is not yet valid (nbf claim)."""


class JWTInvalidSignatureError(JWTError):
    """Token signature is invalid."""


class JWTInvalidClaimError(JWTError):
    """Token has invalid claims."""


class JWTAlgorithmError(JWTError):
    """Unsupported or invalid algorithm."""


# HMAC algorithms and their hash functions
HMAC_ALGORITHMS = {
    "HS256": hashlib.sha256,
    "HS384": hashlib.sha384,
    "HS512": hashlib.sha512,
}

# RSA algorithms (require cryptography package)
RSA_ALGORITHMS = {"RS256", "RS384", "RS512"}

# EC algorithms (require cryptography package)
EC_ALGORITHMS = {"ES256", "ES384", "ES512"}

# Mapping of EC algorithms to their curve names and hash functions
EC_ALGORITHM_CONFIG = {
    "ES256": ("secp256r1", "sha256", 32),
    "ES384": ("secp384r1", "sha384", 48),
    "ES512": ("secp521r1", "sha512", 66),  # Note: ES512 uses secp521r1
}

# RSA algorithm hash mapping
RSA_ALGORITHM_HASHES = {
    "RS256": "sha256",
    "RS384": "sha384",
    "RS512": "sha512",
}

# All supported algorithms
SUPPORTED_ALGORITHMS = list(HMAC_ALGORITHMS.keys()) + list(RSA_ALGORITHMS) + list(EC_ALGORITHMS)


def _requires_cryptography(algorithm: str) -> bool:
    """Check if an algorithm requires the cryptography package."""
    return algorithm in RSA_ALGORITHMS or algorithm in EC_ALGORITHMS


def _get_cryptography():
    """Import and return cryptography modules, raising helpful error if not available."""
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

        return {
            "hashes": hashes,
            "serialization": serialization,
            "rsa": rsa,
            "ec": ec,
            "padding": padding,
            "default_backend": default_backend,
        }
    except ImportError:
        raise JWTAlgorithmError(
            "RSA/EC algorithms require the 'cryptography' package. "
            "Install with: uv add 'django-matt[jwt-asymmetric]' or uv add cryptography"
        )


def _base64url_encode(data: bytes) -> str:
    """Encode bytes to base64url without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    """Decode base64url string (with or without padding)."""
    # Add padding if needed
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def _json_encode(obj: dict[str, Any]) -> bytes:
    """Encode dict to JSON bytes."""
    return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)


def _json_decode(data: bytes) -> dict[str, Any]:
    """Decode JSON bytes to dict."""
    return orjson.loads(data)


def _load_private_key(key: str | bytes, password: bytes | None = None):
    """Load a private key from PEM format."""
    crypto = _get_cryptography()
    if isinstance(key, str):
        key = key.encode("utf-8")

    return crypto["serialization"].load_pem_private_key(
        key, password=password, backend=crypto["default_backend"]()
    )


def _load_public_key(key: str | bytes):
    """Load a public key from PEM format."""
    crypto = _get_cryptography()
    if isinstance(key, str):
        key = key.encode("utf-8")

    try:
        return crypto["serialization"].load_pem_public_key(key, backend=crypto["default_backend"]())
    except Exception:
        # Try loading as certificate
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(key, crypto["default_backend"]())
        return cert.public_key()


def _create_signature(
    signing_input: str,
    secret: str | bytes,
    algorithm: str,
) -> bytes:
    """Create signature for the given input using the specified algorithm."""
    data = signing_input.encode("utf-8")

    # HMAC algorithms
    if algorithm in HMAC_ALGORITHMS:
        if isinstance(secret, str):
            secret = secret.encode("utf-8")
        hash_func = HMAC_ALGORITHMS[algorithm]
        return hmac.new(secret, data, hash_func).digest()

    # RSA algorithms
    if algorithm in RSA_ALGORITHMS:
        crypto = _get_cryptography()
        private_key = _load_private_key(secret)

        hash_name = RSA_ALGORITHM_HASHES[algorithm]
        hash_class = getattr(crypto["hashes"], hash_name.upper())()

        return private_key.sign(
            data,
            crypto["padding"].PKCS1v15(),
            hash_class,
        )

    # EC algorithms
    if algorithm in EC_ALGORITHMS:
        crypto = _get_cryptography()
        private_key = _load_private_key(secret)

        _, hash_name, sig_size = EC_ALGORITHM_CONFIG[algorithm]
        hash_class = getattr(crypto["hashes"], hash_name.upper())()

        from cryptography.hazmat.primitives.asymmetric import utils as asym_utils

        der_sig = private_key.sign(data, crypto["ec"].ECDSA(hash_class))

        # Convert DER signature to raw format (r || s)
        r, s = asym_utils.decode_dss_signature(der_sig)
        return r.to_bytes(sig_size, byteorder="big") + s.to_bytes(sig_size, byteorder="big")

    raise JWTAlgorithmError(f"Unsupported algorithm: {algorithm}")


def _verify_signature(
    signing_input: str,
    signature: bytes,
    secret: str | bytes,
    algorithm: str,
) -> bool:
    """Verify signature for the given input."""
    data = signing_input.encode("utf-8")

    # HMAC algorithms
    if algorithm in HMAC_ALGORITHMS:
        expected = _create_signature(signing_input, secret, algorithm)
        return hmac.compare_digest(signature, expected)

    # RSA algorithms
    if algorithm in RSA_ALGORITHMS:
        crypto = _get_cryptography()
        public_key = _load_public_key(secret)

        hash_name = RSA_ALGORITHM_HASHES[algorithm]
        hash_class = getattr(crypto["hashes"], hash_name.upper())()

        try:
            public_key.verify(
                signature,
                data,
                crypto["padding"].PKCS1v15(),
                hash_class,
            )
            return True
        except Exception:
            return False

    # EC algorithms
    if algorithm in EC_ALGORITHMS:
        crypto = _get_cryptography()
        public_key = _load_public_key(secret)

        _, hash_name, sig_size = EC_ALGORITHM_CONFIG[algorithm]
        hash_class = getattr(crypto["hashes"], hash_name.upper())()

        # Convert raw signature to DER format
        from cryptography.hazmat.primitives.asymmetric import utils as asym_utils

        r = int.from_bytes(signature[:sig_size], byteorder="big")
        s = int.from_bytes(signature[sig_size:], byteorder="big")
        der_sig = asym_utils.encode_dss_signature(r, s)

        try:
            public_key.verify(der_sig, data, crypto["ec"].ECDSA(hash_class))
            return True
        except Exception:
            return False

    raise JWTAlgorithmError(f"Unsupported algorithm: {algorithm}")


def encode_jwt(
    payload: dict[str, Any],
    secret: str | bytes,
    algorithm: str = "HS256",
    expires_in: int | None = None,
    issued_at: bool = True,
    not_before: int | None = None,
    issuer: str | None = None,
    audience: str | list[str] | None = None,
    jwt_id: str | None = None,
    headers: dict[str, Any] | None = None,
) -> str:
    """
    Encode a JWT token.

    Args:
        payload: The claims to include in the token
        secret: The secret key for signing
        algorithm: Signing algorithm (HS256, HS384, HS512)
        expires_in: Seconds until expiration (sets 'exp' claim)
        issued_at: Add 'iat' claim with current timestamp
        not_before: Seconds until token becomes valid (sets 'nbf' claim)
        issuer: Token issuer (sets 'iss' claim)
        audience: Token audience (sets 'aud' claim)
        jwt_id: Unique token ID (sets 'jti' claim)
        headers: Additional headers to include

    Returns:
        The encoded JWT string

    Example:
        >>> token = encode_jwt(
        ...     {"user_id": 123},
        ...     secret="mysecret",
        ...     expires_in=3600,
        ... )
    """
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise JWTAlgorithmError(
            f"Unsupported algorithm: {algorithm}. Supported: {', '.join(SUPPORTED_ALGORITHMS)}"
        )

    # Build header
    header = {"alg": algorithm, "typ": "JWT"}
    if headers:
        header.update(headers)

    # Build payload with registered claims
    claims = dict(payload)
    now = int(time.time())

    if issued_at:
        claims["iat"] = now

    if expires_in is not None:
        claims["exp"] = now + expires_in

    if not_before is not None:
        claims["nbf"] = now + not_before

    if issuer is not None:
        claims["iss"] = issuer

    if audience is not None:
        claims["aud"] = audience if isinstance(audience, list) else [audience]

    if jwt_id is not None:
        claims["jti"] = jwt_id

    # Fast path: use Rust for HMAC algorithms (no custom headers)
    if HAS_RUST and algorithm in HMAC_ALGORITHMS and not headers:
        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        claims_json = orjson.dumps(claims, option=orjson.OPT_SORT_KEYS)
        return jwt_encode_rust(claims_json, secret_bytes, algorithm)

    # Encode segments
    header_segment = _base64url_encode(_json_encode(header))
    payload_segment = _base64url_encode(_json_encode(claims))
    signing_input = f"{header_segment}.{payload_segment}"

    # Create signature
    signature = _create_signature(signing_input, secret, algorithm)
    signature_segment = _base64url_encode(signature)

    return f"{signing_input}.{signature_segment}"


def decode_jwt(
    token: str,
    secret: str | bytes,
    algorithms: list[str] | None = None,
    verify_exp: bool = True,
    verify_nbf: bool = True,
    verify_iat: bool = False,
    verify_iss: str | None = None,
    verify_aud: str | list[str] | None = None,
    leeway: int = 0,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: The JWT string to decode
        secret: The secret key for verification
        algorithms: Allowed algorithms (default: ["HS256"])
        verify_exp: Verify expiration claim
        verify_nbf: Verify not-before claim
        verify_iat: Verify issued-at claim
        verify_iss: Expected issuer (None to skip verification)
        verify_aud: Expected audience (None to skip verification)
        leeway: Seconds of leeway for time-based claims
        options: Additional verification options

    Returns:
        The decoded payload dict

    Raises:
        JWTDecodeError: Token format is invalid
        JWTExpiredError: Token has expired
        JWTNotYetValidError: Token is not yet valid
        JWTInvalidSignatureError: Signature verification failed
        JWTInvalidClaimError: Claims verification failed

    Example:
        >>> payload = decode_jwt(token, secret="mysecret")
        >>> print(payload["user_id"])
    """
    if algorithms is None:
        algorithms = ["HS256"]

    # Validate algorithm list
    for alg in algorithms:
        if alg not in SUPPORTED_ALGORITHMS:
            raise JWTAlgorithmError(f"Unsupported algorithm: {alg}")

    # Fast path: use Rust for simple HMAC decode (no nbf/iat/iss/aud verification)
    if (
        HAS_RUST
        and len(algorithms) == 1
        and algorithms[0] in HMAC_ALGORITHMS
        and not verify_nbf
        and not verify_iat
        and verify_iss is None
        and verify_aud is None
        and options is None
    ):
        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        try:
            return dict(jwt_decode_rust(token, secret_bytes, algorithms[0], verify_exp, leeway))
        except ValueError as e:
            msg = str(e)
            if "expired" in msg.lower():
                raise JWTExpiredError(msg)
            if "signature" in msg.lower():
                raise JWTInvalidSignatureError(msg)
            raise JWTDecodeError(msg)

    # Split token
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise JWTDecodeError("Invalid token format")

        header_segment, payload_segment, signature_segment = parts
    except Exception as e:
        raise JWTDecodeError(f"Invalid token format: {e}")

    # Decode header
    try:
        header = _json_decode(_base64url_decode(header_segment))
    except Exception as e:
        raise JWTDecodeError(f"Invalid header: {e}")

    # Check algorithm
    alg = header.get("alg")
    if alg not in algorithms:
        raise JWTAlgorithmError(f"Algorithm {alg} not allowed. Allowed: {', '.join(algorithms)}")

    # Verify signature
    signing_input = f"{header_segment}.{payload_segment}"
    try:
        signature = _base64url_decode(signature_segment)
    except Exception as e:
        raise JWTDecodeError(f"Invalid signature encoding: {e}")

    if not _verify_signature(signing_input, signature, secret, alg):
        raise JWTInvalidSignatureError("Signature verification failed")

    # Decode payload
    try:
        payload = _json_decode(_base64url_decode(payload_segment))
    except Exception as e:
        raise JWTDecodeError(f"Invalid payload: {e}")

    # Verify claims
    now = int(time.time())

    # Expiration
    if verify_exp and "exp" in payload:
        exp = payload["exp"]
        if not isinstance(exp, (int, float)):
            raise JWTInvalidClaimError("Invalid 'exp' claim")
        if now > exp + leeway:
            raise JWTExpiredError("Token has expired")

    # Not Before
    if verify_nbf and "nbf" in payload:
        nbf = payload["nbf"]
        if not isinstance(nbf, (int, float)):
            raise JWTInvalidClaimError("Invalid 'nbf' claim")
        if now < nbf - leeway:
            raise JWTNotYetValidError("Token is not yet valid")

    # Issued At
    if verify_iat and "iat" in payload:
        iat = payload["iat"]
        if not isinstance(iat, (int, float)):
            raise JWTInvalidClaimError("Invalid 'iat' claim")
        if iat > now + leeway:
            raise JWTInvalidClaimError("Token issued in the future")

    # Issuer
    if verify_iss is not None:
        iss = payload.get("iss")
        if iss != verify_iss:
            raise JWTInvalidClaimError(f"Invalid issuer. Expected: {verify_iss}, got: {iss}")

    # Audience
    if verify_aud is not None:
        aud = payload.get("aud")
        if aud is None:
            raise JWTInvalidClaimError("Token missing 'aud' claim")

        expected_aud = [verify_aud] if isinstance(verify_aud, str) else verify_aud
        token_aud = aud if isinstance(aud, list) else [aud]

        if not any(a in token_aud for a in expected_aud):
            raise JWTInvalidClaimError(
                f"Invalid audience. Expected: {expected_aud}, got: {token_aud}"
            )

    return payload


def get_unverified_header(token: str) -> dict[str, Any]:
    """
    Get the header from a JWT without verification.

    Useful for determining the algorithm before verification.

    Args:
        token: The JWT string

    Returns:
        The header dict

    Warning:
        Do not trust this data for security decisions without verification.
    """
    try:
        header_segment = token.split(".")[0]
        return _json_decode(_base64url_decode(header_segment))
    except Exception as e:
        raise JWTDecodeError(f"Invalid token header: {e}")


def get_unverified_payload(token: str) -> dict[str, Any]:
    """
    Get the payload from a JWT without verification.

    Useful for inspecting claims before verification.

    Args:
        token: The JWT string

    Returns:
        The payload dict

    Warning:
        Do not trust this data for security decisions without verification.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise JWTDecodeError("Invalid token format")
        return _json_decode(_base64url_decode(parts[1]))
    except Exception as e:
        raise JWTDecodeError(f"Invalid token payload: {e}")


@dataclass
class JWTToken:
    """
    Wrapper class for JWT tokens with convenient methods.

    Example:
        >>> token = JWTToken.create(
        ...     payload={"user_id": 123},
        ...     secret="mysecret",
        ...     expires_in=3600,
        ... )
        >>> print(token.user_id)  # Access claims as attributes
        >>> if token.is_expired:
        ...     print("Token expired!")
    """

    token: str
    _payload: dict[str, Any] | None = None
    _header: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        payload: dict[str, Any],
        secret: str | bytes,
        **kwargs,
    ) -> "JWTToken":
        """Create a new JWT token."""
        token_str = encode_jwt(payload, secret, **kwargs)
        return cls(token=token_str, _payload=payload)

    @classmethod
    def from_string(
        cls,
        token: str,
        secret: str | bytes,
        **kwargs,
    ) -> "JWTToken":
        """Create from existing token string with verification."""
        payload = decode_jwt(token, secret, **kwargs)
        return cls(token=token, _payload=payload)

    @property
    def payload(self) -> dict[str, Any]:
        """Get the token payload."""
        if self._payload is None:
            self._payload = get_unverified_payload(self.token)
        return self._payload

    @property
    def header(self) -> dict[str, Any]:
        """Get the token header."""
        if self._header is None:
            self._header = get_unverified_header(self.token)
        return self._header

    @property
    def algorithm(self) -> str:
        """Get the signing algorithm."""
        return self.header.get("alg", "unknown")

    @property
    def expires_at(self) -> datetime | None:
        """Get expiration time as datetime."""
        exp = self.payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=UTC)
        return None

    @property
    def issued_at(self) -> datetime | None:
        """Get issued time as datetime."""
        iat = self.payload.get("iat")
        if iat:
            return datetime.fromtimestamp(iat, tz=UTC)
        return None

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        exp = self.payload.get("exp")
        if exp is None:
            return False
        return int(time.time()) > exp

    @property
    def time_until_expiry(self) -> int | None:
        """Get seconds until expiration (negative if expired)."""
        exp = self.payload.get("exp")
        if exp is None:
            return None
        return exp - int(time.time())

    def __getattr__(self, name: str) -> Any:
        """Access claims as attributes."""
        if name.startswith("_"):
            raise AttributeError(name)
        return self.payload.get(name)

    def __str__(self) -> str:
        return self.token

    def __repr__(self) -> str:
        return f"JWTToken(algorithm={self.algorithm}, expires_at={self.expires_at})"


# Utility functions for common operations
def create_access_token(
    user_id: str | int,
    secret: str | bytes,
    expires_in: int = 3600,
    extra_claims: dict[str, Any] | None = None,
    **kwargs,
) -> str:
    """
    Create an access token for a user.

    Args:
        user_id: The user identifier
        secret: Signing secret
        expires_in: Seconds until expiration (default 1 hour)
        extra_claims: Additional claims to include

    Returns:
        The encoded JWT string
    """
    payload = {"sub": str(user_id), "type": "access"}
    if extra_claims:
        payload.update(extra_claims)

    return encode_jwt(payload, secret, expires_in=expires_in, **kwargs)


def create_refresh_token(
    user_id: str | int,
    secret: str | bytes,
    expires_in: int = 604800,  # 7 days
    extra_claims: dict[str, Any] | None = None,
    **kwargs,
) -> str:
    """
    Create a refresh token for a user.

    Args:
        user_id: The user identifier
        secret: Signing secret
        expires_in: Seconds until expiration (default 7 days)
        extra_claims: Additional claims to include

    Returns:
        The encoded JWT string
    """
    import uuid

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return encode_jwt(payload, secret, expires_in=expires_in, **kwargs)


def verify_token_type(token: str, expected_type: str, secret: str | bytes) -> bool:
    """
    Verify that a token is of the expected type.

    Args:
        token: The JWT to verify
        expected_type: Expected token type ("access" or "refresh")
        secret: Signing secret

    Returns:
        True if token is valid and of expected type
    """
    try:
        payload = decode_jwt(token, secret)
        return payload.get("type") == expected_type
    except JWTError:
        return False

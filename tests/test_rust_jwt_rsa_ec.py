"""Tests for RSA/EC JWT signing via Rust extensions."""

import time

import pytest

cryptography = pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from django_matt.auth.jwt_builtin import (
    JWTDecodeError,
    JWTExpiredError,
    JWTInvalidSignatureError,
    decode_jwt,
    encode_jwt,
)


# ---------------------------------------------------------------------------
# Key fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate a 2048-bit RSA key pair."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture(scope="module")
def ec_p256_keypair():
    """Generate an EC P-256 key pair."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture(scope="module")
def ec_p384_keypair():
    """Generate an EC P-384 key pair."""
    private_key = ec.generate_private_key(ec.SECP384R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


# ---------------------------------------------------------------------------
# RSA roundtrip tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("algorithm", ["RS256", "RS384", "RS512"])
def test_rsa_encode_decode_roundtrip(rsa_keypair, algorithm):
    private_pem, public_pem = rsa_keypair
    payload = {"sub": "user42", "role": "admin"}

    token = encode_jwt(payload, secret=private_pem, algorithm=algorithm, expires_in=300)
    decoded = decode_jwt(token, secret=public_pem, algorithms=[algorithm])

    assert decoded["sub"] == "user42"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded


# ---------------------------------------------------------------------------
# EC roundtrip tests
# ---------------------------------------------------------------------------

def test_es256_encode_decode_roundtrip(ec_p256_keypair):
    private_pem, public_pem = ec_p256_keypair
    payload = {"sub": "user99", "scope": "read"}

    token = encode_jwt(payload, secret=private_pem, algorithm="ES256", expires_in=300)
    decoded = decode_jwt(token, secret=public_pem, algorithms=["ES256"])

    assert decoded["sub"] == "user99"
    assert decoded["scope"] == "read"


def test_es384_encode_decode_roundtrip(ec_p384_keypair):
    private_pem, public_pem = ec_p384_keypair
    payload = {"sub": "user77", "tier": "premium"}

    token = encode_jwt(payload, secret=private_pem, algorithm="ES384", expires_in=300)
    decoded = decode_jwt(token, secret=public_pem, algorithms=["ES384"])

    assert decoded["sub"] == "user77"
    assert decoded["tier"] == "premium"


# ---------------------------------------------------------------------------
# Invalid signature detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("algorithm", ["RS256", "RS384", "RS512"])
def test_rsa_invalid_signature(rsa_keypair, algorithm):
    private_pem, public_pem = rsa_keypair
    token = encode_jwt({"sub": "x"}, secret=private_pem, algorithm=algorithm, expires_in=300)

    # Tamper with the signature
    parts = token.rsplit(".", 1)
    tampered = parts[0] + ".AAAA" + parts[1][4:]

    with pytest.raises((JWTInvalidSignatureError, JWTDecodeError)):
        decode_jwt(tampered, secret=public_pem, algorithms=[algorithm])


def test_ec_invalid_signature(ec_p256_keypair):
    private_pem, public_pem = ec_p256_keypair
    token = encode_jwt({"sub": "x"}, secret=private_pem, algorithm="ES256", expires_in=300)

    parts = token.rsplit(".", 1)
    tampered = parts[0] + ".AAAA" + parts[1][4:]

    with pytest.raises((JWTInvalidSignatureError, JWTDecodeError)):
        decode_jwt(tampered, secret=public_pem, algorithms=["ES256"])


# ---------------------------------------------------------------------------
# Wrong key detection
# ---------------------------------------------------------------------------

def test_rsa_wrong_key():
    """Decoding with a different RSA key pair should fail."""
    key1 = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key2 = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    priv1 = key1.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub2 = key2.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    token = encode_jwt({"sub": "a"}, secret=priv1, algorithm="RS256", expires_in=300)

    with pytest.raises((JWTInvalidSignatureError, JWTDecodeError)):
        decode_jwt(token, secret=pub2, algorithms=["RS256"])


def test_ec_wrong_key():
    """Decoding with a different EC key pair should fail."""
    key1 = ec.generate_private_key(ec.SECP256R1())
    key2 = ec.generate_private_key(ec.SECP256R1())

    priv1 = key1.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub2 = key2.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    token = encode_jwt({"sub": "a"}, secret=priv1, algorithm="ES256", expires_in=300)

    with pytest.raises((JWTInvalidSignatureError, JWTDecodeError)):
        decode_jwt(token, secret=pub2, algorithms=["ES256"])


# ---------------------------------------------------------------------------
# Expired token tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("algorithm,fixture_name", [
    ("RS256", "rsa_keypair"),
    ("ES256", "ec_p256_keypair"),
])
def test_expired_token_asymmetric(algorithm, fixture_name, request):
    private_pem, public_pem = request.getfixturevalue(fixture_name)

    token = encode_jwt(
        {"sub": "user1"},
        secret=private_pem,
        algorithm=algorithm,
        expires_in=-10,  # already expired
    )

    with pytest.raises(JWTExpiredError):
        decode_jwt(token, secret=public_pem, algorithms=[algorithm])


# ---------------------------------------------------------------------------
# Rust acceleration detection
# ---------------------------------------------------------------------------

def test_rust_acceleration_available():
    """Verify whether Rust acceleration is detected (informational)."""
    from django_matt._accel import HAS_RUST

    # This test passes regardless — it just logs the state
    if HAS_RUST:
        print("Rust JWT acceleration: ACTIVE")
    else:
        print("Rust JWT acceleration: FALLBACK (Python cryptography)")


# ---------------------------------------------------------------------------
# Direct Rust function tests (when available)
# ---------------------------------------------------------------------------

def test_rust_jwt_encode_decode_rsa_direct(rsa_keypair):
    """Test Rust functions directly if available."""
    try:
        from django_matt._rust import jwt_decode, jwt_encode
    except ImportError:
        pytest.skip("Rust extensions not available")

    import orjson

    private_pem, public_pem = rsa_keypair
    payload = {"sub": "direct_test", "exp": int(time.time()) + 300}
    payload_json = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    token = jwt_encode(payload_json, private_pem.encode(), "RS256")
    decoded = dict(jwt_decode(token, public_pem.encode(), "RS256", True, 0))

    assert decoded["sub"] == "direct_test"


def test_rust_jwt_encode_decode_ec_direct(ec_p256_keypair):
    """Test Rust EC functions directly if available."""
    try:
        from django_matt._rust import jwt_decode, jwt_encode
    except ImportError:
        pytest.skip("Rust extensions not available")

    import orjson

    private_pem, public_pem = ec_p256_keypair
    payload = {"sub": "ec_direct", "exp": int(time.time()) + 300}
    payload_json = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    token = jwt_encode(payload_json, private_pem.encode(), "ES256")
    decoded = dict(jwt_decode(token, public_pem.encode(), "ES256", True, 0))

    assert decoded["sub"] == "ec_direct"


def test_rust_jwt_verify_rsa(rsa_keypair):
    """Test Rust jwt_verify with RSA."""
    try:
        from django_matt._rust import jwt_encode, jwt_verify
    except ImportError:
        pytest.skip("Rust extensions not available")

    import orjson

    private_pem, public_pem = rsa_keypair
    payload = {"sub": "verify_test", "exp": int(time.time()) + 300}
    payload_json = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    token = jwt_encode(payload_json, private_pem.encode(), "RS256")
    assert jwt_verify(token, public_pem.encode(), "RS256") is True
    assert jwt_verify(token + "tampered", public_pem.encode(), "RS256") is False


def test_rust_jwt_verify_ec(ec_p256_keypair):
    """Test Rust jwt_verify with EC."""
    try:
        from django_matt._rust import jwt_encode, jwt_verify
    except ImportError:
        pytest.skip("Rust extensions not available")

    import orjson

    private_pem, public_pem = ec_p256_keypair
    payload = {"sub": "verify_ec", "exp": int(time.time()) + 300}
    payload_json = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    token = jwt_encode(payload_json, private_pem.encode(), "ES256")
    assert jwt_verify(token, public_pem.encode(), "ES256") is True

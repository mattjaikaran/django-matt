# JWT Acceleration

## What It Is

HMAC-based JWT encode/decode/verify operations compiled to Rust. Every authenticated request in a JWT-based API hits this path — token verification happens in middleware before any view code runs.

## Why It Exists

JWT verification involves:
1. Base64url decoding the header and payload
2. HMAC-SHA computation over the signing input
3. Constant-time signature comparison
4. JSON parsing of the payload

Python's `hmac` module is already C-accelerated (via OpenSSL), so the raw HMAC speedup is modest. The Rust implementation's main advantages are:

- **GIL release** — HMAC computation runs without holding the GIL, allowing other Python threads/coroutines to proceed. In an ASGI server with multiple workers, this directly improves concurrency.
- **Single-pass pipeline** — base64 decode + HMAC + comparison in one native call, avoiding Python object creation between steps.
- **Constant-time comparison** — uses the `subtle` crate's `ConstantTimeEq` trait, which is guaranteed constant-time at the compiler level (not just "probably" constant-time like Python's `hmac.compare_digest`).

## How It Works

### Encode

```python
from django_matt._accel import jwt_encode_rust

token = jwt_encode_rust(
    payload_json=b'{"sub":"user123","exp":1234567890}',  # pre-serialized with orjson
    secret=b"your-secret-key",
    algorithm="HS256",  # HS256, HS384, or HS512
)
# → "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIi..."
```

### Decode + Verify

```python
from django_matt._accel import jwt_decode_rust

payload_dict = jwt_decode_rust(
    token="eyJhbGci...",
    secret=b"your-secret-key",
    algorithm="HS256",
    verify_exp=True,   # check expiration
    leeway=0,          # seconds of clock skew tolerance
)
# → {"sub": "user123", "exp": 1234567890}
```

### Verify Only (faster, no payload decode)

```python
from django_matt._accel import jwt_verify_rust

is_valid = jwt_verify_rust(
    token="eyJhbGci...",
    secret=b"your-secret-key",
    algorithm="HS256",
)
# → True/False
```

## Where It's Used

`django_matt/auth/jwt_builtin.py` — the internal JWT implementation:

- `encode_jwt()` uses Rust for HMAC algorithms, Python for RSA/EC
- `decode_jwt()` uses Rust for HMAC algorithms, Python for RSA/EC
- The switch is transparent — the `jwt_builtin.py` module checks `HAS_RUST` and delegates automatically

RSA and EC algorithms (RS256, ES256, etc.) are not implemented in Rust because the `cryptography` package that handles them is already Rust-based internally. There's no speedup to be gained.

## Performance

| Operation | Python | Rust | Speedup |
|-----------|--------|------|---------|
| JWT encode (HS256) | ~2.9μs | ~1.9μs | **1.5x** |
| JWT decode+verify (HS256) | ~2.9μs | ~2.0μs | **1.5x** |
| JWT verify only (HS256) | ~2.0μs | ~1.3μs | **1.5x** |

The 1.5x speedup is modest because Python's HMAC is already C-optimized. The real win is GIL release — in a server handling 1000 concurrent requests, JWT verification doesn't block other coroutines.

## Supported Algorithms

| Algorithm | Rust | Python Fallback |
|-----------|------|-----------------|
| HS256 | Yes | Yes |
| HS384 | Yes | Yes |
| HS512 | Yes | Yes |
| RS256/384/512 | No (deferred) | Yes (via `cryptography`) |
| ES256/384/512 | No (deferred) | Yes (via `cryptography`) |

## Error Handling

Rust JWT errors are mapped to Python `ValueError` with descriptive messages:

- `"Invalid JWT format: expected 3 parts"` — malformed token
- `"Token algorithm does not match expected: HS256"` — header says different algorithm
- `"Signature verification failed"` — tampered token or wrong secret
- `"Token has expired"` — `exp` claim is in the past
- `"Rust JWT only supports HMAC algorithms"` — tried RS/EC with Rust

These map to `JWTError` subclasses in `django_matt/auth/jwt_builtin.py`.

## Rust Implementation

Source: `rust/src/jwt.rs`

- **base64url_encode/decode** — URL-safe base64 without padding via the `base64` crate
- **hmac_sign** — HMAC-SHA256/384/512 via the `hmac` + `sha2` crates
- **constant_time_eq** — via the `subtle` crate's `ConstantTimeEq`
- **jwt_encode** — builds header, encodes payload, signs, returns complete JWT string
- **jwt_decode** — splits token, verifies signature, decodes payload via `orjson.loads()`, optionally checks expiration
- **jwt_verify** — signature check only (no payload decode)
- **7 Rust unit tests** covering base64 roundtrip, HMAC algorithms, constant-time comparison

## Future Enhancements

- **JWK support** — parse JSON Web Keys for key rotation without restart
- **Token caching** — LRU cache of recently verified tokens (trade memory for CPU on repeated tokens)
- **Batch verification** — verify multiple tokens in parallel using Rayon (useful for WebSocket connection bursts)

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::time::{SystemTime, UNIX_EPOCH};

/// Base64url encode without padding.
fn base64url_encode(data: &[u8]) -> String {
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine;
    URL_SAFE_NO_PAD.encode(data)
}

/// Base64url decode (handles missing padding).
fn base64url_decode(data: &str) -> Result<Vec<u8>, String> {
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine;
    URL_SAFE_NO_PAD
        .decode(data)
        .map_err(|e| format!("Invalid base64url: {e}"))
}

/// HMAC-SHA signing.
fn hmac_sign(data: &[u8], key: &[u8], algorithm: &str) -> Result<Vec<u8>, String> {
    use hmac::{Hmac, Mac};
    use sha2::{Sha256, Sha384, Sha512};

    match algorithm {
        "HS256" => {
            let mut mac =
                Hmac::<Sha256>::new_from_slice(key).map_err(|e| format!("HMAC error: {e}"))?;
            mac.update(data);
            Ok(mac.finalize().into_bytes().to_vec())
        }
        "HS384" => {
            let mut mac =
                Hmac::<Sha384>::new_from_slice(key).map_err(|e| format!("HMAC error: {e}"))?;
            mac.update(data);
            Ok(mac.finalize().into_bytes().to_vec())
        }
        "HS512" => {
            let mut mac =
                Hmac::<Sha512>::new_from_slice(key).map_err(|e| format!("HMAC error: {e}"))?;
            mac.update(data);
            Ok(mac.finalize().into_bytes().to_vec())
        }
        _ => Err(format!("Unsupported HMAC algorithm: {algorithm}")),
    }
}

/// RSA PKCS#1 v1.5 signing.
fn rsa_sign(data: &[u8], private_key_pem: &str, algorithm: &str) -> Result<Vec<u8>, String> {
    use pkcs8::DecodePrivateKey;
    use rsa::pkcs1v15::SigningKey;
    use rsa::RsaPrivateKey;
    use sha2::{Sha256, Sha384, Sha512};
    use signature::{SignatureEncoding, Signer};

    let private_key = RsaPrivateKey::from_pkcs8_pem(private_key_pem)
        .map_err(|e| format!("Failed to parse RSA private key: {e}"))?;

    let sig_bytes = match algorithm {
        "RS256" => {
            let signing_key = SigningKey::<Sha256>::new(private_key);
            let sig = signing_key.sign(data);
            sig.to_vec()
        }
        "RS384" => {
            let signing_key = SigningKey::<Sha384>::new(private_key);
            let sig = signing_key.sign(data);
            sig.to_vec()
        }
        "RS512" => {
            let signing_key = SigningKey::<Sha512>::new(private_key);
            let sig = signing_key.sign(data);
            sig.to_vec()
        }
        _ => return Err(format!("Unsupported RSA algorithm: {algorithm}")),
    };

    Ok(sig_bytes)
}

/// RSA PKCS#1 v1.5 verification.
fn rsa_verify(
    data: &[u8],
    sig_bytes: &[u8],
    public_key_pem: &str,
    algorithm: &str,
) -> Result<bool, String> {
    use pkcs8::DecodePublicKey;
    use rsa::pkcs1v15::{Signature, VerifyingKey};
    use rsa::RsaPublicKey;
    use sha2::{Sha256, Sha384, Sha512};
    use signature::Verifier;

    let public_key = RsaPublicKey::from_public_key_pem(public_key_pem)
        .map_err(|e| format!("Failed to parse RSA public key: {e}"))?;

    let signature =
        Signature::try_from(sig_bytes).map_err(|e| format!("Invalid RSA signature: {e}"))?;

    let valid = match algorithm {
        "RS256" => {
            let verifying_key = VerifyingKey::<Sha256>::new(public_key);
            verifying_key.verify(data, &signature).is_ok()
        }
        "RS384" => {
            let verifying_key = VerifyingKey::<Sha384>::new(public_key);
            verifying_key.verify(data, &signature).is_ok()
        }
        "RS512" => {
            let verifying_key = VerifyingKey::<Sha512>::new(public_key);
            verifying_key.verify(data, &signature).is_ok()
        }
        _ => return Err(format!("Unsupported RSA algorithm: {algorithm}")),
    };

    Ok(valid)
}

/// EC (ECDSA) signing — returns raw (r || s) format as required by JWT spec.
fn ec_sign(data: &[u8], private_key_pem: &str, algorithm: &str) -> Result<Vec<u8>, String> {
    match algorithm {
        "ES256" => {
            use ecdsa::SigningKey;
            use p256::NistP256;
            use pkcs8::DecodePrivateKey;
            use signature::Signer;

            let signing_key = SigningKey::<NistP256>::from_pkcs8_pem(private_key_pem)
                .map_err(|e| format!("Failed to parse EC P-256 private key: {e}"))?;

            let sig: ecdsa::Signature<NistP256> = signing_key.sign(data);
            Ok(sig.to_bytes().to_vec())
        }
        "ES384" => {
            use ecdsa::SigningKey;
            use p384::NistP384;
            use pkcs8::DecodePrivateKey;
            use signature::Signer;

            let signing_key = SigningKey::<NistP384>::from_pkcs8_pem(private_key_pem)
                .map_err(|e| format!("Failed to parse EC P-384 private key: {e}"))?;

            let sig: ecdsa::Signature<NistP384> = signing_key.sign(data);
            Ok(sig.to_bytes().to_vec())
        }
        _ => Err(format!("Unsupported EC algorithm: {algorithm}")),
    }
}

/// EC (ECDSA) verification — expects raw (r || s) format.
fn ec_verify(
    data: &[u8],
    sig_bytes: &[u8],
    public_key_pem: &str,
    algorithm: &str,
) -> Result<bool, String> {
    match algorithm {
        "ES256" => {
            use ecdsa::{Signature, VerifyingKey};
            use p256::NistP256;
            use pkcs8::DecodePublicKey;
            use signature::Verifier;

            let verifying_key = VerifyingKey::<NistP256>::from_public_key_pem(public_key_pem)
                .map_err(|e| format!("Failed to parse EC P-256 public key: {e}"))?;

            let signature = Signature::<NistP256>::from_slice(sig_bytes)
                .map_err(|e| format!("Invalid EC signature: {e}"))?;

            Ok(verifying_key.verify(data, &signature).is_ok())
        }
        "ES384" => {
            use ecdsa::{Signature, VerifyingKey};
            use p384::NistP384;
            use pkcs8::DecodePublicKey;
            use signature::Verifier;

            let verifying_key = VerifyingKey::<NistP384>::from_public_key_pem(public_key_pem)
                .map_err(|e| format!("Failed to parse EC P-384 public key: {e}"))?;

            let signature = Signature::<NistP384>::from_slice(sig_bytes)
                .map_err(|e| format!("Invalid EC signature: {e}"))?;

            Ok(verifying_key.verify(data, &signature).is_ok())
        }
        _ => Err(format!("Unsupported EC algorithm: {algorithm}")),
    }
}

/// Constant-time comparison of two byte slices.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    use subtle::ConstantTimeEq;
    a.ct_eq(b).into()
}

/// Determine signing category from algorithm name.
fn algorithm_category(algorithm: &str) -> Result<&'static str, String> {
    match algorithm {
        "HS256" | "HS384" | "HS512" => Ok("hmac"),
        "RS256" | "RS384" | "RS512" => Ok("rsa"),
        "ES256" | "ES384" => Ok("ec"),
        _ => Err(format!("Unsupported algorithm: {algorithm}")),
    }
}

/// Encode a JWT token.
///
/// Supports HMAC (HS256/HS384/HS512), RSA (RS256/RS384/RS512), and EC (ES256/ES384).
///
/// For HMAC, `secret` is the shared key bytes.
/// For RSA/EC, `secret` is the PEM-encoded private key bytes.
#[pyfunction]
#[pyo3(signature = (payload_json, secret, algorithm = "HS256"))]
fn jwt_encode(payload_json: &[u8], secret: &[u8], algorithm: &str) -> PyResult<String> {
    let category = algorithm_category(algorithm).map_err(PyValueError::new_err)?;

    // Build header
    let header_json = format!(r#"{{"alg":"{algorithm}","typ":"JWT"}}"#);
    let header_b64 = base64url_encode(header_json.as_bytes());
    let payload_b64 = base64url_encode(payload_json);

    // Sign
    let signing_input = format!("{header_b64}.{payload_b64}");
    let signing_data = signing_input.as_bytes();

    let signature = match category {
        "hmac" => hmac_sign(signing_data, secret, algorithm),
        "rsa" => {
            let pem = std::str::from_utf8(secret)
                .map_err(|_| PyValueError::new_err("RSA private key must be valid UTF-8 PEM"))?;
            rsa_sign(signing_data, pem, algorithm)
        }
        "ec" => {
            let pem = std::str::from_utf8(secret)
                .map_err(|_| PyValueError::new_err("EC private key must be valid UTF-8 PEM"))?;
            ec_sign(signing_data, pem, algorithm)
        }
        _ => unreachable!(),
    }
    .map_err(PyRuntimeError::new_err)?;

    let signature_b64 = base64url_encode(&signature);
    Ok(format!("{signing_input}.{signature_b64}"))
}

/// Decode and verify a JWT token.
///
/// For HMAC, `secret` is the shared key bytes.
/// For RSA/EC, `secret` is the PEM-encoded public key bytes.
#[pyfunction]
#[pyo3(signature = (token, secret, algorithm = "HS256", verify_exp = true, leeway = 0))]
fn jwt_decode<'py>(
    py: Python<'py>,
    token: &str,
    secret: &[u8],
    algorithm: &str,
    verify_exp: bool,
    leeway: i64,
) -> PyResult<Bound<'py, PyDict>> {
    let category = algorithm_category(algorithm).map_err(PyValueError::new_err)?;

    // Split token
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return Err(PyValueError::new_err("Invalid JWT format: expected 3 parts"));
    }

    let header_b64 = parts[0];
    let payload_b64 = parts[1];
    let signature_b64 = parts[2];

    // Verify header algorithm matches
    let header_bytes = base64url_decode(header_b64)
        .map_err(|e| PyValueError::new_err(format!("Invalid header: {e}")))?;
    let header_str = std::str::from_utf8(&header_bytes)
        .map_err(|_| PyValueError::new_err("Invalid header UTF-8"))?;

    if !header_str.contains(algorithm) {
        return Err(PyValueError::new_err(format!(
            "Token algorithm does not match expected: {algorithm}"
        )));
    }

    // Verify signature
    let signing_input = format!("{header_b64}.{payload_b64}");
    let actual_signature = base64url_decode(signature_b64)
        .map_err(|e| PyValueError::new_err(format!("Invalid signature: {e}")))?;

    let valid = match category {
        "hmac" => {
            let expected_signature = hmac_sign(signing_input.as_bytes(), secret, algorithm)
                .map_err(PyRuntimeError::new_err)?;
            constant_time_eq(&expected_signature, &actual_signature)
        }
        "rsa" => {
            let pem = std::str::from_utf8(secret)
                .map_err(|_| PyValueError::new_err("RSA public key must be valid UTF-8 PEM"))?;
            rsa_verify(signing_input.as_bytes(), &actual_signature, pem, algorithm)
                .map_err(PyRuntimeError::new_err)?
        }
        "ec" => {
            let pem = std::str::from_utf8(secret)
                .map_err(|_| PyValueError::new_err("EC public key must be valid UTF-8 PEM"))?;
            ec_verify(signing_input.as_bytes(), &actual_signature, pem, algorithm)
                .map_err(PyRuntimeError::new_err)?
        }
        _ => unreachable!(),
    };

    if !valid {
        return Err(PyValueError::new_err("Signature verification failed"));
    }

    // Decode payload
    let payload_bytes = base64url_decode(payload_b64)
        .map_err(|e| PyValueError::new_err(format!("Invalid payload: {e}")))?;

    // Parse JSON payload into Python dict
    let orjson = py.import("orjson")?;
    let payload_dict = orjson
        .call_method1("loads", (payload_bytes.as_slice(),))?
        .downcast_into::<PyDict>()?;

    // Verify expiration if requested
    if verify_exp {
        if let Ok(Some(exp_obj)) = payload_dict.get_item("exp") {
            let exp: i64 = exp_obj
                .extract()
                .map_err(|_| PyValueError::new_err("Invalid 'exp' claim: not a number"))?;
            let now = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs() as i64;
            if now > exp + leeway {
                return Err(PyValueError::new_err("Token has expired"));
            }
        }
    }

    Ok(payload_dict)
}

/// Verify a JWT signature without decoding the payload.
///
/// Faster than full decode when you only need to check validity.
#[pyfunction]
#[pyo3(signature = (token, secret, algorithm = "HS256"))]
fn jwt_verify(token: &str, secret: &[u8], algorithm: &str) -> PyResult<bool> {
    let category = match algorithm_category(algorithm) {
        Ok(c) => c,
        Err(_) => return Ok(false),
    };

    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return Ok(false);
    }

    let signing_input = format!("{}.{}", parts[0], parts[1]);
    let actual = match base64url_decode(parts[2]) {
        Ok(sig) => sig,
        Err(_) => return Ok(false),
    };

    let valid = match category {
        "hmac" => {
            let expected = match hmac_sign(signing_input.as_bytes(), secret, algorithm) {
                Ok(sig) => sig,
                Err(_) => return Ok(false),
            };
            constant_time_eq(&expected, &actual)
        }
        "rsa" => {
            let pem = match std::str::from_utf8(secret) {
                Ok(p) => p,
                Err(_) => return Ok(false),
            };
            match rsa_verify(signing_input.as_bytes(), &actual, pem, algorithm) {
                Ok(v) => v,
                Err(_) => false,
            }
        }
        "ec" => {
            let pem = match std::str::from_utf8(secret) {
                Ok(p) => p,
                Err(_) => return Ok(false),
            };
            match ec_verify(signing_input.as_bytes(), &actual, pem, algorithm) {
                Ok(v) => v,
                Err(_) => false,
            }
        }
        _ => false,
    };

    Ok(valid)
}

/// Register JWT functions in the module.
pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_function(wrap_pyfunction!(jwt_encode, parent)?)?;
    parent.add_function(wrap_pyfunction!(jwt_decode, parent)?)?;
    parent.add_function(wrap_pyfunction!(jwt_verify, parent)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_base64url_roundtrip() {
        let data = b"hello world";
        let encoded = base64url_encode(data);
        let decoded = base64url_decode(&encoded).unwrap();
        assert_eq!(decoded, data);
    }

    #[test]
    fn test_hmac_sign_hs256() {
        let sig = hmac_sign(b"test data", b"secret", "HS256").unwrap();
        assert_eq!(sig.len(), 32); // SHA-256 = 32 bytes
    }

    #[test]
    fn test_hmac_sign_hs384() {
        let sig = hmac_sign(b"test data", b"secret", "HS384").unwrap();
        assert_eq!(sig.len(), 48); // SHA-384 = 48 bytes
    }

    #[test]
    fn test_hmac_sign_hs512() {
        let sig = hmac_sign(b"test data", b"secret", "HS512").unwrap();
        assert_eq!(sig.len(), 64); // SHA-512 = 64 bytes
    }

    #[test]
    fn test_hmac_unsupported() {
        assert!(hmac_sign(b"data", b"key", "RS256").is_err());
    }

    #[test]
    fn test_constant_time_eq() {
        assert!(constant_time_eq(b"hello", b"hello"));
        assert!(!constant_time_eq(b"hello", b"world"));
        assert!(!constant_time_eq(b"hello", b"hell"));
    }

    #[test]
    fn test_algorithm_category() {
        assert_eq!(algorithm_category("HS256").unwrap(), "hmac");
        assert_eq!(algorithm_category("RS256").unwrap(), "rsa");
        assert_eq!(algorithm_category("ES256").unwrap(), "ec");
        assert!(algorithm_category("XX256").is_err());
    }
}

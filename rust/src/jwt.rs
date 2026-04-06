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

/// Constant-time comparison of two byte slices.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    use subtle::ConstantTimeEq;
    a.ct_eq(b).into()
}

/// Encode a JWT token using HMAC algorithms (HS256/HS384/HS512).
///
/// Takes a JSON payload as bytes (pre-serialized with orjson on Python side),
/// signs it, and returns the complete JWT string.
#[pyfunction]
#[pyo3(signature = (payload_json, secret, algorithm = "HS256"))]
fn jwt_encode(payload_json: &[u8], secret: &[u8], algorithm: &str) -> PyResult<String> {
    // Validate algorithm
    if !matches!(algorithm, "HS256" | "HS384" | "HS512") {
        return Err(PyValueError::new_err(format!(
            "Rust JWT only supports HMAC algorithms (HS256/HS384/HS512), got: {algorithm}"
        )));
    }

    // Build header
    let header_json = format!(r#"{{"alg":"{algorithm}","typ":"JWT"}}"#);
    let header_b64 = base64url_encode(header_json.as_bytes());
    let payload_b64 = base64url_encode(payload_json);

    // Sign
    let signing_input = format!("{header_b64}.{payload_b64}");
    let signature = hmac_sign(signing_input.as_bytes(), secret, algorithm)
        .map_err(PyRuntimeError::new_err)?;
    let signature_b64 = base64url_encode(&signature);

    Ok(format!("{signing_input}.{signature_b64}"))
}

/// Decode and verify a JWT token using HMAC algorithms.
///
/// Returns the raw payload as bytes (to be deserialized with orjson on Python side).
/// Performs signature verification and optionally checks expiration.
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
    // Validate algorithm
    if !matches!(algorithm, "HS256" | "HS384" | "HS512") {
        return Err(PyValueError::new_err(format!(
            "Rust JWT only supports HMAC algorithms, got: {algorithm}"
        )));
    }

    // Split token
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return Err(PyValueError::new_err("Invalid JWT format: expected 3 parts"));
    }

    let header_b64 = parts[0];
    let payload_b64 = parts[1];
    let signature_b64 = parts[2];

    // Verify header algorithm matches
    let header_bytes =
        base64url_decode(header_b64).map_err(|e| PyValueError::new_err(format!("Invalid header: {e}")))?;
    let header_str =
        std::str::from_utf8(&header_bytes).map_err(|_| PyValueError::new_err("Invalid header UTF-8"))?;

    // Quick check: does the header contain the expected algorithm?
    if !header_str.contains(algorithm) {
        return Err(PyValueError::new_err(format!(
            "Token algorithm does not match expected: {algorithm}"
        )));
    }

    // Verify signature
    let signing_input = format!("{header_b64}.{payload_b64}");
    let expected_signature = hmac_sign(signing_input.as_bytes(), secret, algorithm)
        .map_err(PyRuntimeError::new_err)?;
    let actual_signature = base64url_decode(signature_b64)
        .map_err(|e| PyValueError::new_err(format!("Invalid signature: {e}")))?;

    if !constant_time_eq(&expected_signature, &actual_signature) {
        return Err(PyValueError::new_err("Signature verification failed"));
    }

    // Decode payload
    let payload_bytes = base64url_decode(payload_b64)
        .map_err(|e| PyValueError::new_err(format!("Invalid payload: {e}")))?;

    // Parse JSON payload into Python dict
    let payload_str =
        std::str::from_utf8(&payload_bytes).map_err(|_| PyValueError::new_err("Invalid payload UTF-8"))?;

    // Use Python's json/orjson to parse (since we need a Python dict)
    let orjson = py.import("orjson")?;
    let payload_dict = orjson
        .call_method1("loads", (payload_bytes.as_slice(),))?
        .downcast_into::<PyDict>()?;

    // Verify expiration if requested
    if verify_exp {
        if let Ok(Some(exp_obj)) = payload_dict.get_item("exp") {
            let exp: i64 = exp_obj.extract().map_err(|_| {
                PyValueError::new_err("Invalid 'exp' claim: not a number")
            })?;
            let now = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs() as i64;
            if now > exp + leeway {
                return Err(PyValueError::new_err("Token has expired"));
            }
        }
    }

    // Suppress unused variable warning
    let _ = payload_str;

    Ok(payload_dict)
}

/// Verify a JWT signature without decoding the payload.
///
/// Faster than full decode when you only need to check validity.
#[pyfunction]
#[pyo3(signature = (token, secret, algorithm = "HS256"))]
fn jwt_verify(token: &str, secret: &[u8], algorithm: &str) -> PyResult<bool> {
    if !matches!(algorithm, "HS256" | "HS384" | "HS512") {
        return Ok(false);
    }

    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return Ok(false);
    }

    let signing_input = format!("{}.{}", parts[0], parts[1]);
    let expected = match hmac_sign(signing_input.as_bytes(), secret, algorithm) {
        Ok(sig) => sig,
        Err(_) => return Ok(false),
    };
    let actual = match base64url_decode(parts[2]) {
        Ok(sig) => sig,
        Err(_) => return Ok(false),
    };

    Ok(constant_time_eq(&expected, &actual))
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
}

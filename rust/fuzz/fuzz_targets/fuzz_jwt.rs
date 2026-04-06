#![no_main]
use libfuzzer_sys::fuzz_target;

// ---- Duplicated pure-Rust logic from src/jwt.rs (no PyO3) ----

fn base64url_encode(data: &[u8]) -> String {
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine;
    URL_SAFE_NO_PAD.encode(data)
}

fn base64url_decode(data: &str) -> Result<Vec<u8>, String> {
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine;
    URL_SAFE_NO_PAD
        .decode(data)
        .map_err(|e| format!("Invalid base64url: {e}"))
}

fn hmac_sign(data: &[u8], key: &[u8], algorithm: &str) -> Result<Vec<u8>, String> {
    use hmac::{Hmac, Mac};
    use sha2::{Sha256, Sha384, Sha512};
    match algorithm {
        "HS256" => {
            let mut mac = Hmac::<Sha256>::new_from_slice(key).map_err(|e| format!("{e}"))?;
            mac.update(data);
            Ok(mac.finalize().into_bytes().to_vec())
        }
        "HS384" => {
            let mut mac = Hmac::<Sha384>::new_from_slice(key).map_err(|e| format!("{e}"))?;
            mac.update(data);
            Ok(mac.finalize().into_bytes().to_vec())
        }
        "HS512" => {
            let mut mac = Hmac::<Sha512>::new_from_slice(key).map_err(|e| format!("{e}"))?;
            mac.update(data);
            Ok(mac.finalize().into_bytes().to_vec())
        }
        _ => Err(format!("Unsupported: {algorithm}")),
    }
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    use subtle::ConstantTimeEq;
    a.ct_eq(b).into()
}

fn jwt_verify_pure(token: &str, secret: &[u8], algorithm: &str) -> bool {
    if !matches!(algorithm, "HS256" | "HS384" | "HS512") {
        return false;
    }
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return false;
    }
    let signing_input = format!("{}.{}", parts[0], parts[1]);
    let expected = match hmac_sign(signing_input.as_bytes(), secret, algorithm) {
        Ok(sig) => sig,
        Err(_) => return false,
    };
    let actual = match base64url_decode(parts[2]) {
        Ok(sig) => sig,
        Err(_) => return false,
    };
    constant_time_eq(&expected, &actual)
}

fn jwt_encode_pure(payload: &[u8], secret: &[u8], algorithm: &str) -> Option<String> {
    if !matches!(algorithm, "HS256" | "HS384" | "HS512") {
        return None;
    }
    let header_json = format!(r#"{{"alg":"{algorithm}","typ":"JWT"}}"#);
    let header_b64 = base64url_encode(header_json.as_bytes());
    let payload_b64 = base64url_encode(payload);
    let signing_input = format!("{header_b64}.{payload_b64}");
    let signature = hmac_sign(signing_input.as_bytes(), secret, algorithm).ok()?;
    let signature_b64 = base64url_encode(&signature);
    Some(format!("{signing_input}.{signature_b64}"))
}

// ---- Fuzz target ----

fuzz_target!(|data: &[u8]| {
    if data.len() > 4096 {
        return;
    }

    let secret = b"fuzz-secret-key-32-bytes-long!!!";

    // Fuzz base64url roundtrip
    let encoded = base64url_encode(data);
    let decoded = base64url_decode(&encoded).unwrap();
    assert_eq!(decoded, data);

    // Fuzz base64url decode of arbitrary input
    if let Ok(input) = std::str::from_utf8(data) {
        let _ = base64url_decode(input);

        // Fuzz JWT verify on arbitrary token strings
        let _ = jwt_verify_pure(input, secret, "HS256");

        // Fuzz JWT encode with arbitrary payload
        if let Some(token) = jwt_encode_pure(data, secret, "HS256") {
            // Verify roundtrip: encode then verify
            assert!(jwt_verify_pure(&token, secret, "HS256"));
            // Wrong secret should fail
            assert!(!jwt_verify_pure(&token, b"wrong-secret-key-32-bytes-long!!", "HS256"));
        }
    }

    // Fuzz HMAC signing
    for alg in &["HS256", "HS384", "HS512"] {
        let _ = hmac_sign(data, secret, alg);
    }
});

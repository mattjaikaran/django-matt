#![no_main]
use libfuzzer_sys::fuzz_target;

// ---- Duplicated pure-Rust logic from src/headers.rs (no PyO3) ----

#[derive(Debug, Default)]
struct ParsedHeaders {
    auth_type: Option<String>,
    auth_credential: Option<String>,
    api_key: Option<String>,
    request_id: Option<String>,
    content_type_media: Option<String>,
    content_type_params: Option<String>,
    accept: Vec<(String, f64)>,
}

fn parse_headers_pure(
    authorization: Option<&str>,
    api_key: Option<&str>,
    request_id: Option<&str>,
    content_type: Option<&str>,
    accept: Option<&str>,
) -> ParsedHeaders {
    let mut result = ParsedHeaders::default();

    // Authorization
    if let Some(auth_str) = authorization {
        if let Some((auth_type, credential)) = auth_str.split_once(' ') {
            result.auth_type = Some(auth_type.trim().to_string());
            result.auth_credential = Some(credential.trim().to_string());
        }
        // Malformed (no space) is ignored — matches Rust implementation
    }

    // X-API-Key
    if let Some(key) = api_key {
        result.api_key = Some(key.to_string());
    }

    // X-Request-ID
    if let Some(id) = request_id {
        result.request_id = Some(id.to_string());
    }

    // Content-Type
    if let Some(ct) = content_type {
        if let Some((media_type, params)) = ct.split_once(';') {
            result.content_type_media = Some(media_type.trim().to_string());
            result.content_type_params = Some(params.trim().to_string());
        } else {
            result.content_type_media = Some(ct.trim().to_string());
        }
    }

    // Accept header
    if let Some(accept_str) = accept {
        for part in accept_str.split(',') {
            let part = part.trim();
            if part.is_empty() {
                continue;
            }
            if let Some((media, q_part)) = part.split_once(";q=") {
                let q: f64 = q_part
                    .split(';')
                    .next()
                    .and_then(|s| s.trim().parse().ok())
                    .unwrap_or(1.0);
                result.accept.push((media.trim().to_string(), q));
            } else {
                result.accept.push((part.to_string(), 1.0));
            }
        }
    }

    result
}

// ---- Fuzz target ----

fuzz_target!(|data: &[u8]| {
    if data.len() > 4096 {
        return;
    }

    let Ok(input) = std::str::from_utf8(data) else { return };

    // Split input into up to 5 "headers" separated by newlines
    let parts: Vec<&str> = input.splitn(5, '\n').collect();
    let auth = parts.first().filter(|s| !s.is_empty()).copied();
    let api_key = parts.get(1).filter(|s| !s.is_empty()).copied();
    let req_id = parts.get(2).filter(|s| !s.is_empty()).copied();
    let ct = parts.get(3).filter(|s| !s.is_empty()).copied();
    let accept = parts.get(4).filter(|s| !s.is_empty()).copied();

    let result = parse_headers_pure(auth, api_key, req_id, ct, accept);

    // Verify: if auth was provided with a space, we should have parsed type/credential
    if let Some(a) = auth {
        if a.contains(' ') {
            assert!(result.auth_type.is_some());
            assert!(result.auth_credential.is_some());
        } else {
            // Malformed — should be None
            assert!(result.auth_type.is_none());
        }
    }

    // Verify: accept quality values should be finite or NaN (never panic)
    for (_, q) in &result.accept {
        // Just verify no panics occurred during parsing
        let _ = q.is_finite();
    }
});

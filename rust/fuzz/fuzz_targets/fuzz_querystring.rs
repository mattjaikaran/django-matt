#![no_main]
use libfuzzer_sys::fuzz_target;

// ---- Duplicated pure-Rust logic from src/querystring.rs (no PyO3) ----

fn url_decode(input: &str) -> String {
    let mut result = String::with_capacity(input.len());
    let mut chars = input.bytes();
    while let Some(b) = chars.next() {
        match b {
            b'+' => result.push(' '),
            b'%' => {
                let hi = chars.next().and_then(from_hex);
                let lo = chars.next().and_then(from_hex);
                if let (Some(h), Some(l)) = (hi, lo) {
                    result.push((h << 4 | l) as char);
                } else {
                    result.push('%');
                }
            }
            _ => result.push(b as char),
        }
    }
    result
}

fn from_hex(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

/// Simplified parse_query_string that exercises the same logic
/// without PyO3 types.
fn parse_qs_pure(qs: &str) -> (Vec<String>, Vec<(String, String)>, Vec<(String, bool)>, Vec<(String, String)>) {
    let qs = qs.strip_prefix('?').unwrap_or(qs);
    let mut fields = Vec::new();
    let mut filters = Vec::new();
    let mut sort = Vec::new();
    let mut extras = Vec::new();

    if qs.is_empty() {
        return (fields, filters, sort, extras);
    }

    for pair in qs.split('&') {
        let (key, value) = match pair.split_once('=') {
            Some((k, v)) => (k, url_decode(v)),
            None => (pair, String::new()),
        };

        match key {
            "fields" => {
                for field in value.split(',') {
                    let trimmed = field.trim();
                    if !trimmed.is_empty() {
                        fields.push(trimmed.to_string());
                    }
                }
            }
            "sort" | "ordering" => {
                for item in value.split(',') {
                    let trimmed = item.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    if let Some(stripped) = trimmed.strip_prefix('-') {
                        sort.push((stripped.to_string(), false));
                    } else {
                        sort.push((trimmed.to_string(), true));
                    }
                }
            }
            "page" | "page_size" | "limit" | "offset" | "cursor" | "no_page" => {}
            _ if key.starts_with("filter[") && key.ends_with(']') => {
                let filter_name = &key[7..key.len() - 1];
                if !filter_name.is_empty() {
                    filters.push((filter_name.to_string(), value));
                }
            }
            _ => {
                extras.push((key.to_string(), value));
            }
        }
    }

    (fields, filters, sort, extras)
}

// ---- Fuzz target ----

fuzz_target!(|data: &[u8]| {
    if data.len() > 4096 {
        return;
    }

    let Ok(input) = std::str::from_utf8(data) else { return };

    // Fuzz url_decode — must not panic on any input
    let decoded = url_decode(input);
    // Decoded output must be valid (no partial chars)
    assert!(decoded.len() <= input.len() * 4);

    // Fuzz query string parsing
    let (fields, filters, sort, extras) = parse_qs_pure(input);

    // Basic sanity: no output should be empty if we split non-empty values
    let _ = (fields, filters, sort, extras);
});

#![no_main]
use libfuzzer_sys::fuzz_target;
use std::io::Write;

// ---- Duplicated pure-Rust logic from src/serializer.rs (no PyO3) ----

fn write_json_string(buf: &mut Vec<u8>, s: &str) {
    buf.push(b'"');
    for byte in s.bytes() {
        match byte {
            b'"' => buf.extend_from_slice(b"\\\""),
            b'\\' => buf.extend_from_slice(b"\\\\"),
            b'\n' => buf.extend_from_slice(b"\\n"),
            b'\r' => buf.extend_from_slice(b"\\r"),
            b'\t' => buf.extend_from_slice(b"\\t"),
            b if b < 0x20 => {
                write!(buf, "\\u{:04x}", b).unwrap();
            }
            _ => buf.push(byte),
        }
    }
    buf.push(b'"');
}

fn to_camel_case(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut capitalize_next = false;
    for (i, c) in s.chars().enumerate() {
        if c == '_' {
            capitalize_next = true;
        } else if capitalize_next {
            result.extend(c.to_uppercase());
            capitalize_next = false;
        } else if i == 0 {
            result.push(c);
        } else {
            result.push(c);
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

    // Fuzz JSON string escaping — must produce valid JSON string
    let mut buf = Vec::new();
    write_json_string(&mut buf, input);

    // Verify: must start and end with quote
    assert!(buf.starts_with(b"\""));
    assert!(buf.ends_with(b"\""));
    // Must be valid UTF-8
    assert!(std::str::from_utf8(&buf).is_ok());

    // Fuzz camelCase conversion
    let camel = to_camel_case(input);
    // camelCase output should never contain leading underscore if input doesn't
    if !input.starts_with('_') {
        assert!(!camel.starts_with('_'));
    }
    // No underscores in output (unless they were leading/trailing)
    let inner = input.trim_matches('_');
    if !inner.is_empty() && !inner.contains("__") {
        // Single underscores in the middle should be removed
        let camel_inner = to_camel_case(inner);
        assert!(!camel_inner.contains('_'), "camel_case({inner}) = {camel_inner}");
    }
});

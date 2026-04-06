use pyo3::prelude::*;
use pyo3::types::PyDict;

/// Parse common HTTP headers into a structured dict.
///
/// Extracts and pre-parses headers that django-matt middleware needs:
/// - Authorization (type + credential)
/// - Accept (media types with quality values)
/// - Content-Type (media type + params)
/// - X-Request-ID
/// - X-API-Key
#[pyfunction]
fn parse_headers<'py>(py: Python<'py>, meta: &Bound<'py, PyDict>) -> PyResult<Bound<'py, PyDict>> {
    let result = PyDict::new(py);

    // Authorization: <type> <credential> (e.g. "Bearer <token>")
    // Malformed headers without a space separator are ignored.
    if let Ok(Some(auth)) = meta.get_item("HTTP_AUTHORIZATION") {
        let auth_str: &str = auth.extract()?;
        if let Some((auth_type, credential)) = auth_str.split_once(' ') {
            let auth_dict = PyDict::new(py);
            auth_dict.set_item("type", auth_type.trim())?;
            auth_dict.set_item("credential", credential.trim())?;
            result.set_item("authorization", auth_dict)?;
        }
    }

    // X-API-Key
    if let Ok(Some(api_key)) = meta.get_item("HTTP_X_API_KEY") {
        let key_str: &str = api_key.extract()?;
        result.set_item("api_key", key_str)?;
    }

    // X-Request-ID
    if let Ok(Some(req_id)) = meta.get_item("HTTP_X_REQUEST_ID") {
        let id_str: &str = req_id.extract()?;
        result.set_item("request_id", id_str)?;
    }

    // Content-Type
    if let Ok(Some(ct)) = meta.get_item("CONTENT_TYPE") {
        let ct_str: &str = ct.extract()?;
        let ct_dict = PyDict::new(py);
        if let Some((media_type, params)) = ct_str.split_once(';') {
            ct_dict.set_item("media_type", media_type.trim())?;
            ct_dict.set_item("params", params.trim())?;
        } else {
            ct_dict.set_item("media_type", ct_str.trim())?;
        }
        result.set_item("content_type", ct_dict)?;
    }

    // Accept header — parse media types with quality values
    if let Ok(Some(accept)) = meta.get_item("HTTP_ACCEPT") {
        let accept_str: &str = accept.extract()?;
        let accepts = PyDict::new(py);
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
                accepts.set_item(media.trim(), q)?;
            } else {
                accepts.set_item(part, 1.0)?;
            }
        }
        result.set_item("accept", accepts)?;
    }

    Ok(result)
}

/// Register header parsing functions.
pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_function(wrap_pyfunction!(parse_headers, parent)?)?;
    Ok(())
}

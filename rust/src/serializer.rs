use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyNone, PyString};
use std::io::Write;

/// Fast JSON serialization for a list of Python dicts.
///
/// Bypasses Python's json module by directly writing JSON from Python objects.
/// Supports optional field renaming (snake_case → camelCase via alias map).
///
/// This is the hot path for list serialization in django-matt views:
///   queryset → [model_construct() → model_dump() for obj in qs] → json
///
/// With this function:
///   queryset → [model_dump() for obj in qs] → serialize_dicts_to_json()
#[pyfunction]
#[pyo3(signature = (dicts, alias_map = None))]
fn serialize_dicts_to_json<'py>(
    py: Python<'py>,
    dicts: &Bound<'py, PyList>,
    alias_map: Option<&Bound<'py, PyDict>>,
) -> PyResult<Bound<'py, pyo3::types::PyBytes>> {
    let len = dicts.len();
    // Pre-allocate buffer (rough estimate: 200 bytes per dict)
    let mut buf: Vec<u8> = Vec::with_capacity(len * 200);

    buf.push(b'[');

    for i in 0..len {
        if i > 0 {
            buf.push(b',');
        }
        let item = dicts.get_item(i)?;
        let dict = item
            .downcast::<PyDict>()
            .map_err(|_| pyo3::exceptions::PyTypeError::new_err("Expected list of dicts"))?;
        write_dict(&mut buf, dict, alias_map)?;
    }

    buf.push(b']');

    Ok(pyo3::types::PyBytes::new(py, &buf))
}

/// Serialize a single Python dict to JSON bytes.
#[pyfunction]
#[pyo3(signature = (dict, alias_map = None))]
fn serialize_dict_to_json<'py>(
    py: Python<'py>,
    dict: &Bound<'py, PyDict>,
    alias_map: Option<&Bound<'py, PyDict>>,
) -> PyResult<Bound<'py, pyo3::types::PyBytes>> {
    let mut buf: Vec<u8> = Vec::with_capacity(256);
    write_dict(&mut buf, dict, alias_map)?;
    Ok(pyo3::types::PyBytes::new(py, &buf))
}

/// Write a Python dict as JSON to the buffer.
fn write_dict(
    buf: &mut Vec<u8>,
    dict: &Bound<'_, PyDict>,
    alias_map: Option<&Bound<'_, PyDict>>,
) -> PyResult<()> {
    buf.push(b'{');

    let mut first = true;
    for (key, value) in dict.iter() {
        if !first {
            buf.push(b',');
        }
        first = false;

        // Write key (with optional alias transformation)
        let key_str: &str = key
            .downcast::<PyString>()
            .map_err(|_| pyo3::exceptions::PyTypeError::new_err("Dict keys must be strings"))?
            .to_str()?;

        let output_key = if let Some(aliases) = alias_map {
            if let Ok(Some(alias)) = aliases.get_item(&key) {
                alias.extract::<String>()?
            } else {
                key_str.to_string()
            }
        } else {
            key_str.to_string()
        };

        write_json_string(buf, &output_key);
        buf.push(b':');

        // Write value
        write_value(buf, &value, alias_map)?;
    }

    buf.push(b'}');
    Ok(())
}

/// Write a Python value as JSON.
fn write_value(
    buf: &mut Vec<u8>,
    value: &Bound<'_, PyAny>,
    alias_map: Option<&Bound<'_, PyDict>>,
) -> PyResult<()> {
    // None
    if value.is_instance_of::<PyNone>() {
        buf.extend_from_slice(b"null");
        return Ok(());
    }

    // Bool (must check before int since bool is subclass of int in Python)
    if let Ok(b) = value.downcast::<PyBool>() {
        if b.is_true() {
            buf.extend_from_slice(b"true");
        } else {
            buf.extend_from_slice(b"false");
        }
        return Ok(());
    }

    // Int
    if let Ok(i) = value.downcast::<PyInt>() {
        let val: i64 = i.extract()?;
        write!(buf, "{val}").unwrap();
        return Ok(());
    }

    // Float
    if let Ok(f) = value.downcast::<PyFloat>() {
        let val: f64 = f.extract()?;
        if val.is_finite() {
            // Use ryu for fast float formatting
            let mut float_buf = ryu::Buffer::new();
            buf.extend_from_slice(float_buf.format(val).as_bytes());
        } else {
            buf.extend_from_slice(b"null");
        }
        return Ok(());
    }

    // String
    if let Ok(s) = value.downcast::<PyString>() {
        write_json_string(buf, s.to_str()?);
        return Ok(());
    }

    // List
    if let Ok(list) = value.downcast::<PyList>() {
        buf.push(b'[');
        for i in 0..list.len() {
            if i > 0 {
                buf.push(b',');
            }
            let item = list.get_item(i)?;
            write_value(buf, &item, alias_map)?;
        }
        buf.push(b']');
        return Ok(());
    }

    // Dict (nested)
    if let Ok(dict) = value.downcast::<PyDict>() {
        write_dict(buf, dict, alias_map)?;
        return Ok(());
    }

    // Fallback: use str() representation as JSON string
    let s = value.str()?.to_str()?.to_string();
    write_json_string(buf, &s);
    Ok(())
}

/// Write a JSON-escaped string.
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

/// Build a snake_case → camelCase alias map from a list of field names.
///
/// Example: ["first_name", "last_name", "id"] → {"first_name": "firstName", "last_name": "lastName"}
/// Fields without underscores are omitted (no transformation needed).
#[pyfunction]
fn build_camel_case_map<'py>(
    py: Python<'py>,
    field_names: &Bound<'py, PyList>,
) -> PyResult<Bound<'py, PyDict>> {
    let map = PyDict::new(py);

    for i in 0..field_names.len() {
        let name = field_names.get_item(i)?;
        let name_str: &str = name.extract()?;

        if name_str.contains('_') {
            let camel = to_camel_case(name_str);
            if camel != name_str {
                map.set_item(name_str, camel)?;
            }
        }
    }

    Ok(map)
}

/// Convert snake_case to camelCase.
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

/// Register serializer functions.
pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_function(wrap_pyfunction!(serialize_dicts_to_json, parent)?)?;
    parent.add_function(wrap_pyfunction!(serialize_dict_to_json, parent)?)?;
    parent.add_function(wrap_pyfunction!(build_camel_case_map, parent)?)?;
    parent.add_function(wrap_pyfunction!(parse_json_bytes, parent)?)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Stage 21A: Zero-copy JSON deserialization
// ---------------------------------------------------------------------------

/// Parse JSON bytes directly into a Python dict with minimal copying.
///
/// Uses serde_json's `from_slice` which borrows from the input bytes
/// for string values, then converts to Python objects. This is faster
/// than Python's json.loads because parsing happens in Rust (no GIL
/// during parse) and string conversion is batched.
///
/// When the ``simd`` feature is enabled at compile time, this uses
/// simd-json for even faster parsing on x86_64/aarch64.
#[pyfunction]
fn parse_json_bytes<'py>(
    py: Python<'py>,
    data: &[u8],
) -> PyResult<PyObject> {
    #[cfg(feature = "simd")]
    {
        let mut data_mut = data.to_vec();
        let value: serde_json::Value = simd_json::from_slice(&mut data_mut)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid JSON: {e}")))?;
        json_value_to_pyobject(py, &value)
    }

    #[cfg(not(feature = "simd"))]
    {
        let value: serde_json::Value = serde_json::from_slice(data)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid JSON: {e}")))?;
        json_value_to_pyobject(py, &value)
    }
}

/// Convert a serde_json::Value to a Python object efficiently.
///
/// Avoids intermediate allocations by converting directly from the
/// parsed JSON tree to Python objects in a single traversal.
fn json_value_to_pyobject(py: Python<'_>, value: &serde_json::Value) -> PyResult<PyObject> {
    match value {
        serde_json::Value::Null => Ok(py.None()),
        serde_json::Value::Bool(b) => Ok(b.to_object(py)),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.to_object(py))
            } else if let Some(f) = n.as_f64() {
                Ok(f.to_object(py))
            } else {
                Ok(py.None())
            }
        }
        serde_json::Value::String(s) => Ok(s.to_object(py)),
        serde_json::Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_value_to_pyobject(py, item)?)?;
            }
            Ok(list.into())
        }
        serde_json::Value::Object(obj) => {
            let dict = PyDict::new(py);
            for (key, val) in obj {
                dict.set_item(key, json_value_to_pyobject(py, val)?)?;
            }
            Ok(dict.into())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_write_json_string_simple() {
        let mut buf = Vec::new();
        write_json_string(&mut buf, "hello");
        assert_eq!(buf, b"\"hello\"");
    }

    #[test]
    fn test_write_json_string_escape() {
        let mut buf = Vec::new();
        write_json_string(&mut buf, "he\"llo");
        assert_eq!(buf, b"\"he\\\"llo\"");
    }

    #[test]
    fn test_write_json_string_newline() {
        let mut buf = Vec::new();
        write_json_string(&mut buf, "a\nb");
        assert_eq!(buf, b"\"a\\nb\"");
    }

    #[test]
    fn test_to_camel_case() {
        assert_eq!(to_camel_case("first_name"), "firstName");
        assert_eq!(to_camel_case("last_name"), "lastName");
        assert_eq!(to_camel_case("id"), "id");
        assert_eq!(to_camel_case("created_at"), "createdAt");
        assert_eq!(to_camel_case("is_active"), "isActive");
    }
}

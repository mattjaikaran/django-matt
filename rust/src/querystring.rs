use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

/// Parse a URL query string into structured components.
///
/// Handles:
///   - `?fields=id,name,email` → fields list
///   - `?filter[status]=active&filter[role]=admin` → filter dict
///   - `?sort=-created,name` → sort list of (field, ascending) tuples
///   - `?page=2&limit=20` → pagination dict
///   - Regular key=value pairs → extras dict
#[pyfunction]
fn parse_query_string<'py>(py: Python<'py>, qs: &str) -> PyResult<Bound<'py, PyDict>> {
    let result = PyDict::new(py);
    let fields = PyList::empty(py);
    let filters = PyDict::new(py);
    let sort = PyList::empty(py);
    let pagination = PyDict::new(py);
    let extras = PyDict::new(py);

    // Strip leading '?'
    let qs = qs.strip_prefix('?').unwrap_or(qs);

    if qs.is_empty() {
        result.set_item("fields", &fields)?;
        result.set_item("filters", &filters)?;
        result.set_item("sort", &sort)?;
        result.set_item("pagination", &pagination)?;
        result.set_item("extras", &extras)?;
        return Ok(result);
    }

    for pair in qs.split('&') {
        let (key, value) = match pair.split_once('=') {
            Some((k, v)) => (k, url_decode(v)),
            None => (pair, String::new()),
        };

        match key {
            // Fields: ?fields=id,name,email
            "fields" => {
                for field in value.split(',') {
                    let trimmed = field.trim();
                    if !trimmed.is_empty() {
                        fields.append(trimmed)?;
                    }
                }
            }

            // Sort: ?sort=-created,name or ?ordering=-created,name
            "sort" | "ordering" => {
                for item in value.split(',') {
                    let trimmed = item.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    let (field, ascending) = if let Some(stripped) = trimmed.strip_prefix('-') {
                        (stripped, false)
                    } else {
                        (trimmed, true)
                    };
                    let tuple = (field, ascending);
                    sort.append(tuple)?;
                }
            }

            // Pagination: ?page=2&limit=20&offset=40
            "page" | "page_size" | "limit" | "offset" | "cursor" | "no_page" => {
                pagination.set_item(key, &value)?;
            }

            // Filters: ?filter[status]=active
            _ if key.starts_with("filter[") && key.ends_with(']') => {
                let filter_name = &key[7..key.len() - 1];
                if !filter_name.is_empty() {
                    filters.set_item(filter_name, &value)?;
                }
            }

            // Django-style filters: ?status=active or ?status__in=a,b
            _ => {
                extras.set_item(key, &value)?;
            }
        }
    }

    result.set_item("fields", &fields)?;
    result.set_item("filters", &filters)?;
    result.set_item("sort", &sort)?;
    result.set_item("pagination", &pagination)?;
    result.set_item("extras", &extras)?;

    Ok(result)
}

/// Basic URL percent-decoding.
fn url_decode(input: &str) -> String {
    let mut result = String::with_capacity(input.len());
    let mut chars = input.bytes();

    while let Some(b) = chars.next() {
        match b {
            b'+' => result.push(' '),
            b'%' => {
                let hi = chars.next().and_then(|c| from_hex(c));
                let lo = chars.next().and_then(|c| from_hex(c));
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

/// Register query string functions.
pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_function(wrap_pyfunction!(parse_query_string, parent)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_url_decode_basic() {
        assert_eq!(url_decode("hello%20world"), "hello world");
        assert_eq!(url_decode("hello+world"), "hello world");
        assert_eq!(url_decode("100%25"), "100%");
    }

    #[test]
    fn test_url_decode_passthrough() {
        assert_eq!(url_decode("simple"), "simple");
        assert_eq!(url_decode(""), "");
    }

    #[test]
    fn test_from_hex() {
        assert_eq!(from_hex(b'0'), Some(0));
        assert_eq!(from_hex(b'9'), Some(9));
        assert_eq!(from_hex(b'a'), Some(10));
        assert_eq!(from_hex(b'f'), Some(15));
        assert_eq!(from_hex(b'A'), Some(10));
        assert_eq!(from_hex(b'g'), None);
    }
}

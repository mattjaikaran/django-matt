use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3::types::PyDict;
use std::collections::HashMap;

/// Result of processing a request through the middleware chain.
#[pyclass]
#[derive(Clone)]
pub struct ProcessResult {
    #[pyo3(get)]
    pub action: String,
    #[pyo3(get)]
    pub headers: HashMap<String, String>,
    #[pyo3(get)]
    pub modified: bool,
}

#[pymethods]
impl ProcessResult {
    fn __repr__(&self) -> String {
        format!("ProcessResult(action='{}', modified={})", self.action, self.modified)
    }
}

/// A Rust-native middleware layer (e.g. header injection, CORS).
#[derive(Clone)]
struct RustLayer {
    name: String,
    layer_type: String,
    config: HashMap<String, String>,
}

impl RustLayer {
    fn process(&self, headers: &mut HashMap<String, String>) -> String {
        match self.layer_type.as_str() {
            "cors" => {
                if let Some(origin) = self.config.get("allow_origin") {
                    headers.insert("Access-Control-Allow-Origin".to_string(), origin.clone());
                }
                if let Some(methods) = self.config.get("allow_methods") {
                    headers.insert("Access-Control-Allow-Methods".to_string(), methods.clone());
                }
                if let Some(h) = self.config.get("allow_headers") {
                    headers.insert("Access-Control-Allow-Headers".to_string(), h.clone());
                }
                "continue".to_string()
            }
            "headers" => {
                for (k, v) in &self.config {
                    if k != "type" {
                        headers.insert(k.clone(), v.clone());
                    }
                }
                "continue".to_string()
            }
            "block" => {
                // Check if a header matches a block condition
                if let Some(block_header) = self.config.get("if_header") {
                    if let Some(block_value) = self.config.get("equals") {
                        if headers.get(block_header).map(|v| v == block_value).unwrap_or(false) {
                            return "block".to_string();
                        }
                    }
                }
                "continue".to_string()
            }
            _ => "continue".to_string(),
        }
    }
}

/// Middleware chain that executes layers in order.
///
/// Rust-native layers (CORS, header injection, blocking rules) execute
/// without the GIL. Python layers are called back via PyObject.
///
/// Usage from Python::
///
///     from django_matt._rust import MiddlewareChain
///     chain = MiddlewareChain()
///     chain.add_rust_layer("cors", '{"allow_origin": "*", "allow_methods": "GET,POST"}')
///     chain.add_rust_layer("headers", '{"X-Frame-Options": "DENY"}')
///     result = chain.process({"Host": "example.com"})
#[pyclass]
pub struct MiddlewareChain {
    rust_layers: Vec<RustLayer>,
}

#[pymethods]
impl MiddlewareChain {
    #[new]
    fn new() -> Self {
        MiddlewareChain {
            rust_layers: Vec::new(),
        }
    }

    /// Add a Rust-native middleware layer.
    ///
    /// Supported types:
    ///   - ``cors``: CORS headers (config: allow_origin, allow_methods, allow_headers)
    ///   - ``headers``: Static header injection (config: key=value pairs)
    ///   - ``block``: Conditional blocking (config: if_header, equals)
    fn add_rust_layer(&mut self, name: &str, config_json: &str) -> PyResult<()> {
        let config: HashMap<String, String> = serde_json::from_str(config_json)
            .map_err(|e| PyValueError::new_err(format!("Invalid config JSON: {e}")))?;

        let layer_type = config.get("type")
            .cloned()
            .unwrap_or_else(|| name.to_string());

        self.rust_layers.push(RustLayer {
            name: name.to_string(),
            layer_type,
            config,
        });
        Ok(())
    }

    /// Process request headers through all Rust layers.
    ///
    /// Returns a ``ProcessResult`` with the final action and modified headers.
    fn process<'py>(
        &self,
        py: Python<'py>,
        headers: &Bound<'py, PyDict>,
    ) -> PyResult<ProcessResult> {
        // Convert PyDict to HashMap
        let mut header_map: HashMap<String, String> = HashMap::new();
        for (k, v) in headers.iter() {
            header_map.insert(k.extract()?, v.extract()?);
        }

        let mut final_action = "continue".to_string();
        let original_len = header_map.len();

        for layer in &self.rust_layers {
            let action = layer.process(&mut header_map);
            if action != "continue" {
                final_action = action;
                break;
            }
        }

        let modified = header_map.len() != original_len || final_action != "continue";

        Ok(ProcessResult {
            action: final_action,
            headers: header_map,
            modified,
        })
    }

    /// Return the number of registered layers.
    #[getter]
    fn layer_count(&self) -> usize {
        self.rust_layers.len()
    }

    /// Return layer names in order.
    fn layer_names(&self) -> Vec<String> {
        self.rust_layers.iter().map(|l| l.name.clone()).collect()
    }
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<MiddlewareChain>()?;
    parent.add_class::<ProcessResult>()?;
    Ok(())
}

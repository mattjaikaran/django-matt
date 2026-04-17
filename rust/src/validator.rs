use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3::types::{PyDict, PyList, PyString};
use std::collections::HashMap;

/// A single field validation rule.
#[derive(Debug, Clone)]
struct FieldRule {
    field_type: FieldType,
    required: bool,
    nullable: bool,
    min_length: Option<usize>,
    max_length: Option<usize>,
    min_value: Option<f64>,
    max_value: Option<f64>,
    pattern: Option<String>,
    choices: Option<Vec<String>>,
}

#[derive(Debug, Clone)]
enum FieldType {
    Str,
    Int,
    Float,
    Bool,
    List,
    Dict,
    Any,
}

impl FieldType {
    fn from_str(s: &str) -> Self {
        match s {
            "str" | "string" => FieldType::Str,
            "int" | "integer" => FieldType::Int,
            "float" | "number" => FieldType::Float,
            "bool" | "boolean" => FieldType::Bool,
            "list" | "array" => FieldType::List,
            "dict" | "object" => FieldType::Dict,
            _ => FieldType::Any,
        }
    }

    fn name(&self) -> &str {
        match self {
            FieldType::Str => "str",
            FieldType::Int => "int",
            FieldType::Float => "float",
            FieldType::Bool => "bool",
            FieldType::List => "list",
            FieldType::Dict => "dict",
            FieldType::Any => "any",
        }
    }
}

/// A compiled schema with pre-parsed field rules.
#[derive(Debug, Clone)]
struct CompiledSchema {
    fields: HashMap<String, FieldRule>,
    allow_extra: bool,
}

/// A validation error for a single field.
#[derive(Debug, Clone)]
struct ValidationError {
    field: String,
    message: String,
    error_type: String,
}

/// Pre-compiled schema validator for fast request body validation.
///
/// Register schemas once at startup, then validate request bodies in
/// microseconds per request.
///
/// Usage from Python::
///
///     from django_matt._rust import SchemaValidator
///     validator = SchemaValidator()
///     validator.register("CreateUser", '{"fields": {"name": {"type": "str", "required": true, "max_length": 100}}}')
///     result = validator.validate("CreateUser", {"name": "Matt"})
///     # result = (True, {}, [])
#[pyclass]
pub struct SchemaValidator {
    schemas: HashMap<String, CompiledSchema>,
}

#[pymethods]
impl SchemaValidator {
    #[new]
    fn new() -> Self {
        SchemaValidator {
            schemas: HashMap::new(),
        }
    }

    /// Register a schema definition (called once at startup).
    ///
    /// Schema JSON format::
    ///
    ///     {
    ///         "fields": {
    ///             "name": {"type": "str", "required": true, "max_length": 100},
    ///             "age": {"type": "int", "min_value": 0, "max_value": 150},
    ///             "email": {"type": "str", "required": true, "pattern": ".*@.*"},
    ///             "role": {"type": "str", "choices": ["admin", "user", "guest"]}
    ///         },
    ///         "allow_extra": false
    ///     }
    fn register(&mut self, name: &str, schema_json: &str) -> PyResult<()> {
        let parsed: serde_json::Value = serde_json::from_str(schema_json)
            .map_err(|e| PyValueError::new_err(format!("Invalid schema JSON: {e}")))?;

        let fields_val = parsed.get("fields")
            .ok_or_else(|| PyValueError::new_err("Schema must have 'fields' key"))?;

        let fields_obj = fields_val.as_object()
            .ok_or_else(|| PyValueError::new_err("'fields' must be an object"))?;

        let allow_extra = parsed.get("allow_extra")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let mut fields = HashMap::new();
        for (field_name, field_def) in fields_obj {
            let obj = field_def.as_object()
                .ok_or_else(|| PyValueError::new_err(format!("Field '{field_name}' must be an object")))?;

            let field_type_str = obj.get("type")
                .and_then(|v| v.as_str())
                .unwrap_or("any");

            let rule = FieldRule {
                field_type: FieldType::from_str(field_type_str),
                required: obj.get("required").and_then(|v| v.as_bool()).unwrap_or(false),
                nullable: obj.get("nullable").and_then(|v| v.as_bool()).unwrap_or(false),
                min_length: obj.get("min_length").and_then(|v| v.as_u64()).map(|v| v as usize),
                max_length: obj.get("max_length").and_then(|v| v.as_u64()).map(|v| v as usize),
                min_value: obj.get("min_value").and_then(|v| v.as_f64()),
                max_value: obj.get("max_value").and_then(|v| v.as_f64()),
                pattern: obj.get("pattern").and_then(|v| v.as_str()).map(|s| s.to_string()),
                choices: obj.get("choices").and_then(|v| v.as_array()).map(|arr| {
                    arr.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect()
                }),
            };

            fields.insert(field_name.clone(), rule);
        }

        self.schemas.insert(name.to_string(), CompiledSchema { fields, allow_extra });
        Ok(())
    }

    /// Validate a Python dict against a registered schema.
    ///
    /// Returns ``(valid, errors)`` where ``errors`` is a list of dicts
    /// with ``field``, ``message``, and ``type`` keys.
    fn validate<'py>(
        &self,
        py: Python<'py>,
        schema_name: &str,
        data: &Bound<'py, PyDict>,
    ) -> PyResult<(bool, Bound<'py, PyList>)> {
        let schema = self.schemas.get(schema_name)
            .ok_or_else(|| PyValueError::new_err(format!("Unknown schema: {schema_name}")))?;

        let errors = self.validate_dict(py, schema, data)?;

        let error_list = PyList::empty(py);
        for err in &errors {
            let d = PyDict::new(py);
            d.set_item("field", &err.field)?;
            d.set_item("message", &err.message)?;
            d.set_item("type", &err.error_type)?;
            error_list.append(d)?;
        }

        Ok((errors.is_empty(), error_list))
    }

    /// Validate raw JSON bytes against a registered schema.
    ///
    /// Parses JSON and validates in a single pass. Returns ``(valid, parsed_data, errors)``.
    fn parse_and_validate<'py>(
        &self,
        py: Python<'py>,
        schema_name: &str,
        body: &[u8],
    ) -> PyResult<(bool, PyObject, Bound<'py, PyList>)> {
        let schema = self.schemas.get(schema_name)
            .ok_or_else(|| PyValueError::new_err(format!("Unknown schema: {schema_name}")))?;

        // Parse JSON
        let value: serde_json::Value = serde_json::from_slice(body)
            .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {e}")))?;

        let obj = value.as_object()
            .ok_or_else(|| PyValueError::new_err("Request body must be a JSON object"))?;

        // Convert to PyDict for validation
        let data = json_to_pydict(py, &value)?;
        let bound_data = data.bind(py);
        let errors = self.validate_dict(py, schema, bound_data)?;

        let error_list = PyList::empty(py);
        for err in &errors {
            let d = PyDict::new(py);
            d.set_item("field", &err.field)?;
            d.set_item("message", &err.message)?;
            d.set_item("type", &err.error_type)?;
            error_list.append(d)?;
        }

        Ok((errors.is_empty(), data.into_any(), error_list))
    }

    /// Return the number of registered schemas.
    #[getter]
    fn schema_count(&self) -> usize {
        self.schemas.len()
    }

    /// Return registered schema names.
    fn schema_names(&self) -> Vec<String> {
        self.schemas.keys().cloned().collect()
    }
}

impl SchemaValidator {
    fn validate_dict<'py>(
        &self,
        py: Python<'py>,
        schema: &CompiledSchema,
        data: &Bound<'py, PyDict>,
    ) -> PyResult<Vec<ValidationError>> {
        let mut errors = Vec::new();

        // Check required fields and validate present fields
        for (field_name, rule) in &schema.fields {
            match data.get_item(field_name)? {
                None => {
                    if rule.required {
                        errors.push(ValidationError {
                            field: field_name.clone(),
                            message: "This field is required".to_string(),
                            error_type: "missing".to_string(),
                        });
                    }
                }
                Some(value) => {
                    if value.is_none() {
                        if !rule.nullable {
                            errors.push(ValidationError {
                                field: field_name.clone(),
                                message: "This field cannot be null".to_string(),
                                error_type: "null".to_string(),
                            });
                        }
                        continue;
                    }

                    // Type check
                    if let Some(err) = self.check_type(py, field_name, &value, rule) {
                        errors.push(err);
                        continue;
                    }

                    // Constraint checks
                    errors.extend(self.check_constraints(field_name, &value, rule));
                }
            }
        }

        // Check for extra fields
        if !schema.allow_extra {
            for key in data.keys() {
                let key_str: String = key.extract()?;
                if !schema.fields.contains_key(&key_str) {
                    errors.push(ValidationError {
                        field: key_str,
                        message: "Extra field not allowed".to_string(),
                        error_type: "extra".to_string(),
                    });
                }
            }
        }

        Ok(errors)
    }

    fn check_type<'py>(
        &self,
        _py: Python<'py>,
        field_name: &str,
        value: &Bound<'py, pyo3::PyAny>,
        rule: &FieldRule,
    ) -> Option<ValidationError> {
        let type_ok = match rule.field_type {
            FieldType::Str => value.is_instance_of::<PyString>(),
            FieldType::Int => {
                // Accept int but not bool (bool is subclass of int in Python)
                value.get_type().name().map(|n| n == "int").unwrap_or(false)
            }
            FieldType::Float => {
                value.extract::<f64>().is_ok() && !value.is_instance_of::<pyo3::types::PyBool>()
            }
            FieldType::Bool => value.is_instance_of::<pyo3::types::PyBool>(),
            FieldType::List => value.is_instance_of::<PyList>(),
            FieldType::Dict => value.is_instance_of::<PyDict>(),
            FieldType::Any => true,
        };

        if !type_ok {
            Some(ValidationError {
                field: field_name.to_string(),
                message: format!("Expected type '{}', got '{}'", rule.field_type.name(), value.get_type().name().map(|n| n.to_string()).unwrap_or_else(|_| "unknown".to_string())),
                error_type: "type".to_string(),
            })
        } else {
            None
        }
    }

    fn check_constraints<'py>(
        &self,
        field_name: &str,
        value: &Bound<'py, pyo3::PyAny>,
        rule: &FieldRule,
    ) -> Vec<ValidationError> {
        let mut errors = Vec::new();

        // String length constraints
        if let Ok(s) = value.extract::<String>() {
            if let Some(min) = rule.min_length {
                if s.len() < min {
                    errors.push(ValidationError {
                        field: field_name.to_string(),
                        message: format!("Must be at least {min} characters"),
                        error_type: "min_length".to_string(),
                    });
                }
            }
            if let Some(max) = rule.max_length {
                if s.len() > max {
                    errors.push(ValidationError {
                        field: field_name.to_string(),
                        message: format!("Must be at most {max} characters"),
                        error_type: "max_length".to_string(),
                    });
                }
            }
            if let Some(ref choices) = rule.choices {
                if !choices.contains(&s) {
                    errors.push(ValidationError {
                        field: field_name.to_string(),
                        message: format!("Must be one of: {}", choices.join(", ")),
                        error_type: "choices".to_string(),
                    });
                }
            }
        }

        // Numeric constraints
        if let Ok(n) = value.extract::<f64>() {
            if let Some(min) = rule.min_value {
                if n < min {
                    errors.push(ValidationError {
                        field: field_name.to_string(),
                        message: format!("Must be at least {min}"),
                        error_type: "min_value".to_string(),
                    });
                }
            }
            if let Some(max) = rule.max_value {
                if n > max {
                    errors.push(ValidationError {
                        field: field_name.to_string(),
                        message: format!("Must be at most {max}"),
                        error_type: "max_value".to_string(),
                    });
                }
            }
        }

        errors
    }
}

/// Convert a serde_json::Value to a Python object.
fn json_to_pydict(py: Python<'_>, value: &serde_json::Value) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);
    if let Some(obj) = value.as_object() {
        for (k, v) in obj {
            let py_val = json_to_pyobject(py, v)?;
            dict.set_item(k, py_val)?;
        }
    }
    Ok(dict.unbind())
}

fn json_to_pyobject(py: Python<'_>, value: &serde_json::Value) -> PyResult<PyObject> {
    match value {
        serde_json::Value::Null => Ok(py.None()),
        serde_json::Value::Bool(b) => Ok(pyo3::types::PyBool::new(py, *b).to_owned().into_any().unbind()),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.into_pyobject(py)?.into_any().unbind())
            } else if let Some(f) = n.as_f64() {
                Ok(f.into_pyobject(py)?.into_any().unbind())
            } else {
                Ok(py.None())
            }
        }
        serde_json::Value::String(s) => Ok(s.as_str().into_pyobject(py)?.into_any().unbind()),
        serde_json::Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_to_pyobject(py, item)?)?;
            }
            Ok(list.into_any().unbind())
        }
        serde_json::Value::Object(_) => {
            let d = json_to_pydict(py, value)?;
            Ok(d.into_any())
        }
    }
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<SchemaValidator>()?;
    Ok(())
}

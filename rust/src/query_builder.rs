use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;

/// Build a parameterized SELECT query from structured specs.
///
/// Returns ``(sql, params)`` where params is a list of string values.
///
/// Usage from Python::
///
///     from django_matt._rust import build_select, build_filter_clause
///     sql, params = build_select("users", ["id", "name"], [("age", "gte", "18")], [("name", False)], 10, 0)
///     # sql = 'SELECT "id", "name" FROM "users" WHERE "age" >= $1 ORDER BY "name" ASC LIMIT 10 OFFSET 0'
///     # params = ["18"]
#[pyfunction]
fn build_select(
    table: &str,
    fields: Vec<String>,
    filters: Vec<(String, String, String)>,
    order_by: Vec<(String, bool)>,
    limit: Option<u32>,
    offset: Option<u32>,
) -> PyResult<(String, Vec<String>)> {
    let mut sql = String::with_capacity(256);
    let mut params: Vec<String> = Vec::new();

    // SELECT
    if fields.is_empty() {
        sql.push_str("SELECT *");
    } else {
        sql.push_str("SELECT ");
        let field_list: Vec<String> = fields.iter().map(|f| format!("\"{}\"", f)).collect();
        sql.push_str(&field_list.join(", "));
    }

    // FROM
    sql.push_str(&format!(" FROM \"{}\"", table));

    // WHERE
    if !filters.is_empty() {
        let (clause, filter_params) = build_where_clause(&filters)?;
        sql.push_str(" WHERE ");
        sql.push_str(&clause);
        params.extend(filter_params);
    }

    // ORDER BY
    if !order_by.is_empty() {
        sql.push_str(" ORDER BY ");
        let order_parts: Vec<String> = order_by
            .iter()
            .map(|(field, desc)| {
                if *desc {
                    format!("\"{}\" DESC", field)
                } else {
                    format!("\"{}\" ASC", field)
                }
            })
            .collect();
        sql.push_str(&order_parts.join(", "));
    }

    // LIMIT
    if let Some(lim) = limit {
        sql.push_str(&format!(" LIMIT {}", lim));
    }

    // OFFSET
    if let Some(off) = offset {
        if off > 0 {
            sql.push_str(&format!(" OFFSET {}", off));
        }
    }

    Ok((sql, params))
}

/// Build a parameterized WHERE clause from filter specs.
///
/// Each filter is ``(field, operator, value)``.
/// Supported operators: eq, ne, gt, gte, lt, lte, like, ilike, in, is_null
///
/// Returns ``(clause, params)``.
#[pyfunction]
fn build_filter_clause(
    filters: Vec<(String, String, String)>,
) -> PyResult<(String, Vec<String>)> {
    build_where_clause(&filters)
}

fn build_where_clause(
    filters: &[(String, String, String)],
) -> PyResult<(String, Vec<String>)> {
    let mut parts: Vec<String> = Vec::new();
    let mut params: Vec<String> = Vec::new();
    let mut param_idx = 1;

    for (field, op, value) in filters {
        let sql_op = match op.as_str() {
            "eq" | "=" => "=",
            "ne" | "!=" => "!=",
            "gt" | ">" => ">",
            "gte" | ">=" => ">=",
            "lt" | "<" => "<",
            "lte" | "<=" => "<=",
            "like" => "LIKE",
            "ilike" => "ILIKE",
            "in" => "IN",
            "is_null" => {
                if value == "true" {
                    parts.push(format!("\"{}\" IS NULL", field));
                } else {
                    parts.push(format!("\"{}\" IS NOT NULL", field));
                }
                continue;
            }
            other => {
                return Err(PyValueError::new_err(format!("Unknown operator: {other}")));
            }
        };

        if op == "in" {
            // IN operator: value is comma-separated
            let values: Vec<&str> = value.split(',').map(|v| v.trim()).collect();
            let placeholders: Vec<String> = values
                .iter()
                .map(|v| {
                    params.push(v.to_string());
                    let p = format!("${}", param_idx);
                    param_idx += 1;
                    p
                })
                .collect();
            parts.push(format!("\"{}\" IN ({})", field, placeholders.join(", ")));
        } else {
            params.push(value.clone());
            parts.push(format!("\"{}\" {} ${}", field, sql_op, param_idx));
            param_idx += 1;
        }
    }

    Ok((parts.join(" AND "), params))
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_function(wrap_pyfunction!(build_select, parent)?)?;
    parent.add_function(wrap_pyfunction!(build_filter_clause, parent)?)?;
    Ok(())
}

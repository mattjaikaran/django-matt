use pyo3::prelude::*;

mod headers;
mod jwt;
mod middleware_chain;
mod permissions;
mod query_builder;
mod querystring;
mod rate_limiter;
mod router;
mod serializer;
mod validator;

/// django-matt Rust acceleration module.
///
/// Compiled hot paths:
/// - URL routing (radix tree)
/// - JWT encode/decode/verify (HMAC: HS256/HS384/HS512, RSA: RS256/RS384/RS512, EC: ES256/ES384)
/// - Query string parsing
/// - Header parsing
/// - JSON serialization (dict list → bytes)
/// - Rate limiting (token bucket)
/// - Permission evaluation (bitfield expressions)
/// - Schema validation (pre-compiled rules)
/// - Middleware chain (CORS, headers, blocking)
/// - Query builder (parameterized SQL)
#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("HAS_RUST_EXTENSIONS", true)?;

    router::register(m)?;
    jwt::register(m)?;
    querystring::register(m)?;
    headers::register(m)?;
    serializer::register(m)?;
    rate_limiter::register(m)?;
    permissions::register(m)?;
    validator::register(m)?;
    middleware_chain::register(m)?;
    query_builder::register(m)?;

    Ok(())
}

use pyo3::prelude::*;

mod jwt;
mod router;

/// django-matt Rust acceleration module.
///
/// Provides compiled implementations of hot paths:
/// - URL routing (radix tree)
/// - JWT encode/decode/verify (HMAC: HS256/HS384/HS512)
/// - Schema serialization (planned)
/// - Query string parsing (planned)
#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("HAS_RUST_EXTENSIONS", true)?;

    router::register(m)?;
    jwt::register(m)?;

    Ok(())
}

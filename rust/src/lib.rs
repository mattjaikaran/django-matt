use pyo3::prelude::*;

mod router;

/// django-matt Rust acceleration module.
///
/// Provides compiled implementations of hot paths:
/// - URL routing (radix tree)
/// - JWT encode/decode/verify (planned)
/// - Schema serialization (planned)
/// - Query string parsing (planned)
#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("HAS_RUST_EXTENSIONS", true)?;

    // Router submodule
    router::register(m)?;

    Ok(())
}

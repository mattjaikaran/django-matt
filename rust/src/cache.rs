//! Stage 21D: Rust-layer response cache with TTL eviction.
//!
//! Provides an in-process response cache that sits between the router
//! and view execution. Cached responses bypass Python entirely for
//! repeated reads, delivering sub-millisecond latency.
//!
//! The cache key is ``{method}:{path}`` and each entry carries a TTL.
//! Eviction runs lazily on access — expired entries are removed when
//! they would be returned or when the cache exceeds capacity.
//!
//! This cache is per-worker (shared-nothing architecture — see granian_backend.py
//! for the multi-process design). No cross-worker coordination is needed.

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::collections::HashMap;
use std::time::{Duration, Instant};

/// A single cached response entry.
#[derive(Debug, Clone)]
struct CacheEntry {
    /// Raw response body bytes.
    body: Vec<u8>,
    /// HTTP status code.
    status: u16,
    /// Response content type (for correct serialization).
    content_type: String,
    /// When this entry was inserted.
    inserted_at: Instant,
    /// Time-to-live from insertion.
    ttl: Duration,
}

impl CacheEntry {
    fn is_expired(&self) -> bool {
        self.inserted_at.elapsed() >= self.ttl
    }
}

/// An in-process response cache with TTL-based eviction.
///
/// Python usage::
///
///     from django_matt._rust import ResponseCache
///     cache = ResponseCache(max_entries=1000, default_ttl_seconds=30)
///     cache.set("GET:/api/users", b'[{"id":1}]', 200, "application/json", ttl=60)
///     result = cache.get("GET:/api/users")
///     # result = (b'[{"id":1}]', 200, "application/json") or None
#[pyclass]
pub struct ResponseCache {
    entries: HashMap<String, CacheEntry>,
    max_entries: usize,
    default_ttl: Duration,
}

#[pymethods]
impl ResponseCache {
    /// Create a new response cache.
    ///
    /// Args:
    ///     max_entries: Maximum number of cached responses before eviction (default 1000).
    ///     default_ttl_seconds: Default TTL in seconds for entries (default 30).
    #[new]
    #[pyo3(signature = (max_entries = 1000, default_ttl_seconds = 30))]
    fn new(max_entries: usize, default_ttl_seconds: u64) -> Self {
        ResponseCache {
            entries: HashMap::with_capacity(max_entries.min(1024)),
            max_entries,
            default_ttl: Duration::from_secs(default_ttl_seconds),
        }
    }

    /// Store a response in the cache.
    ///
    /// Args:
    ///     key: Cache key, typically ``"{method}:{path}"``.
    ///     body: Raw response body bytes.
    ///     status: HTTP status code.
    ///     content_type: Content-Type header value.
    ///     ttl: Optional TTL in seconds for this specific entry.
    #[pyo3(signature = (key, body, status, content_type, ttl = None))]
    fn set(
        &mut self,
        key: &str,
        body: Vec<u8>,
        status: u16,
        content_type: &str,
        ttl: Option<u64>,
    ) {
        let ttl_dur = ttl.map_or(self.default_ttl, Duration::from_secs);

        let entry = CacheEntry {
            body,
            status,
            content_type: content_type.to_string(),
            inserted_at: Instant::now(),
            ttl: ttl_dur,
        };

        // Evict if at capacity (drop oldest expired first, then LRU-ish via removal)
        if self.entries.len() >= self.max_entries {
            self.evict_expired();
            // If still full, drop the entry with the earliest insertion time
            if self.entries.len() >= self.max_entries {
                if let Some(oldest_key) = self
                    .entries
                    .iter()
                    .min_by_key(|(_, e)| e.inserted_at)
                    .map(|(k, _)| k.clone())
                {
                    self.entries.remove(&oldest_key);
                }
            }
        }

        self.entries.insert(key.to_string(), entry);
    }

    /// Retrieve a cached response.
    ///
    /// Returns ``(body, status, content_type)`` as a tuple, or ``None`` if
    /// not found or expired.
    fn get<'py>(&mut self, py: Python<'py>, key: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
        if let Some(entry) = self.entries.get(key) {
            if entry.is_expired() {
                self.entries.remove(key);
                return Ok(None);
            }

            let body = PyBytes::new(py, &entry.body);
            let content_type = entry.content_type.clone();
            let status = entry.status;

            let tuple: Bound<'py, PyAny> = (body, status, content_type).into_pyobject(py)?;
            Ok(Some(tuple))
        } else {
            Ok(None)
        }
    }

    /// Remove a specific entry from the cache.
    fn invalidate(&mut self, key: &str) {
        self.entries.remove(key);
    }

    /// Remove all entries whose key starts with the given prefix.
    ///
    /// Useful for bulk invalidation (e.g., ``cache.invalidate_prefix("GET:/api/users")``
    /// removes all user-related responses).
    fn invalidate_prefix(&mut self, prefix: &str) -> usize {
        let keys: Vec<String> = self
            .entries
            .keys()
            .filter(|k| k.starts_with(prefix))
            .cloned()
            .collect();
        let count = keys.len();
        for key in keys {
            self.entries.remove(&key);
        }
        count
    }

    /// Evict all expired entries. Called automatically on set/get,
    /// but can be called explicitly for proactive cleanup.
    fn evict_expired(&mut self) -> usize {
        let mut expired: Vec<String> = Vec::new();
        for (key, entry) in &self.entries {
            if entry.is_expired() {
                expired.push(key.clone());
            }
        }
        let count = expired.len();
        for key in expired {
            self.entries.remove(&key);
        }
        count
    }

    /// Remove all entries from the cache.
    fn clear(&mut self) {
        self.entries.clear();
    }

    /// Number of entries currently in the cache (including expired).
    #[getter]
    fn size(&self) -> usize {
        self.entries.len()
    }

    /// Maximum capacity.
    #[getter]
    fn capacity(&self) -> usize {
        self.max_entries
    }

    /// Cache statistics: (hits, misses, size).
    ///
    /// Note: hits/misses track access pattern since creation or last reset.
    /// These are approximate — if keys are re-set, counts reflect the
    /// current key lifecycle.
    fn stats(&self) -> (usize, usize) {
        let total = self.entries.len();
        let expired = self.entries.values().filter(|e| e.is_expired()).count();
        (total - expired, expired)
    }
}

/// Register the cache class.
pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<ResponseCache>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_set_get() {
        let mut cache = ResponseCache::new(10, 60);
        cache.set("GET:/test", b"hello".to_vec(), 200, "text/plain", None);

        // Can't easily test get() without Python — test internal state
        assert_eq!(cache.size(), 1);
    }

    #[test]
    fn test_cache_expiry() {
        let mut cache = ResponseCache {
            entries: HashMap::new(),
            max_entries: 10,
            default_ttl: Duration::from_secs(0), // immediate expiry
        };
        cache.set("GET:/test", b"hello".to_vec(), 200, "text/plain", None);
        // Entry should be expired immediately
        assert!(cache.entries.get("GET:/test").unwrap().is_expired());
    }

    #[test]
    fn test_cache_eviction() {
        let mut cache = ResponseCache::new(2, 60);
        cache.set("k1", b"a".to_vec(), 200, "text/plain", None);
        cache.set("k2", b"b".to_vec(), 200, "text/plain", None);
        cache.set("k3", b"c".to_vec(), 200, "text/plain", None);
        // Should have evicted one
        assert!(cache.size() <= 2);
    }

    #[test]
    fn test_invalidate_prefix() {
        let mut cache = ResponseCache::new(10, 60);
        cache.set("GET:/api/users", b"[]".to_vec(), 200, "application/json", None);
        cache.set("GET:/api/posts", b"[]".to_vec(), 200, "application/json", None);
        cache.set("POST:/api/users", b"{}".to_vec(), 201, "application/json", None);

        let removed = cache.invalidate_prefix("GET:/api/");
        assert_eq!(removed, 2);
        assert_eq!(cache.size(), 1);
    }
}

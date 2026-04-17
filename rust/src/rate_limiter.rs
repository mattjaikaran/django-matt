use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::Mutex;
use std::time::Instant;

/// A single token bucket.
struct TokenBucket {
    tokens: f64,
    last_refill: Instant,
}

/// Atomic token-bucket rate limiter, entirely off the GIL.
///
/// Each unique key (e.g. IP address, user ID) gets its own bucket.
/// Tokens refill continuously at `refill_per_second`. When a request
/// arrives, one token is consumed. If no tokens remain, the request
/// is denied.
///
/// Usage from Python::
///
///     from django_matt._rust import RateLimiter
///     limiter = RateLimiter(capacity=100, refill_per_second=10.0)
///     allowed, remaining, reset_ms = limiter.check(b"192.168.1.1")
#[pyclass]
pub struct RateLimiter {
    buckets: Mutex<HashMap<Vec<u8>, TokenBucket>>,
    capacity: u32,
    refill_rate: f64,
}

#[pymethods]
impl RateLimiter {
    #[new]
    fn new(capacity: u32, refill_per_second: f64) -> Self {
        RateLimiter {
            buckets: Mutex::new(HashMap::new()),
            capacity,
            refill_rate: refill_per_second,
        }
    }

    /// Check if a request is allowed for the given key.
    ///
    /// Returns ``(allowed, remaining, reset_at_ms)`` where:
    /// - ``allowed``: whether the request should proceed
    /// - ``remaining``: tokens left after this request
    /// - ``reset_at_ms``: milliseconds until the bucket is fully refilled
    fn check(&self, key: &[u8]) -> (bool, u32, u64) {
        let mut buckets = self.buckets.lock().unwrap();
        let now = Instant::now();

        let bucket = buckets
            .entry(key.to_vec())
            .or_insert_with(|| TokenBucket {
                tokens: self.capacity as f64,
                last_refill: now,
            });

        // Refill tokens based on elapsed time
        let elapsed = now.duration_since(bucket.last_refill).as_secs_f64();
        bucket.tokens = (bucket.tokens + elapsed * self.refill_rate).min(self.capacity as f64);
        bucket.last_refill = now;

        if bucket.tokens >= 1.0 {
            bucket.tokens -= 1.0;
            let remaining = bucket.tokens as u32;
            let reset_ms = if remaining >= self.capacity {
                0
            } else {
                ((self.capacity as f64 - bucket.tokens) / self.refill_rate * 1000.0) as u64
            };
            (true, remaining, reset_ms)
        } else {
            let reset_ms = ((1.0 - bucket.tokens) / self.refill_rate * 1000.0) as u64;
            (false, 0, reset_ms)
        }
    }

    /// Bulk-check multiple keys at once.
    ///
    /// Returns a list of ``(allowed, remaining, reset_at_ms)`` tuples,
    /// one per input key, in the same order.
    fn check_many(&self, keys: Vec<Vec<u8>>) -> Vec<(bool, u32, u64)> {
        keys.iter().map(|k| self.check(k.as_slice())).collect()
    }

    /// Remove expired buckets that have been full for longer than ``max_idle_seconds``.
    ///
    /// Call periodically (e.g. every 60s) to prevent memory growth from
    /// one-time visitors.
    fn cleanup(&self, max_idle_seconds: f64) -> usize {
        let mut buckets = self.buckets.lock().unwrap();
        let now = Instant::now();
        let before = buckets.len();

        buckets.retain(|_, bucket| {
            let elapsed = now.duration_since(bucket.last_refill).as_secs_f64();
            let would_be = (bucket.tokens + elapsed * self.refill_rate).min(self.capacity as f64);
            // Keep if bucket isn't full OR hasn't been idle long enough
            would_be < self.capacity as f64 || elapsed < max_idle_seconds
        });

        before - buckets.len()
    }

    /// Return the number of tracked keys.
    #[getter]
    fn size(&self) -> usize {
        self.buckets.lock().unwrap().len()
    }

    /// Return the configured capacity.
    #[getter]
    fn capacity(&self) -> u32 {
        self.capacity
    }

    /// Return the configured refill rate.
    #[getter]
    fn refill_rate(&self) -> f64 {
        self.refill_rate
    }
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<RateLimiter>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_check() {
        let limiter = RateLimiter::new(5, 1.0);
        let key = b"test";

        // First 5 should be allowed
        for i in 0..5 {
            let (allowed, remaining, _) = limiter.check(key);
            assert!(allowed, "Request {} should be allowed", i);
            assert_eq!(remaining, (4 - i) as u32);
        }

        // 6th should be denied
        let (allowed, remaining, _) = limiter.check(key);
        assert!(!allowed);
        assert_eq!(remaining, 0);
    }

    #[test]
    fn test_different_keys_independent() {
        let limiter = RateLimiter::new(1, 0.0);

        let (allowed, _, _) = limiter.check(b"key_a");
        assert!(allowed);

        let (allowed, _, _) = limiter.check(b"key_b");
        assert!(allowed);

        // key_a should be exhausted
        let (allowed, _, _) = limiter.check(b"key_a");
        assert!(!allowed);
    }

    #[test]
    fn test_check_many() {
        let limiter = RateLimiter::new(2, 0.0);
        let keys: Vec<Vec<u8>> = vec![b"a".to_vec(), b"b".to_vec(), b"c".to_vec()];
        let results = limiter.check_many(keys);
        assert_eq!(results.len(), 3);
        assert!(results.iter().all(|(allowed, _, _)| *allowed));
    }

    #[test]
    fn test_size() {
        let limiter = RateLimiter::new(10, 1.0);
        assert_eq!(limiter.size(), 0);
        limiter.check(b"a");
        limiter.check(b"b");
        assert_eq!(limiter.size(), 2);
    }
}

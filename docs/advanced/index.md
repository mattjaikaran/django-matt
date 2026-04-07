# Advanced Guides

Deep dives into production deployment, scaling, security, performance tuning, and extensibility.

## Guides

### [Production Readiness Checklist](production-checklist.md)
Everything you need to verify before deploying a django-matt app to production. Covers security hardening, performance tuning, observability, database configuration, auth settings, error handling, and deployment infrastructure.

### [Scaling Guide](scaling.md)
How to scale django-matt apps from a single process to a distributed fleet. Covers horizontal scaling with ASGI, database connection pooling, caching strategies, background task offloading, WebSocket scaling, and slim mode for reduced memory footprint.

### [Building Custom Extensions](custom-extensions.md)
How to extend django-matt with custom modules, interceptors, exception filters, auth backends, and serialization backends. Includes guidance on packaging extensions for distribution via entry points.

### [Security Best Practices](security.md)
Comprehensive security guidance covering JWT configuration, API key management, secrets backends, rate limiting, CORS, input validation, SQL injection prevention, and OWASP top 10 coverage.

### [Performance Tuning Guide](performance-tuning.md)
Deep dive into squeezing maximum performance out of django-matt. Covers Rust extensions, auto-instrumentation, query optimization, serialization with orjson and model_construct, caching layers, and connection pooling tuning.

## Related

- [Best Practices](../best-practices.md) -- high-level patterns for project structure, async development, service layers, and testing
- [Configuration](../configuration.md) -- the `configure()` system and settings namespaces
- [Observability](../observability/) -- tracing, metrics, and structured logging

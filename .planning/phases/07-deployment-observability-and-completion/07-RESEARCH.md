# Phase 7: Deployment, Observability, and Completion - Research

**Researched:** 2026-03-08
**Domain:** Deployment configs, observability (logging/metrics/tracing), audit/files/tasks/admin/GraphQL/HTMX/AI/ML/pagination/filtering/throttling
**Confidence:** HIGH

## Summary

Phase 7 is the final phase of django-matt v1. It covers two major areas: (1) deployment and observability hardening, and (2) bringing the remaining optional modules to v1 quality. All modules already have substantial code -- this phase is about auditing, fixing bugs, adding missing features (particularly soft delete in audit, CONN_MAX_AGE enforcement in deployment templates), and ensuring test coverage meets success criteria.

The codebase already has: deploy providers for Fly.io, Railway, Render, AWS, Hetzner, and DigitalOcean; a full observability module with structured logging, Prometheus metrics, and OpenTelemetry tracing; audit logging with AuditableMixin; S3/R2/MinIO storage backends; Celery/Dramatiq/Django-Q task backends; Strawberry GraphQL schema generation; Django Unfold admin integration; HTMX helpers; AI/ML modules; and pagination/filtering/throttling modules. The primary gaps are: CONN_MAX_AGE=0 enforcement across all ASGI deployment templates, soft-delete integration with audit module, test coverage for success criteria verification, and wiring up the remaining missing pieces.

**Primary recommendation:** Audit each module's existing code against its requirements, fix the identified gaps (especially CONN_MAX_AGE enforcement which is a known production blocker from STATE.md), write success-criteria-aligned tests, and avoid rewriting modules that already work.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPLOY-01 | Docker deployment template with ASGI (Granian/uvicorn) | `deploy/docker.py` has DockerfileGenerator; needs ASGI default and CONN_MAX_AGE=0 |
| DEPLOY-02 | Fly.io deployment configuration | `deploy/providers/flyio.py` exists with FlyioProvider; needs CONN_MAX_AGE audit |
| DEPLOY-03 | Railway deployment configuration | `deploy/providers/railway.py` exists; needs CONN_MAX_AGE audit |
| DEPLOY-04 | Render deployment configuration | `deploy/providers/render.py` exists; needs CONN_MAX_AGE audit |
| DEPLOY-05 | AWS deployment configuration | `deploy/providers/aws.py` exists; needs CONN_MAX_AGE audit |
| DEPLOY-06 | CONN_MAX_AGE=0 enforced in all ASGI deployment templates | Known blocker from STATE.md; `deploy/environments.py` defaults 0 but line 253 overrides to 600; config templates use non-zero values |
| OBS-01 | Structured logging with configurable formatters | `observability/logging.py` has JSONFormatter, PrettyJSONFormatter, ColoredTextFormatter |
| OBS-02 | Metrics collection (Prometheus-compatible) | `observability/metrics.py` has MetricsManager with prometheus_client fallback |
| OBS-03 | Distributed tracing (OpenTelemetry) | `observability/tracing.py` has TracingManager with OTEL/Jaeger/Zipkin/Datadog/NewRelic |
| OBS-04 | Request/response inspector for development | `inspector/` module exists with middleware, controllers, storage, export |
| AUDIT-01 | Audit log capturing create/update/delete with user, timestamp, and diff | `audit/models.py` AuditLog.log() with changes/old_values/new_values; AuditableMixin tracks changes |
| AUDIT-02 | Soft delete support with restore capability | `db/soft_delete.py` has SoftDeleteMixin; needs integration test with audit module |
| AUDIT-03 | Audit log query API for admin dashboards | `audit/utils.py` has get_audit_history, get_user_actions, get_recent_activity |
| FILE-01 | File upload handling with validation (size, type) | `files/upload.py` has UploadedFile; `files/validators.py` exists |
| FILE-02 | S3 storage backend | `files/s3.py` has S3Storage with full CRUD |
| FILE-03 | Cloudflare R2 storage backend | `files/s3.py` has R2Storage extending S3Storage |
| FILE-04 | MinIO storage backend | `files/s3.py` has MinIOStorage extending S3Storage |
| FILE-05 | Signed URL generation for private files | `files/s3.py` has presigned_download_url() and presigned_upload_url() |
| TASK-01 | Celery task integration | `tasks/backends/celery.py` exists |
| TASK-02 | Dramatiq task integration | `tasks/backends/dramatiq.py` exists |
| TASK-03 | Django-Q task integration | `tasks/backends/django_q.py` exists |
| TASK-04 | Task status tracking and result retrieval | `tasks/base.py` has TaskResult with status tracking |
| HTMX-01 | HTMX response helpers (triggers, swaps, redirects) | `htmx/response.py` exists (487 lines) |
| HTMX-02 | Livewire-style reactive component helpers | `htmx/components.py` exists (646 lines) |
| COMP-01 | Backend-served component system | `components/` module exists with base, data, forms, layout, serving, theming |
| GQL-01 | Strawberry-based schema auto-generation | `graphql/schema.py` and `graphql/codegen.py` exist |
| GQL-02 | DataLoader integration for N+1 prevention | `graphql/dataloaders.py` exists (513 lines) |
| GQL-03 | GraphQL endpoint served alongside REST | `graphql/views.py` exists (333 lines) |
| ADMIN-01 | Django Unfold integration for modern admin UI | `admin/base.py` and `admin/config.py` exist |
| ADMIN-02 | Admin dashboard widgets | `admin/widgets.py` (501 lines) and `admin/dashboard.py` (389 lines) |
| ADMIN-03 | Admin inline configuration | `admin/generator.py` (473 lines) handles inline generation |
| AI-01 | LLM integration helpers | `ai/base.py` (492 lines), `ai/router.py`, `ai/streaming.py` |
| AI-02 | Embedding generation and storage | `ai/embeddings.py` (313 lines) |
| AI-03 | RAG pipeline utilities | `ai/rag.py` (789 lines) |
| AI-04 | IDE context generation for AI coding tools | `ai/ide/` and `ai/context/` directories exist |
| ML-01 | Vector storage with pgvector integration | `ai/vectorstore.py` (728 lines), `ml/` module |
| ML-02 | Structured output parsing from LLM responses | `ml/` module with llamacpp, localai, vllm backends |
| PERF-01 | Pagination: page number, limit/offset, cursor-based | `pagination/` with page_number.py, limit_offset.py, cursor.py |
| PERF-02 | Filtering backend with Django filter integration | `filtering/` with backends.py, filters.py, filterset.py, search.py |
| PERF-03 | Rate limiting / throttling | `throttling/` with backends.py, throttles.py, decorators.py, middleware.py |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| django | >=5.2.0 | Web framework | Base dependency |
| pydantic | >=2.0.0 | Schema validation | Base dependency |
| orjson | >=3.10.0 | JSON serialization | Base dependency, used everywhere |
| prometheus-client | optional | Metrics exposition | Industry standard Prometheus format |
| opentelemetry-sdk | optional | Distributed tracing | CNCF standard for observability |
| boto3 | optional | S3/R2/MinIO storage | AWS SDK, works with all S3-compatible |
| strawberry-graphql | optional | GraphQL schema | Django-native GraphQL library |
| celery | optional | Background tasks | Industry standard task queue |
| django-unfold | optional | Modern admin UI | Best modern Django admin theme |
| redis | >=6.4.0 | Cache/broker | Base dependency |

### Supporting (already available)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dramatiq | optional | Alternative task queue | When Celery is too heavy |
| django-q2 | optional | Simple task queue | When want Django-native tasks |
| ddtrace | optional | Datadog APM | When using Datadog |
| newrelic | optional | New Relic APM | When using New Relic |

### Alternatives Considered
None -- all libraries are already chosen and implemented. This phase is audit and completion, not selection.

## Architecture Patterns

### Module Structure (already established)
```
django_matt/
├── deploy/              # Provider-based deployment (Fly, Railway, Render, AWS)
│   ├── base.py          # DeploymentProvider ABC, DeploymentConfig
│   ├── docker.py        # DockerfileGenerator, ComposeGenerator
│   ├── environments.py  # Environment config with conn_max_age
│   └── providers/       # Individual platform providers
├── deployment/          # Kubernetes/Helm (separate from deploy/)
├── observability/       # Logging, metrics, tracing, middleware, views
├── audit/               # AuditLog model, AuditableMixin, middleware
├── db/soft_delete.py    # SoftDeleteMixin (separate from audit/)
├── files/               # Storage backends (S3, R2, MinIO, local)
├── tasks/               # Task backends (Celery, Dramatiq, Django-Q, sync)
├── graphql/             # Strawberry schema gen, dataloaders, views
├── admin/               # Unfold integration, dashboard, widgets
├── htmx/                # Response helpers, components, middleware
├── components/          # Backend-served component system
├── ai/                  # LLM integration, embeddings, RAG, IDE context
├── ml/                  # llamacpp, localai, vllm backends
├── pagination/          # PageNumber, LimitOffset, Cursor
├── filtering/           # FilterBackend, FilterSet, search
└── throttling/          # Rate limiting with backends
```

### Pattern 1: Optional Dependency Guards
**What:** All optional modules use try/except import with HAS_X flags
**When to use:** Every module with optional pip dependencies
**Example:**
```python
# Already established in observability/metrics.py
try:
    from prometheus_client import Counter, Histogram
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
```

### Pattern 2: Provider Registry
**What:** Deploy providers register via decorator and are retrieved by name
**When to use:** Deployment provider selection
**Example:**
```python
# Already established in deploy/base.py
@register_provider("fly")
class FlyioProvider(DeploymentProvider):
    ...
```

### Pattern 3: Async ORM Wrapping
**What:** Model classmethods use sync_to_async for async callers
**When to use:** All sync ORM in async codepaths (established in Phases 1, 4, 5, 6)
**Example:**
```python
# Already established in audit/models.py
@classmethod
async def alog(cls, action, user=None, obj=None, **kwargs):
    from asgiref.sync import sync_to_async
    return await sync_to_async(cls.log)(action, user, obj, **kwargs)
```

### Anti-Patterns to Avoid
- **Non-zero CONN_MAX_AGE in ASGI templates:** Django ticket #33497 -- persistent connections break under ASGI. Always use 0.
- **asyncio.get_event_loop() in storage backends:** `files/s3.py` uses `asyncio.get_event_loop()` which is deprecated in Python 3.12+. Should use `asyncio.get_running_loop()` or `asyncio.to_thread()`.
- **datetime.utcnow() usage:** `tasks/base.py` line 274 uses `datetime.utcnow()` -- should be `datetime.now(UTC)` (established fix from Phase 6).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Prometheus metrics | Custom metrics format | prometheus_client | Standard format, compatible with all scrapers |
| S3 operations | Custom HTTP to S3 | boto3 | Handles auth, retries, multipart, regions |
| GraphQL schema | Manual schema building | Strawberry | Type-safe, Django-integrated |
| OpenTelemetry | Custom tracing | opentelemetry-sdk | Industry standard, many exporters |
| Soft delete | Custom queryset manager | Existing `db/soft_delete.py` | Already implemented with restore, with_deleted, etc. |

**Key insight:** All modules are already implemented. The work is verification and gap-filling, not greenfield development.

## Common Pitfalls

### Pitfall 1: CONN_MAX_AGE in ASGI Deployments
**What goes wrong:** Non-zero CONN_MAX_AGE causes connection leaks under ASGI (Django ticket #33497)
**Why it happens:** Django's connection reuse uses thread IDs, meaningless in async
**How to avoid:** Set CONN_MAX_AGE=0 in ALL deployment templates, config generators, and environment configs
**Warning signs:** `deploy/environments.py` line 253 sets `conn_max_age: 600` for production env; `config/environments/production.py` defaults to 600; `config/settings/prod.py` uses `None`
**CRITICAL:** This is a known blocker from STATE.md -- must be systematically audited across ALL config files

### Pitfall 2: asyncio.get_event_loop() Deprecation
**What goes wrong:** `asyncio.get_event_loop()` emits DeprecationWarning in Python 3.12+ when no running loop exists
**Why it happens:** Old pattern from pre-3.10 Python
**How to avoid:** Use `asyncio.get_running_loop()` (inside async) or `asyncio.to_thread()` (for sync-to-async wrapping)
**Warning signs:** `files/s3.py` uses `loop = asyncio.get_event_loop()` in multiple methods

### Pitfall 3: datetime.utcnow() Usage
**What goes wrong:** Returns naive datetime, deprecated in Python 3.12
**Why it happens:** Old pattern
**How to avoid:** Use `datetime.now(UTC)` from `datetime` module
**Warning signs:** `tasks/base.py` line 274 and 286 use `datetime.utcnow()`

### Pitfall 4: SoftDelete Not Wired to Audit
**What goes wrong:** AUDIT-02 requires soft delete with restore, but `SoftDeleteMixin` is in `db/` not `audit/`
**Why it happens:** Separate module development
**How to avoid:** Tests must verify that soft-deleted records via SoftDeleteMixin are restorable and that audit logging works with soft-delete operations

### Pitfall 5: Test Isolation with Global Registries
**What goes wrong:** Task registry (`task_registry`), metrics manager (`metrics_manager`), and readiness checker (`readiness_checker`) are module-level singletons that leak between tests
**Why it happens:** Singleton pattern without test cleanup
**How to avoid:** Reset registries in test fixtures; use fresh CollectorRegistry for metrics tests

## Code Examples

### CONN_MAX_AGE Enforcement Pattern
```python
# All deploy providers and config generators must emit:
DATABASES = {
    "default": {
        ...
        "CONN_MAX_AGE": 0,  # Required for ASGI deployments
    }
}
```

### Audit + Soft Delete Test Pattern
```python
# Success criteria #3 verification
class Article(AuditableMixin, SoftDeleteMixin, models.Model):
    title = models.CharField(max_length=200)

# Create -> audit log with action=CREATE
article = Article.objects.create(title="Test")
assert AuditLog.objects.filter(action="create").exists()

# Update -> audit log with changes diff
article.title = "Updated"
article.save()
log = AuditLog.objects.filter(action="update").first()
assert "title" in log.changes

# Soft delete -> deleted_at set, record restorable
article.delete()
assert article.deleted_at is not None
article.restore()
assert article.deleted_at is None
```

### File Upload + Signed URL Test Pattern
```python
# Success criteria #4 verification
from unittest.mock import MagicMock, patch

storage = S3Storage(bucket="test", region="us-east-1", access_key="key", secret_key="secret")

with patch.object(storage, 'client') as mock_client:
    mock_client.put_object.return_value = {}
    key = await storage.save(b"file content", key="test.txt")

    mock_client.generate_presigned_url.return_value = "https://signed-url"
    url = await storage.presigned_download_url(key)
    assert url.url == "https://signed-url"
```

### Task Execution + Status Test Pattern
```python
# Success criteria #5 verification
from django_matt.tasks import task, TaskStatus

@task
def add(x, y):
    return x + y

# Sync execution
result = add.apply(args=(1, 2))
assert result.status == TaskStatus.SUCCESS
assert result.result == 3
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asyncio.get_event_loop()` | `asyncio.get_running_loop()` or `asyncio.to_thread()` | Python 3.10/3.12 | Deprecated warning in 3.12+ |
| `datetime.utcnow()` | `datetime.now(UTC)` | Python 3.12 | Deprecated, returns naive datetime |
| CONN_MAX_AGE=600 for ASGI | CONN_MAX_AGE=0 for ASGI | Django 4.1+ understanding | Connection leaks under async |
| Jaeger-specific exporter | OTLP exporter (universal) | OpenTelemetry 2023+ | Jaeger now supports OTLP natively |

**Deprecated/outdated:**
- `opentelemetry-exporter-jaeger` package: Jaeger now recommends OTLP protocol. The code in `tracing.py` imports it but with proper fallback.
- `asyncio.get_event_loop()` in `files/s3.py`: Must be replaced with `asyncio.to_thread()` for Python 3.12+ compatibility.

## Open Questions

1. **deploy/ vs deployment/ module split**
   - What we know: `deploy/` has providers (Fly, Railway, etc.) and `deployment/` has Kubernetes/Helm. Both exist.
   - What's unclear: Whether they should be consolidated
   - Recommendation: Leave as-is for now; both work. Focus on CONN_MAX_AGE enforcement in `deploy/`.

2. **SoftDeleteMixin integration with AuditableMixin**
   - What we know: SoftDeleteMixin is in `db/soft_delete.py`, AuditableMixin is in `audit/mixins.py`
   - What's unclear: Whether a model using both will have audit logs for soft-delete and restore operations
   - Recommendation: Test the combination; may need AuditableMixin.delete() to detect soft-delete and log appropriately

3. **ML module scope for v1**
   - What we know: `ml/` has llamacpp.py (1894 lines), localai.py (1241 lines), vllm.py (1533 lines)
   - What's unclear: How much testing/verification these need vs "it compiles"
   - Recommendation: ML-01 (vector storage) and ML-02 (structured output) focus on the interface, not deep integration testing of each LLM backend

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-django and pytest-asyncio |
| Config file | `pyproject.toml` (pytest section) |
| Quick run command | `uv run pytest tests/test_deploy.py tests/test_observability.py tests/test_audit.py tests/test_files.py tests/test_tasks.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-01 | Docker template with ASGI | unit | `uv run pytest tests/test_deploy.py -x -q` | Yes (1110 lines) |
| DEPLOY-06 | CONN_MAX_AGE=0 in all templates | unit | `uv run pytest tests/test_deploy.py -x -q -k conn` | Needs new tests |
| OBS-01 | Structured logging | unit | `uv run pytest tests/test_observability.py -x -q` | Yes (2500 lines) |
| OBS-02 | Prometheus metrics endpoint | unit | `uv run pytest tests/test_observability.py -x -q -k metrics` | Yes |
| OBS-03 | OTEL tracing spans | unit | `uv run pytest tests/test_observability.py -x -q -k tracing` | Yes |
| OBS-04 | Request inspector | unit | `uv run pytest tests/test_inspector.py -x -q` | Yes (592 lines) |
| AUDIT-01 | Audit log CRUD with diff | unit | `uv run pytest tests/test_audit.py -x -q` | Yes (1131 lines) |
| AUDIT-02 | Soft delete + restore | unit | `uv run pytest tests/test_audit.py -x -q -k soft` | Needs new tests |
| AUDIT-03 | Audit query API | unit | `uv run pytest tests/test_audit.py -x -q -k query` | Partial |
| FILE-01 | File upload validation | unit | `uv run pytest tests/test_files.py -x -q` | Yes (597 lines) |
| FILE-02-04 | S3/R2/MinIO backends | unit | `uv run pytest tests/test_files.py -x -q -k storage` | Needs mock tests |
| FILE-05 | Signed URL generation | unit | `uv run pytest tests/test_files.py -x -q -k presigned` | Needs new tests |
| TASK-01-03 | Celery/Dramatiq/Django-Q | unit | `uv run pytest tests/test_tasks.py -x -q` | Yes (942 lines) |
| TASK-04 | Task status retrieval | unit | `uv run pytest tests/test_tasks.py -x -q -k status` | Partial |
| GQL-01-03 | GraphQL schema + DataLoader | unit | `uv run pytest tests/test_graphql.py -x -q` | Yes (528 lines) |
| ADMIN-01-03 | Unfold admin integration | unit | `uv run pytest tests/test_admin_module.py -x -q` | Yes (1409 lines) |
| HTMX-01-02 | HTMX helpers | unit | `uv run pytest tests/test_htmx.py -x -q` | Yes (701 lines) |
| COMP-01 | Component system | unit | `uv run pytest tests/test_components.py -x -q` | Yes (551 lines) |
| AI-01-04 | AI/LLM integration | unit | `uv run pytest tests/test_ai_context.py -x -q` | Yes (583+274 lines) |
| ML-01-02 | Vector storage, structured output | unit | `uv run pytest tests/test_ml.py -x -q` | Yes (1073 lines) |
| PERF-01 | Pagination | unit | `uv run pytest tests/test_pagination.py -x -q` | Yes (642 lines) |
| PERF-02 | Filtering | unit | `uv run pytest tests/test_filtering.py -x -q` | Yes (744 lines) |
| PERF-03 | Throttling | unit | `uv run pytest tests/test_throttling.py -x -q` | Yes (802 lines) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_deploy.py tests/test_observability.py tests/test_audit.py tests/test_files.py tests/test_tasks.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps
- [ ] `tests/test_deploy.py` -- needs CONN_MAX_AGE=0 enforcement tests for ALL providers
- [ ] `tests/test_audit.py` -- needs soft-delete + restore with audit trail tests
- [ ] `tests/test_files.py` -- needs S3 mock storage + signed URL tests
- [ ] `tests/test_tasks.py` -- needs task execution + status retrieval success-criteria test

## Sources

### Primary (HIGH confidence)
- Project codebase inspection -- all module files read directly
- `.planning/STATE.md` -- known blocker: CONN_MAX_AGE misconfiguration
- `.planning/REQUIREMENTS.md` -- all 38 requirement IDs mapped
- `.planning/ROADMAP.md` -- phase 7 description and success criteria
- Django ticket #33497 (CONN_MAX_AGE ASGI bug) -- referenced in `.planning/research/PITFALLS.md`

### Secondary (MEDIUM confidence)
- Python 3.12 deprecation notices for `asyncio.get_event_loop()` and `datetime.utcnow()`
- OpenTelemetry Jaeger exporter deprecation in favor of OTLP

### Tertiary (LOW confidence)
- None -- all findings verified against project codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already chosen and in use
- Architecture: HIGH -- all modules already implemented, patterns established in prior phases
- Pitfalls: HIGH -- CONN_MAX_AGE blocker documented in STATE.md with Django ticket reference; Python deprecations well-known
- Gaps: HIGH -- direct code inspection identified specific missing pieces

**Research date:** 2026-03-08
**Valid until:** 2026-04-07 (stable -- brownfield audit of existing code)

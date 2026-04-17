# Django Matt — Next-Gen Framework Enhancements

> Design document covering 6 major feature areas to be implemented across multiple sessions.
> Each section is self-contained and can be implemented independently.

---

## 1. Smart Testing DX (`django_matt/testing/smart/`)

### Problem
4700+ tests. Full suite takes minutes. No way to run only what matters after a code change. No flaky test detection. No test replay for CI debugging.

### Design

#### 1A. Affected Test Detection (`pytest-matt` plugin)

Block-level test dependency tracking using coverage.py's branch-level instrumentation.

**How it works:**
1. First full run: instrument every test with `coverage.py`, record which source blocks (AST node ranges) each test touches. Store in `.matttest.db` (SQLite).
2. On subsequent runs: diff changed files at the AST block level (not line level — a comment change doesn't invalidate). Query `.matttest.db` for tests that depend on changed blocks.
3. Run only affected tests.

```python
# django_matt/testing/smart/tracker.py
class TestDependencyTracker:
    """Block-level test-to-source dependency tracking."""
    
    def __init__(self, db_path: Path = Path(".matttest.db")):
        self.db = sqlite3.connect(str(db_path))
        self._ensure_schema()
    
    def record_coverage(self, test_id: str, coverage_data: dict[str, set[int]]) -> None:
        """Record which source blocks a test executed."""
        ...
    
    def get_affected_tests(self, changed_files: list[Path]) -> list[str]:
        """Return test IDs whose dependency blocks changed."""
        ...
    
    def invalidate_file(self, path: Path) -> None:
        """Remove all dependency records for a file (forces re-run)."""
        ...

# django_matt/testing/smart/differ.py
class ASTBlockDiffer:
    """Compare two versions of a file at the AST block level."""
    
    def changed_blocks(self, old_source: str, new_source: str) -> set[tuple[int, int]]:
        """Return (start_line, end_line) ranges of changed AST nodes."""
        ...
```

**CLI:**
```bash
# Run only tests affected by changes since last commit
pytest --matt-affected

# Run only tests affected by changes in specific files
pytest --matt-affected --matt-changed=django_matt/auth/jwt.py

# Rebuild dependency database from scratch
pytest --matt-rebuild-deps

# Show which tests would run (dry run)
pytest --matt-affected --collect-only
```

**Django settings dependency:** If `DJANGO_SETTINGS_MODULE` content changes or `settings.py` is modified, invalidate ALL tests (settings are global dependencies).

#### 1B. Failed-Only Re-runs

```bash
# Re-run only tests that failed in the last run
pytest --matt-failed

# Re-run failed tests with verbose output
pytest --matt-failed -v

# Clear failure state
pytest --matt-clear-failures
```

Stores last-run failures in `.matttest.db` alongside dependency data. Simple but high-value for tight iteration loops.

#### 1C. Flaky Test Detection

```bash
# Stress-test a single test to find intermittent failures
pytest --matt-stress tests/test_auth.py::test_jwt_refresh --count=50

# Run full suite with automatic flaky classification
pytest --matt-detect-flaky --retries=3

# Show flaky test report
python manage.py matt test --flaky-report
```

**Classification logic:**
- Test fails on first run but passes on retry → marked `flaky` (not `failed`)
- Flaky tests stored with failure rate and stack traces in `.matttest.db`
- `--matt-quarantine` flag: run flaky tests separately, don't block CI

#### 1D. Test Replay Archives

```bash
# Record a test run as a portable archive
pytest --matt-record=run-2026-04-16.zip

# Replay a recorded run (reproduces exact environment + failures)
pytest --matt-replay=run-2026-04-16.zip

# CI integration: upload archive on failure
# In CI config: pytest --matt-record=$CI_JOB_ID.zip && upload-artifact
```

**Archive contains:**
- Event stream (test start/pass/fail/skip with timestamps)
- Captured stdout/stderr per test (zstd compressed)
- DB query log per test
- Python version, Django version, installed packages snapshot
- Git SHA + dirty diff

**Implementation:** pytest plugin with `pytest_runtest_protocol` hook that wraps each test in a recording context. Archive format is a ZIP with NDJSON event stream + per-test directories.

#### 1E. Management Command Integration

```bash
# Run affected tests through manage.py
python manage.py matt test --affected

# Run failed tests
python manage.py matt test --failed

# Full test suite with smart defaults
python manage.py matt test --smart
# (equivalent to: --affected if changes exist, else --failed if failures exist, else full suite)

# Show test health dashboard
python manage.py matt test --dashboard
```

### New files
```
django_matt/testing/smart/
    __init__.py
    tracker.py          # TestDependencyTracker — SQLite-backed dependency DB
    differ.py           # ASTBlockDiffer — block-level source comparison
    plugin.py           # pytest plugin (hooks for recording, affected detection, replay)
    recorder.py         # TestRecorder — archive creation/replay
    flaky.py            # FlakyDetector — stress testing + classification
    db.py               # Schema + migrations for .matttest.db
django_matt/management/commands/matt_test.py  # management command wrapper
```

### Estimated effort: 3 sessions

---

## 2. Code Advisor with LLM Prompt Generation (`django_matt/advisor/`)

### Problem
The `review/` engine detects 70+ rule violations but stops at "here's what's wrong." No health score trending. No actionable LLM prompts. Refactoring suggestions from `--ai` are collected but never rendered.

### Design

#### 2A. Code Health Score

Per-file and per-project numeric health score (1-10) that trends over commits.

```python
# django_matt/advisor/health.py
class CodeHealthScorer:
    """Calculate health scores from review findings."""
    
    # Weight matrix: (severity, category) -> deduction
    WEIGHTS = {
        (Severity.CRITICAL, Category.SECURITY): 3.0,
        (Severity.ERROR, Category.COMPLEXITY): 1.5,
        (Severity.WARNING, Category.PERFORMANCE): 0.5,
        ...
    }
    
    def score_file(self, findings: list[Finding], loc: int) -> FileHealth:
        """Score a single file. Returns FileHealth with score, grade, and breakdown."""
        ...
    
    def score_project(self, file_scores: list[FileHealth]) -> ProjectHealth:
        """Aggregate file scores into project health. Weighted by file size."""
        ...

class HealthTrend:
    """Track health scores over git commits."""
    
    def __init__(self, db_path: Path = Path(".matthealth.db")):
        self.db = sqlite3.connect(str(db_path))
    
    def record(self, commit_sha: str, scores: dict[str, FileHealth]) -> None: ...
    def trend(self, since: str = "HEAD~10") -> list[CommitHealth]: ...
    def regressions(self, since: str = "HEAD~1") -> list[HealthRegression]: ...
```

**CLI:**
```bash
# Show current project health
python manage.py matt health
# Output:
# Project Health: 7.2/10 (B+)
# ├── django_matt/auth/jwt.py          9.1 (A)
# ├── django_matt/core/controller.py   6.8 (C+)  ↓ from 7.4
# ├── django_matt/views/base.py        5.2 (D)   ↓ from 6.1
# └── 847 files scored
#
# Regressions since HEAD~1:
#   controller.py: +2 complexity findings (CX003, CX005)
#   base.py: +1 security finding (SEC004)

# Show trend over last 20 commits
python manage.py matt health --trend --since HEAD~20

# Fail CI if health drops below threshold
python manage.py matt health --fail-below 6.0

# JSON output for dashboards
python manage.py matt health --format json
```

#### 2B. LLM-Ready Refactoring Prompts

The core differentiator: for every finding above a severity threshold, generate a structured prompt that can be copy-pasted into an LLM or fed to an AI agent.

```python
# django_matt/advisor/prompts.py
class RefactorPromptGenerator:
    """Generate structured LLM prompts from review findings."""
    
    def generate(self, finding: Finding, source: str, context: FileContext) -> RefactorPrompt:
        """
        Returns a RefactorPrompt with:
        - summary: one-line description of what to fix
        - context: relevant source code (finding location + surrounding functions)
        - instructions: step-by-step refactoring instructions
        - prompt: ready-to-use LLM prompt text
        - constraints: things the refactoring must NOT break
        - verification: how to verify the refactoring worked
        """
        ...

@dataclass
class RefactorPrompt:
    finding_id: str           # e.g., "CX003"
    summary: str              # "Extract complex conditional logic in authenticate()"
    file_path: str
    line_range: tuple[int, int]
    context: str              # source code snippet
    instructions: str         # step-by-step human-readable instructions
    prompt: str               # ready-to-paste LLM prompt
    constraints: list[str]    # "Must maintain backward compatibility with jwt_required decorator"
    verification: str         # "Run: pytest tests/test_auth.py -v"
    estimated_effort: str     # "~15 minutes"
    priority: int             # 1-5, derived from health impact
```

**Example generated prompt:**
```markdown
## Refactor: Extract complex conditional logic in `authenticate()` [CX003]

**File:** django_matt/auth/jwt.py:145-198
**Health impact:** Fixing this improves file score from 6.8 → 7.9

### Context
```python
async def authenticate(self, request):
    # ... 53 lines of nested conditionals ...
```

### Instructions
1. Extract lines 156-172 into `_validate_token_claims(payload: dict) -> bool`
2. Extract lines 175-190 into `_resolve_user(user_id: int) -> User | None`
3. Replace the nested if/elif chain at lines 148-155 with an early-return guard clause pattern
4. The `_anonymous_user` singleton fallback on line 195 should remain in the main function

### Constraints
- `authenticate()` is called by `JWTMiddleware.process_request()` — signature must not change
- `request.auth_payload` must still be set before `_resolve_user` is called
- The `jwt_optional` decorator depends on `authenticate()` returning `None` (not raising) for missing tokens

### Verification
```bash
pytest tests/test_auth.py tests/test_middleware.py -v
```
```

**CLI:**
```bash
# Generate refactoring prompts for all findings
python manage.py matt advisor

# Generate prompts for specific file
python manage.py matt advisor django_matt/auth/jwt.py

# Generate prompts only for regressions
python manage.py matt advisor --regressions-only

# Output as JSON (for piping to AI agents)
python manage.py matt advisor --format json

# Output as markdown file
python manage.py matt advisor --format markdown --output advisor-report.md

# Only high-priority refactors
python manage.py matt advisor --min-priority 3

# Interactive mode: walk through each suggestion
python manage.py matt advisor --interactive
```

#### 2C. CI Integration

```yaml
# GitHub Actions example
- name: Code Health Gate
  run: python manage.py matt health --fail-below 6.0 --format github

- name: Refactor Suggestions
  if: failure()
  run: python manage.py matt advisor --regressions-only --format github
```

### New files
```
django_matt/advisor/
    __init__.py
    health.py           # CodeHealthScorer, HealthTrend
    prompts.py          # RefactorPromptGenerator, RefactorPrompt
    templates/          # Jinja2 templates for different prompt styles
        default.md.j2
        concise.md.j2
        agent.json.j2   # structured format for AI agents
    db.py               # Health trend SQLite schema
django_matt/management/commands/matt_advisor.py
django_matt/management/commands/matt_health.py
```

### Fixes to existing `review/`:
- Wire up `refactor_suggestions` rendering in console and markdown reporters
- Fix `api_design.py` auth check scoping bug (per-class, not per-file)
- Deduplicate overlapping findings across analyzers (sync ORM detected by 3 analyzers)
- Fix `ai_reviewer.py` category fallback (don't default unknown categories to SOLID)

### Estimated effort: 2 sessions

---

## 3. Batch & Async Request Handling (`django_matt/batch/`)

### Problem
No way to send multiple API requests in a single HTTP call. No request coalescing. No automatic N+1 resolution at runtime (only static AST detection).

### Design

#### 3A. HTTP Batch Endpoint (Facebook Graph API pattern)

Single endpoint that accepts an array of sub-requests, executes them (with dependency resolution), and returns all responses.

```python
# django_matt/batch/endpoint.py
class BatchEndpoint:
    """Facebook-style HTTP batch request handler."""
    
    def __init__(
        self,
        api: MattAPI,
        path: str = "/batch",
        max_requests: int = 50,
        timeout_per_request: float = 30.0,
        allow_dependencies: bool = True,
    ): ...
    
    async def handle(self, request: HttpRequest) -> JsonResponse:
        """
        Accepts:
        [
            {"method": "GET", "path": "/users/1", "name": "get_user"},
            {"method": "POST", "path": "/posts", "body": {"author_id": "{result=get_user:$.id}"}, 
             "depends_on": ["get_user"]},
            {"method": "GET", "path": "/users/1/posts", "name": "get_posts"}
        ]
        
        Returns:
        [
            {"status": 200, "body": {"id": 1, "name": "Matt"}, "headers": {...}},
            {"status": 201, "body": {"id": 42, "author_id": 1}, "headers": {...}},
            {"status": 200, "body": [{"id": 10}, {"id": 11}], "headers": {...}}
        ]
        """
        ...
```

**Key features:**
- **Named requests + JSONPath dependencies:** Request B can reference `{result=request_a:$.data.id}` in its path or body. The batch handler resolves dependencies topologically.
- **Parallel execution:** Independent requests (no `depends_on` relationship) execute concurrently via `asyncio.gather`.
- **Waterfall execution:** Dependent requests execute sequentially after their dependencies resolve.
- **Per-request error isolation:** If request 2 fails, requests 1 and 3 still return their results.
- **Shared DB transaction (optional):** `"atomic": true` in the batch request wraps all sub-requests in a single transaction.

```python
# Registration
from django_matt.batch import BatchEndpoint

api = MattAPI()
batch = BatchEndpoint(api, path="/batch", max_requests=50)
api.register_batch(batch)

# Or decorator style on any controller
class UserController(APIController):
    prefix = "/users"
    
    @api.batch("/batch")  # auto-wires batch endpoint scoped to this controller's routes
    async def batch(self, requests: list[BatchRequest]) -> list[BatchResponse]: ...
```

#### 3B. Request Coalescing Window

Automatically batch database queries that happen within the same event loop tick.

```python
# django_matt/batch/coalescer.py
class QueryCoalescer:
    """Automatic query batching within an event loop tick."""
    
    def __init__(self, window_ms: float = 0.0):  # 0 = same-tick coalescing
        self._pending: dict[str, list[CoalescedQuery]] = {}
        self._loop = asyncio.get_event_loop()
    
    async def load(self, model: type[Model], pk: Any) -> Model:
        """Register a load request. Actual DB query fires after the coalescing window."""
        ...
    
    async def load_many(self, model: type[Model], pks: list[Any]) -> list[Model]:
        """Batch multiple PKs into a single SELECT ... WHERE id IN (...)."""
        ...

# Usage in views — automatic via middleware
class OrderController(APIController):
    @api.get("/{order_id}")
    async def get_order(self, order_id: int):
        order = await self.coalescer.load(Order, order_id)
        # These two loads are coalesced into a single query:
        customer = await self.coalescer.load(Customer, order.customer_id)
        product = await self.coalescer.load(Product, order.product_id)
        return {"order": order, "customer": customer, "product": product}
```

#### 3C. Runtime N+1 Detection Middleware

```python
# django_matt/batch/n_plus_one.py
class NPlusOneMiddleware:
    """Detect N+1 queries at runtime by tracking query patterns per request."""
    
    # In dev mode: raises NPlusOneWarning with the offending query pattern
    # In prod mode: logs warning + emits metric
    
    def __init__(self, get_response, threshold: int = 5):
        self.threshold = threshold  # same query pattern repeated N times
    
    async def __call__(self, request):
        tracker = QueryPatternTracker()
        with connection.execute_wrapper(tracker.track):
            response = await get_response(request)
        
        duplicates = tracker.get_duplicates(threshold=self.threshold)
        if duplicates:
            for pattern, count in duplicates:
                logger.warning(f"N+1 detected: {pattern} executed {count} times")
                # In debug mode, also inject into response headers:
                # X-NPlusOne-Warning: SELECT ... FROM products WHERE id = %s (×47)
        
        return response
```

### New files
```
django_matt/batch/
    __init__.py
    endpoint.py         # BatchEndpoint — HTTP batch handler
    request.py          # BatchRequest, BatchResponse, BatchError dataclasses
    resolver.py         # DependencyResolver — topological sort + JSONPath interpolation
    coalescer.py        # QueryCoalescer — same-tick query batching
    n_plus_one.py       # NPlusOneMiddleware — runtime detection
    middleware.py       # BatchMiddleware — injects coalescer into request
```

### Estimated effort: 2 sessions

---

## 4. Migrations DX (`django_matt/migrations/`)

### Problem
Django migrations have no conflict prevention, no safe DDL rewriting, no dependency visualization, and `squashmigrations` is manual and fragile.

### Design

#### 4A. Online DDL Advisor

Automatically detect and rewrite unsafe migration operations into safe expand-contract sequences.

```python
# django_matt/migrations/advisor.py
class MigrationAdvisor:
    """Rewrite unsafe DDL operations into safe online-DDL sequences."""
    
    UNSAFE_PATTERNS = {
        # AddField NOT NULL without default → split into:
        #   1. ADD COLUMN NULL
        #   2. Backfill default value
        #   3. ALTER COLUMN SET NOT NULL (with NOT VALID + VALIDATE)
        "add_non_nullable": AddNonNullableRewriter,
        
        # AlterField type change → split into:
        #   1. ADD new column
        #   2. Dual-write trigger
        #   3. Backfill
        #   4. Switch reads
        #   5. Drop old column
        "alter_field_type": AlterFieldTypeRewriter,
        
        # CreateIndex without CONCURRENTLY → rewrite
        "create_index": ConcurrentIndexRewriter,
        
        # RemoveField that's referenced by index → drop index first
        "remove_indexed_field": RemoveIndexedFieldRewriter,
        
        # RenameField → add new + dual-write + migrate + drop old
        "rename_field": RenameFieldRewriter,
    }
    
    def analyze(self, migration_path: Path) -> list[MigrationIssue]: ...
    def rewrite(self, migration_path: Path) -> Path:
        """Generate a safe replacement migration file."""
        ...
```

**CLI:**
```bash
# Analyze pending migrations for safety issues
python manage.py matt migrate --check

# Auto-rewrite unsafe migrations into safe versions
python manage.py matt migrate --rewrite

# Preview what the safe version would look like
python manage.py matt migrate --rewrite --dry-run

# Output:
# ⚠ myapp/0015_add_email_verified.py
#   - AddField 'email_verified' BooleanField(default=False) NOT NULL
#   - This will lock the table for the duration of the backfill
#
# ✓ Safe rewrite generated: myapp/0015_add_email_verified_safe.py
#   Step 1: ADD COLUMN email_verified BOOLEAN NULL
#   Step 2: UPDATE myapp_user SET email_verified = false WHERE email_verified IS NULL (batched, 10k rows/batch)
#   Step 3: ALTER COLUMN email_verified SET NOT NULL
```

#### 4B. Migration Dependency Visualization

```bash
# Show migration dependency graph (ASCII in terminal)
python manage.py matt migrate --graph

# Output as DOT format for Graphviz
python manage.py matt migrate --graph --format dot > migrations.dot

# Show only migrations for a specific app
python manage.py matt migrate --graph --app myapp

# Detect and highlight circular dependencies
python manage.py matt migrate --graph --check-cycles
```

```python
# django_matt/migrations/graph.py
class MigrationGraphRenderer:
    """Render migration dependency graph."""
    
    def render_ascii(self, graph: MigrationGraph) -> str: ...
    def render_dot(self, graph: MigrationGraph) -> str: ...
    def render_mermaid(self, graph: MigrationGraph) -> str: ...
    def detect_cycles(self, graph: MigrationGraph) -> list[list[str]]: ...
    def find_conflicts(self, graph: MigrationGraph) -> list[MigrationConflict]: ...
```

#### 4C. State Hash Verification (Prisma-inspired)

```python
# django_matt/migrations/state_hash.py
class StateHashVerifier:
    """Verify migration state consistency using schema hashes."""
    
    def compute_schema_hash(self, state: ProjectState) -> str:
        """SHA256 of the canonical schema representation."""
        ...
    
    def verify_before_migrate(self, migration: Migration) -> bool:
        """Check that current DB state matches migration's expected from_hash."""
        ...
    
    def record_hash(self, migration_name: str, from_hash: str, to_hash: str) -> None:
        """Store state hash in django_matt_migration_hashes table."""
        ...
```

```bash
# Verify migration chain integrity
python manage.py matt migrate --verify

# Output:
# ✓ myapp/0001 → 0014: state hashes consistent
# ✗ myapp/0015: expected from_hash abc123, got def456
#   Likely cause: migration 0014 was modified after 0015 was created
```

#### 4D. Smart Squash

```bash
# Squash migrations with automatic conflict detection
python manage.py matt migrate --squash myapp 0001 0015

# Preview squash result
python manage.py matt migrate --squash myapp 0001 0015 --dry-run

# Squash all apps
python manage.py matt migrate --squash-all
```

### New files
```
django_matt/migrations/
    __init__.py
    advisor.py          # MigrationAdvisor — unsafe DDL detection + rewriting
    rewriters/
        __init__.py
        base.py         # BaseRewriter
        non_nullable.py # AddNonNullableRewriter
        field_type.py   # AlterFieldTypeRewriter
        concurrent.py   # ConcurrentIndexRewriter
        rename.py       # RenameFieldRewriter
    graph.py            # MigrationGraphRenderer — ASCII/DOT/Mermaid output
    state_hash.py       # StateHashVerifier — Prisma-style integrity checks
    squash.py           # SmartSquasher — improved squashmigrations
django_matt/management/commands/matt_migrate.py
```

### Estimated effort: 3 sessions

---

## 5. 2026+ Differentiators

### 5A. WASM Middleware Plugins (`django_matt/wasm/`)

Load `.wasm` files as middleware layers. Write middleware in Rust, Go, C, or any language that compiles to WASM. Zero other Python frameworks support this.

```python
# django_matt/wasm/middleware.py
class WasmMiddlewareLoader:
    """Load and execute WASM middleware modules via wasmtime-py."""
    
    def __init__(self, wasm_dir: Path = Path("middleware_wasm/")):
        self.engine = wasmtime.Engine()
        self.modules: dict[str, WasmMiddleware] = {}
    
    def load(self, path: Path) -> WasmMiddleware:
        """Compile and instantiate a WASM middleware module."""
        module = wasmtime.Module(self.engine, path.read_bytes())
        # Module must export: on_request(headers, body) -> (headers, body, action)
        #                     on_response(headers, body) -> (headers, body)
        ...
    
    def reload(self, name: str) -> None:
        """Hot-reload a WASM module without server restart."""
        ...

# Registration in settings
MATT_WASM_MIDDLEWARE = [
    "middleware_wasm/rate_limiter.wasm",    # Rust-compiled rate limiter
    "middleware_wasm/auth_validator.wasm",   # Go-compiled JWT validator
    "middleware_wasm/request_logger.wasm",   # C-compiled structured logger
]

# Or via Python API
from django_matt.wasm import WasmMiddlewareLoader

loader = WasmMiddlewareLoader()
loader.load(Path("middleware_wasm/rate_limiter.wasm"))
api.add_middleware(loader.as_django_middleware("rate_limiter"))
```

**Why this matters:** WASM middleware is hot-reloadable (no server restart), language-agnostic, sandboxed (can't access filesystem/network unless explicitly granted), and runs at near-native speed. A Rust rate limiter compiled to WASM can process 10M+ requests/sec.

**Dependency:** `wasmtime` (pip install wasmtime — pure Python wheel with embedded runtime)

### 5B. Request Replay Debugging (`django_matt/inspector/replay/`)

Extend the existing `inspector/` module to capture full request context and enable time-travel debugging.

```python
# django_matt/inspector/replay/recorder.py
class RequestRecorder:
    """Capture full request lifecycle for replay."""
    
    def record(self, request, response, queries, side_effects) -> RequestTrace:
        """
        Captures:
        - Full request (method, path, headers, body, user, auth)
        - All DB queries (SQL, params, duration, stack trace)
        - All Redis operations
        - All HTTP calls to external services
        - Full response (status, headers, body)
        - Timing data per phase (middleware, auth, handler, serialization)
        """
        ...

# django_matt/inspector/replay/player.py
class RequestReplayer:
    """Replay a recorded request trace against current code."""
    
    async def replay(self, trace: RequestTrace, mock_externals: bool = True) -> ReplayResult:
        """
        Re-execute the recorded request against current code.
        - DB queries are compared (same queries? different? new N+1?)
        - External HTTP calls are mocked with recorded responses
        - Response is compared (same shape? different values? new errors?)
        """
        ...
```

**CLI:**
```bash
# Enable recording in dev
MATT_INSPECTOR_RECORD=true python manage.py runserver

# Replay a specific request
python manage.py matt replay --trace-id abc123

# Replay all captured requests and diff responses
python manage.py matt replay --all --diff

# Export traces for sharing
python manage.py matt replay --export traces-2026-04-16.json
```

### 5C. Predictive Prefetching (`django_matt/prefetch/`)

Learn from request patterns to automatically prefetch related data.

```python
# django_matt/prefetch/learner.py
class AccessPatternLearner:
    """Track which related objects are accessed after initial queries."""
    
    # Observes: after fetching User, 90% of requests also fetch user.organization
    # Action: automatically add select_related("organization") to User queries
    
    def observe(self, model: type[Model], accessed_relations: list[str]) -> None: ...
    def suggest_prefetches(self, model: type[Model]) -> list[str]: ...
    def auto_optimize(self, queryset: QuerySet) -> QuerySet:
        """Apply learned prefetch patterns to a queryset."""
        ...

# Middleware integration
class PredictivePrefetchMiddleware:
    """Automatically apply learned prefetch patterns to all queries."""
    ...
```

### 5D. Automatic API Evolution (`django_matt/versioning/evolution/`)

Track which schema version each client last used. Serve old shape to old clients via transformation layer.

```python
# django_matt/versioning/evolution/tracker.py
class APIEvolutionTracker:
    """Track client schema versions and auto-transform responses."""
    
    def register_schema_change(
        self,
        path: str,
        version: str,
        transforms: list[SchemaTransform],
    ) -> None:
        """Register a breaking change with bidirectional transforms."""
        ...
    
    def transform_response(
        self,
        path: str,
        client_version: str,
        response_data: dict,
    ) -> dict:
        """Apply transforms to serve old schema shape to old clients."""
        ...

# Example: field renamed from "username" to "handle"
tracker.register_schema_change(
    path="/users/{id}",
    version="2026-04",
    transforms=[
        RenameField(old="username", new="handle"),
    ],
)
# Clients on version 2026-03 still see "username" in responses
# Clients on version 2026-04+ see "handle"
```

### 5E. Hot-Reload State Preservation (`django_matt/dev/`)

Preserve WebSocket connections and in-flight state across code reloads in development.

```python
# django_matt/dev/hot_reload.py
class StatefulReloader:
    """Preserve WebSocket state across code reloads."""
    
    # On file change:
    # 1. Serialize all active WebSocket consumer states
    # 2. Reload Python modules
    # 3. Reconstruct consumers with preserved state
    # 4. Send "reload" frame to connected clients (no reconnection needed)
    ...
```

### New files
```
django_matt/wasm/
    __init__.py
    middleware.py       # WasmMiddlewareLoader
    runtime.py          # WASM runtime management (engine, store, memory)
    abi.py              # Host function definitions (the ABI that WASM modules call)
    examples/           # Example WASM middleware sources (Rust)
django_matt/inspector/replay/
    __init__.py
    recorder.py         # RequestRecorder
    player.py           # RequestReplayer
    storage.py          # Trace storage (SQLite or file-based)
    differ.py           # Response diff engine
django_matt/prefetch/
    __init__.py
    learner.py          # AccessPatternLearner
    middleware.py        # PredictivePrefetchMiddleware
    storage.py          # Pattern storage (Redis or SQLite)
django_matt/versioning/evolution/
    __init__.py
    tracker.py          # APIEvolutionTracker
    transforms.py       # SchemaTransform types (RenameField, RemoveField, AddField, etc.)
    middleware.py        # VersionNegotiationMiddleware
django_matt/dev/
    __init__.py
    hot_reload.py       # StatefulReloader
```

### Estimated effort: 5 sessions (1 per sub-feature)

---

## 6. Rust Native Extensions — New Hot Paths

### Current Rust extensions
- `RadixRouter` — URL routing
- `jwt_encode/decode/verify` — JWT operations
- `parse_query_string` — query string parsing
- `parse_headers` — HTTP header parsing
- `serialize_dicts_to_json` / `serialize_dict_to_json` — JSON serialization
- `build_camel_case_map` — camelCase key mapping

### New Rust extensions to add

#### 6A. Rate Limiter (`rust/src/rate_limiter.rs`)

Atomic token-bucket rate limiting entirely off the GIL.

```rust
// Token bucket with sliding window
#[pyclass]
pub struct RateLimiter {
    buckets: DashMap<Vec<u8>, TokenBucket>,
    capacity: u32,
    refill_rate: f64,
}

#[pymethods]
impl RateLimiter {
    #[new]
    fn new(capacity: u32, refill_per_second: f64) -> Self { ... }
    
    /// Check if request is allowed. Returns (allowed, remaining, reset_at_ms)
    fn check(&self, key: &[u8]) -> (bool, u32, u64) { ... }
    
    /// Bulk check multiple keys at once
    fn check_many(&self, keys: Vec<&[u8]>) -> Vec<(bool, u32, u64)> { ... }
}
```

**Expected speedup:** 5-20x under load (no GIL contention, atomic operations, DashMap for concurrent access).

#### 6B. Permission Evaluator (`rust/src/permissions.rs`)

Compile permission expressions to bitfields, evaluate in nanoseconds.

```rust
#[pyclass]
pub struct PermissionEvaluator {
    // Pre-compiled permission expressions as bitfield operations
    expressions: Vec<CompiledExpression>,
}

#[pymethods]
impl PermissionEvaluator {
    /// Compile a permission expression tree
    fn compile(&mut self, expression: &str) -> usize { ... }
    
    /// Evaluate: does this user's permission bitfield satisfy expression N?
    fn evaluate(&self, expr_id: usize, user_permissions: u64) -> bool { ... }
    
    /// Bulk evaluate multiple expressions for one user
    fn evaluate_many(&self, expr_ids: Vec<usize>, user_permissions: u64) -> Vec<bool> { ... }
}
```

#### 6C. Schema Validator (`rust/src/validator.rs`)

Pre-compiled schema validation — like pydantic-core but tuned for django-matt's controller schemas.

```rust
#[pyclass]
pub struct SchemaValidator {
    // Pre-compiled validation rules per schema
    schemas: HashMap<String, CompiledSchema>,
}

#[pymethods]
impl SchemaValidator {
    /// Register a schema definition (called once at startup)
    fn register(&mut self, name: &str, schema_json: &str) -> PyResult<()> { ... }
    
    /// Validate request body against a registered schema
    /// Returns (valid_data: Option<PyDict>, errors: Vec<ValidationError>)
    fn validate(&self, schema_name: &str, data: &PyDict) -> PyResult<ValidationResult> { ... }
    
    /// Validate + coerce types in one pass (JSON bytes → validated dict)
    fn parse_and_validate(&self, schema_name: &str, body: &[u8]) -> PyResult<ValidationResult> { ... }
}
```

**Expected speedup:** 10-20x for request body validation (single Rust pass: parse JSON + validate types + check constraints + coerce values).

#### 6D. Middleware Chain (`rust/src/middleware.rs`)

Execute the middleware stack in Rust, calling back to Python only for middleware that needs it.

```rust
#[pyclass]
pub struct MiddlewareChain {
    // Ordered list of middleware processors
    // Some are pure Rust (rate limiting, header injection, CORS)
    // Some are Python callbacks (auth, business logic)
    layers: Vec<MiddlewareLayer>,
}

#[pymethods]
impl MiddlewareChain {
    fn add_rust_layer(&mut self, name: &str, config: &str) -> PyResult<()> { ... }
    fn add_python_layer(&mut self, callback: PyObject) -> PyResult<()> { ... }
    
    /// Process request through all layers
    /// Pure-Rust layers execute without GIL, Python layers acquire GIL only when reached
    fn process(&self, py: Python, headers: &[u8], body: &[u8]) -> PyResult<ProcessResult> { ... }
}
```

#### 6E. Query Builder (`rust/src/query_builder.rs`)

Build parameterized SQL from structured filter specs without Python string concatenation.

```rust
#[pyfunction]
pub fn build_select(
    table: &str,
    fields: Vec<&str>,
    filters: Vec<(&str, &str, PyObject)>,  // (field, op, value)
    order_by: Vec<(&str, bool)>,            // (field, desc)
    limit: Option<u32>,
    offset: Option<u32>,
) -> PyResult<(String, Vec<PyObject>)> { ... }

#[pyfunction]
pub fn build_filter_clause(
    filters: Vec<(&str, &str, PyObject)>,
) -> PyResult<(String, Vec<PyObject>)> { ... }
```

### New Rust files
```
rust/src/
    rate_limiter.rs     # Token bucket rate limiter (DashMap + atomics)
    permissions.rs      # Bitfield permission evaluator
    validator.rs        # Pre-compiled schema validator
    middleware.rs       # Middleware chain executor
    query_builder.rs    # SQL query builder

rust/fuzz/fuzz_targets/
    fuzz_rate_limiter.rs
    fuzz_validator.rs
    fuzz_query_builder.rs
```

### Cargo.toml additions
```toml
dashmap = "6"       # concurrent hashmap for rate limiter
serde_json = "1"    # schema validation
regex = "1"         # pattern matching in validator
```

### Estimated effort: 4 sessions (rate_limiter + permissions: 1, validator: 1, middleware: 1, query_builder: 1)

---

## Implementation Order (Recommended)

| Session | Feature | Why first |
|---------|---------|-----------|
| 1 | **2A-2B: Code Advisor + Health Score** | Builds on existing `review/` engine — fastest to ship, immediate value |
| 2 | **1A-1B: Affected Tests + Failed-Only** | Biggest daily DX improvement for 4700+ test suite |
| 3 | **3A: HTTP Batch Endpoint** | Novel feature, no framework has it, high visibility |
| 4 | **6A-6B: Rust Rate Limiter + Permissions** | Extends existing Rust infrastructure, clear perf wins |
| 5 | **4A-4B: Migration Advisor + Graph** | Safety net for production deploys |
| 6 | **1C-1D: Flaky Detection + Test Replay** | Polishes testing DX |
| 7 | **3B-3C: Query Coalescer + N+1 Runtime** | Deep async infrastructure |
| 8 | **6C: Rust Schema Validator** | Major perf win, complex to get right |
| 9 | **5A: WASM Middleware** | Biggest differentiator, needs careful ABI design |
| 10 | **5B: Request Replay Debugging** | Extends inspector, unique in Python ecosystem |
| 11 | **4C-4D: State Hash + Smart Squash** | Migration safety polish |
| 12 | **6D-6E: Rust Middleware Chain + Query Builder** | Deep Rust integration |
| 13 | **5C: Predictive Prefetching** | ML-adjacent, needs observation data first |
| 14 | **5D: API Evolution** | Versioning polish |
| 15 | **5E: Hot-Reload State Preservation** | Dev DX cherry on top |

---

## Summary of What Makes This Unique

**No other Python framework has:**
1. Block-level test impact analysis as a first-class feature
2. Test replay archives (portable `.zip` of a test run)
3. Code health trending with LLM-ready refactoring prompts
4. HTTP batch endpoint with JSONPath inter-request dependencies
5. Runtime N+1 detection middleware (not just static analysis)
6. WASM middleware plugins (hot-reloadable, language-agnostic)
7. Request replay debugging (time-travel for API bugs)
8. Predictive prefetching (learned access patterns → auto-optimization)
9. Automatic API evolution (versionless backward compatibility)
10. Rust rate limiter + permission evaluator + schema validator (off-GIL)
11. Online DDL migration advisor with auto-rewrite
12. State hash verification for migration integrity

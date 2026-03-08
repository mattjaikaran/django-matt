# Phase 5: Billing, Feature Flags, and Analytics - Research

**Researched:** 2026-03-08
**Domain:** Stripe/PayPal/Polar billing webhooks, feature flag evaluation, analytics aggregation, A/B experiments
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Webhook Handling**
- Signature verification failures: reject with 400, log with payload hash for debugging
- Built-in idempotency: track processed webhook event IDs in cache/DB, skip duplicates automatically
- Subscription lifecycle sync: auto-sync on webhook — handler creates/updates local Subscription model from provider event data, fires Django signal after sync for custom logic
- Mock event factories: provide `mock_stripe_event()`, `mock_paypal_event()`, `mock_polar_event()` with valid signatures for testing

**Flag Evaluation Strategy**
- Percentage rollouts: hash-based deterministic — `hash(flag_key + user_id) % 100 < percentage`, same user always gets same result
- Caching: TTL cache with configurable duration (default 30s), using Django cache framework (existing backends.py pattern)
- Org-scoping: flags are org-aware — `is_enabled()` accepts `organization` param, flags can target specific orgs via FlagOverride (aligns with Phase 4 multi-tenancy)
- `@feature_flag` decorator: returns 404 by default when flag disabled, configurable via `disabled_response` parameter

**Analytics Retention & Aggregation**
- Retention: configurable TTL via `ANALYTICS_RETENTION_DAYS` setting (default 90), management command + optional Celery task for cleanup
- Funnel analysis: defined steps — developer declares funnel steps, query returns conversion rate between steps
- Aggregation: on-read with caching — compute via Django ORM aggregation at query time, cache results with TTL
- Backends: DB default + pluggable — database backend ships by default, pluggable interface for external services (Mixpanel, Amplitude, etc.)

**Experiment Assignment & Stats**
- Assignment: hash-based with salt — `hash(experiment_id + user_id + salt) mod num_variants` for deterministic consistency
- Statistical tests: chi-squared for conversion metrics, z-test for proportions (standard A/B testing stats)
- Flag integration: experiments use feature flag VARIANT type — shared infrastructure via existing `flags_integration.py`
- `@experiment` decorator: auto-assigns user to variant and injects variant name as parameter to handler

### Claude's Discretion
- Exact webhook retry/backoff implementation details
- Cache key format for flag lookups and analytics aggregations
- Internal data structures for batch event tracking
- Error message formatting for billing provider errors
- Exact management command naming and flag design for analytics cleanup

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BILL-01 | Stripe integration — subscriptions, one-time payments, webhooks | StripeProvider (39k) exists; verify_webhook works; _handle_subscription_* stubs need real ORM sync |
| BILL-02 | PayPal integration — payments and webhooks | PayPalProvider (29k) exists; verify_webhook parses JSON; same lifecycle stub problem |
| BILL-03 | Polar integration — open-source-friendly billing | PolarProvider (26k) exists; HMAC-SHA256 webhook verification implemented; same lifecycle stub problem |
| BILL-04 | Billing controllers with subscription lifecycle management | BillingController (30k) exists; lifecycle handlers are stubs; need actual Subscription model sync |
| BILL-05 | Webhook handlers with signature verification | WebhookController._handle_webhook() implemented; mark_processed() uses sync .save() — broken in async context |
| FLAG-01 | Feature flag model with boolean/percentage/user-segment targeting | FeatureFlag model complete with FlagType (BOOLEAN/PERCENTAGE/VARIANT), targeting rules, scheduling |
| FLAG-02 | Database backend for feature flags | DatabaseBackend in backends.py (28k) — needs functional completeness audit |
| FLAG-03 | Redis backend for high-performance flag evaluation | RedisBackend exists in backends.py; tests skip because redis not imported properly |
| FLAG-04 | LaunchDarkly backend integration | LaunchDarklyBackend exists in backends.py; needs pytest.importorskip pattern |
| FLAG-05 | Unleash backend integration | UnleashBackend exists in backends.py; needs pytest.importorskip pattern |
| FLAG-06 | Feature flag decorators for views and controllers | @feature_flag, @requires_flag, @variant_flag all exist in decorators.py |
| FLAG-07 | Feature flag middleware for request-scoped flag evaluation | FlagMiddleware in middleware.py (7.8k) exists |
| ANLYT-01 | Event tracking with pluggable backends | EventTracker + DatabaseBackend complete; 43 passing tests |
| ANLYT-02 | Session tracking and user journey recording | AnalyticsSession model and middleware complete |
| ANLYT-03 | Funnel analysis with conversion tracking | Aggregator.analyze_funnel() exists in aggregations.py; no tests for funnel analysis |
| ANLYT-04 | Analytics aggregation queries (daily/weekly/monthly) | Aggregator class complete; no tests for get_event_metrics/get_page_metrics under db |
| EXP-01 | A/B test experiment model with variant assignment | Experiment, Variant, ExperimentAssignment models complete |
| EXP-02 | Multi-armed bandit assignment strategy | ExperimentManager with epsilon-greedy, UCB, Thompson sampling complete; 18 passing tests |
| EXP-03 | Statistical significance analysis for experiment results | StatisticalAnalyzer with chi-square, z-test, Wilson CI complete; 28 passing tests |
| EXP-04 | Experiment decorators for controller endpoints | experiments/decorators.py exists; @experiment decorator needs audit for variant injection pattern |
</phase_requirements>

---

## Summary

Phase 5 is a **completion and correctness audit phase**, not greenfield. All four modules (billing, flags, analytics, experiments) have substantial existing implementations. The work is: (1) fix the async ORM boundary violations exposed by real test runs, (2) implement the subscription lifecycle sync that is currently stub-only, (3) add the mock event factories for testing, (4) confirm the Redis/LaunchDarkly/Unleash backend tests are properly gated, (5) add funnel analysis tests, and (6) end-to-end test each of the five success criteria.

The most critical finding is that `WebhookEvent.mark_processed()` calls synchronous `self.save()` inside an async controller, causing `SynchronousOnlyOperation` errors. This is the same async/sync ORM boundary pattern fixed in Phase 1 for auth — the fix is `await sync_to_async(webhook_event.mark_processed)()` or converting `mark_processed` to an async method using `asave()`.

The second critical finding is that all subscription lifecycle handlers (`_handle_subscription_created/updated/canceled`) are logging stubs. The CONTEXT.md decision is explicit: these must auto-sync to the local `Subscription` model and fire a Django signal. This is the core of success criterion 1.

**Primary recommendation:** Plan 05-01 fixes async ORM violations in billing + implements subscription lifecycle sync + adds mock event factories and integration tests. Plans 05-02 and 05-03 audit flags/analytics/experiments and add the specific tests required by success criteria 2-5.

---

## Standard Stack

### Core (already in pyproject.toml as base deps)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| stripe | 14.2.0 | Stripe API + webhook verification | Already base dep; `stripe.Webhook.construct_event()` for signature check |
| redis | 6.4.0 | Redis backend for flags + cache | Already base dep; `redis.from_url()` for connection |
| django.core.cache | Django 5.2 | TTL cache for flag lookups | Built-in; no extra dep; cache framework already used in auth |
| django.dispatch | Django 5.2 | Django signals for post-webhook hooks | Built-in; standard Django pattern for extensibility |

### Optional (already in pyproject.toml optional extras)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ldclient-py | latest | LaunchDarkly backend | `pytest.importorskip("ldclient")` gates tests |
| UnleashClient | latest | Unleash backend | `pytest.importorskip("UnleashClient")` gates tests |

### No New Dependencies Required

All libraries this phase needs are already in `pyproject.toml` as base dependencies (`stripe`, `redis`) or optional extras. No `uv add` commands needed.

---

## Architecture Patterns

### Recommended Project Structure (existing, already correct)

```
django_matt/
├── billing/
│   ├── providers/base.py       # BillingProvider ABC + data classes
│   ├── providers/stripe.py     # StripeProvider (verify_webhook implemented)
│   ├── providers/paypal.py     # PayPalProvider (verify_webhook implemented)
│   ├── providers/polar.py      # PolarProvider (verify_webhook implemented)
│   ├── controllers.py          # BillingController + WebhookController (stubs to fix)
│   ├── models.py               # BillingCustomer, Subscription, Invoice, WebhookEvent
│   ├── config.py               # BillingConfig dataclass (singleton)
│   └── schemas.py              # Pydantic schemas
├── flags/
│   ├── backends.py             # FlagBackend ABC + DB/Redis/LD/Unleash implementations
│   ├── models.py               # FeatureFlag, FlagOverride, FlagAuditLog
│   ├── decorators.py           # @feature_flag, @requires_flag, @variant_flag
│   ├── middleware.py           # FlagMiddleware (request-scoped)
│   └── context.py              # FlagContext (ContextVar-based)
├── analytics/
│   ├── tracker.py              # EventTracker (batch + flush)
│   ├── aggregations.py         # Aggregator (funnel, metrics, cohort)
│   ├── backends.py             # AnalyticsBackend ABC + DatabaseBackend
│   └── models.py               # AnalyticsSession, AnalyticsEvent, PageView, Funnel
└── experiments/
    ├── manager.py              # ExperimentManager (assignment, bandits)
    ├── analysis.py             # StatisticalAnalyzer (chi-square, z-test)
    ├── flags_integration.py    # experiment_as_flag, sync_experiment_to_flag
    ├── decorators.py           # @experiment decorator
    └── models.py               # Experiment, Variant, ExperimentAssignment, ExperimentResult
```

### Pattern 1: Async ORM Boundary (the fix pattern used throughout the project)

**What:** Django sync model methods called inside async controllers must be wrapped.
**When to use:** Anytime a sync model method (`.save()`, `.mark_processed()`) is called from an async context.
**Example:**
```python
# BROKEN: WebhookEvent.mark_processed() calls self.save() — sync ORM
webhook_event.mark_processed()  # SynchronousOnlyOperation in async context

# FIX OPTION A: wrap with sync_to_async (Phase 1 established pattern)
from asgiref.sync import sync_to_async
await sync_to_async(webhook_event.mark_processed)()

# FIX OPTION B: convert to async method using asave()
async def amark_processed(self, error: str = "") -> None:
    self.processed = True
    self.processed_at = timezone.now()
    if error:
        self.processing_error = error
    await self.asave(update_fields=["processed", "processed_at", "processing_error"])
```

**Decision:** Use Option B (add `amark_processed()` async method) — cleaner API, no per-call overhead, consistent with Phase 1 pattern of converting sync methods to async in async callers.

### Pattern 2: Subscription Lifecycle Sync

**What:** Webhook event arrives → verify signature → parse provider data → update local Subscription model → fire Django signal.
**When to use:** On `subscription.created`, `subscription.updated`, `subscription.canceled`.
**Example:**
```python
# Source: billing/controllers.py _handle_subscription_created (to be implemented)
from django.dispatch import Signal

subscription_created = Signal()  # Fires after local Subscription record created/updated

async def _handle_subscription_created(self, provider: ProviderType, data: dict) -> None:
    """Handle subscription.created event — sync to local DB + fire signal."""
    provider_sub_id = data.get("id")
    if not provider_sub_id:
        return

    # Get or create the BillingCustomer by provider customer ID
    customer_id = data.get("customer")
    billing_customer = await BillingCustomer.objects.filter(
        **{f"{provider}_customer_id": customer_id}
    ).afirst()

    if not billing_customer:
        logger.warning(f"No BillingCustomer for {provider} customer {customer_id}")
        return

    # Upsert local Subscription record
    subscription, created = await Subscription.objects.aupdate_or_create(
        provider=provider,
        provider_subscription_id=provider_sub_id,
        defaults={
            "customer": billing_customer,
            "status": data.get("status", "active"),
            "current_period_start": _parse_ts(data.get("current_period_start")),
            "current_period_end": _parse_ts(data.get("current_period_end")),
            "cancel_at_period_end": data.get("cancel_at_period_end", False),
        },
    )

    # Fire Django signal for custom logic (user can connect handlers)
    from asgiref.sync import sync_to_async
    await sync_to_async(subscription_created.send)(
        sender=Subscription, subscription=subscription, created=created, raw_data=data
    )
```

### Pattern 3: Idempotent Webhook Processing

**What:** Use `WebhookEvent` model with `unique_together = [("provider", "provider_event_id")]` to deduplicate. Already implemented in `_handle_webhook()` via `aget_or_create`.
**Key detail:** The `aget_or_create` check is in place. The gap is only that `mark_processed()` is sync.

### Pattern 4: Mock Event Factories for Testing

**What:** Helper functions that produce valid webhook payloads with real HMAC signatures for testing without network calls.
**When to use:** In all webhook integration tests.
**Example:**
```python
# Source: to be added to billing/testing.py (new file) or billing/__init__.py
import hashlib
import hmac
import time
import orjson

def mock_stripe_event(
    event_type: str = "customer.subscription.created",
    data: dict | None = None,
    secret: str = "whsec_test_secret",
) -> tuple[bytes, str]:
    """Returns (payload_bytes, stripe_signature_header)."""
    payload = orjson.dumps({
        "id": f"evt_{event_type.replace('.', '_')}",
        "type": event_type,
        "data": {"object": data or {}},
    })
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode()}"
    signature = hmac.new(
        secret.encode(),
        signed_payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    header = f"t={timestamp},v1={signature}"
    return payload, header


def mock_polar_event(
    event_type: str = "subscription.created",
    data: dict | None = None,
    secret: str = "test_webhook_secret",
) -> tuple[bytes, str]:
    """Returns (payload_bytes, polar_signature_header)."""
    payload = orjson.dumps({
        "type": event_type,
        "data": data or {},
    })
    signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return payload, f"sha256={signature}"
```

### Pattern 5: Flag Evaluation with Caching

**What:** DatabaseBackend wraps `FeatureFlag.is_enabled_for_user()` with TTL cache using Django cache framework.
**Key detail:** Cache key must include `flag_key + user_id + org_id` for proper scoping.
**Example:**
```python
# Source: flags/backends.py DatabaseBackend (to be verified)
def _cache_key(self, flag_key: str, user_id: str = "", org_id: str = "") -> str:
    return f"flag:{flag_key}:{user_id}:{org_id}"

def is_enabled(self, key, user=None, organization=None, attributes=None, default=False):
    cache_key = self._cache_key(key, str(user.pk) if user else "", str(organization.pk if hasattr(organization, "pk") else organization) if organization else "")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    # DB lookup
    flag = FeatureFlag.objects.by_key(key)
    if flag is None:
        return default
    result = flag.is_enabled_for_user(user, organization, attributes)
    cache.set(cache_key, result, timeout=self.ttl)
    return result
```

### Pattern 6: Deterministic Experiment Assignment

**What:** Hash `experiment_id + user_id + salt` to assign variant deterministically. Already implemented in `experiments/manager.py`.
**Key detail:** The `@experiment` decorator must use the same assignment logic and inject variant name as a kwarg.

### Anti-Patterns to Avoid

- **Sync ORM in async handlers:** Never call `.save()`, `.get()`, `.create()` directly in `async def`. Always use `asave()`, `aget()`, `acreate()`, or `sync_to_async()`.
- **Missing `pytest.importorskip()`:** Optional backends (Redis, LaunchDarkly, Unleash) must gate on `pytest.importorskip()` — without it, missing packages cause collection errors instead of clean skips.
- **Rebuilding webhook signature logic:** Each provider already has a working `verify_webhook()`. The mock factory must match the exact HMAC algorithm used by the real provider.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stripe webhook signature verification | Custom HMAC logic | `stripe.Webhook.construct_event()` | Handles timestamp tolerance, v1/v2/v3 signature schemes, replay protection |
| PayPal webhook verification | Custom REST call | `paypal.py`'s existing JSON parse + optional verify | PayPal's verify endpoint requires OAuth; mock with JSON parse for tests |
| Statistical chi-square test | scipy.stats.chi2_contingency | `experiments/analysis.py`'s pure-Python impl | Already implemented without scipy dep; pure Python, no extra dep |
| Cache TTL management | Custom Redis TTL | `django.core.cache` with `timeout=` | Consistent with rest of codebase; backend-swappable |
| Funnel step queries | Raw SQL | Django ORM `annotate(Count)` + `filter` chaining | Already in `aggregations.py`; avoids N+1 |

---

## Common Pitfalls

### Pitfall 1: Sync ORM in Async Context (ACTIVE BUG)

**What goes wrong:** `WebhookEvent.mark_processed()` calls `self.save()` synchronously. When called from `async def _handle_webhook()`, Django raises `SynchronousOnlyOperation`. The test `TestWebhookController::test_handle_stripe_webhook_success` currently **fails** with this exact error.
**Why it happens:** `mark_processed()` was written as a sync model method (correct) but is called directly in an async controller without wrapping.
**How to avoid:** Add `async def amark_processed()` using `self.asave()`, or wrap with `sync_to_async`. Use the async variant in all async controllers.
**Warning signs:** `django.core.exceptions.SynchronousOnlyOperation` in test output or logs.

### Pitfall 2: Subscription Lifecycle Stubs Not Implemented

**What goes wrong:** All `_handle_subscription_*` methods are logging stubs. Success criterion 1 requires the `Subscription` model to be updated when a webhook arrives. The test will pass signature verification but the local DB will not reflect the subscription state.
**Why it happens:** Controllers.py was written with hooks for override but no default implementation.
**How to avoid:** Implement real `aupdate_or_create` calls in each handler. Fire Django signals after sync. Follow Phase 4 pattern of `filter(organization=...).afirst()` instead of global lookups.

### Pitfall 3: Redis Backend Tests Skip Due to Import Error

**What goes wrong:** `TestRedisBackend` tests skip with "could not import 'redis'" even though `redis` is now a base dependency. The skip comes from `pytest.importorskip("redis")` at the top of each test method — this is correct behavior when redis is not installed, but with redis as a base dep, these tests should now run.
**Why it happens:** After adding `redis` to base deps, these tests will run. If `RedisBackend.__init__` tries to `ping()` a live Redis server, tests will fail in CI without Redis.
**How to avoid:** Mock the Redis client in tests (`unittest.mock.patch`). Use `fakeredis` for integration-style Redis tests without a live server.

### Pitfall 4: Django Signal Sending in Async Context

**What goes wrong:** `Signal.send()` is synchronous. Calling it directly inside `async def _handle_subscription_created()` blocks the event loop.
**Why it happens:** Django signals predate async Django.
**How to avoid:** Wrap with `await sync_to_async(signal.send)(sender=..., **kwargs)`.

### Pitfall 5: Funnel Analysis Test Coverage Gap

**What goes wrong:** `Aggregator.analyze_funnel()` exists but has zero tests (grep confirms no "funnel" test in test_analytics.py). Success criterion 4 requires funnel conversion rate to be calculable — it needs a DB-level test.
**Why it happens:** The test file covers `EventTracker` and middleware thoroughly, but aggregation queries were never tested.
**How to avoid:** Add `@pytest.mark.django_db` tests that create `AnalyticsEvent` records and call `analyze_funnel()`, asserting step counts and conversion rates.

### Pitfall 6: Experiment `@experiment` Decorator Variant Injection

**What goes wrong:** Success criterion 5 requires `@experiment` to auto-assign user to variant and inject variant name as parameter. If the decorator uses positional args or a different kwarg name, handler signatures break.
**Why it happens:** The decorator in `experiments/decorators.py` exists but needs auditing to confirm it injects `variant` (or `variant_key`) as a kwarg that the handler can declare.
**How to avoid:** Test the decorator end-to-end with an async controller handler that declares `variant: str` as a parameter.

---

## Code Examples

### Stripe Webhook Verification (existing, verified working)

```python
# Source: django_matt/billing/providers/stripe.py
async def verify_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            self.config.webhook_secret,
        )
        return WebhookEvent(
            id=event["id"],
            type=event["type"],
            provider="stripe",
            data=event["data"]["object"],
            raw_payload=payload,
        )
    except stripe.error.SignatureVerificationError as e:
        raise BillingWebhookError(f"Invalid webhook signature: {e}")
```

### Async-Safe mark_processed (fix pattern)

```python
# Source: pattern established in Phase 1 (async ORM boundary)
# django_matt/billing/models.py — add alongside existing mark_processed()

async def amark_processed(self, error: str = "") -> None:
    """Mark this event as processed (async-safe version)."""
    self.processed = True
    self.processed_at = timezone.now()
    if error:
        self.processing_error = error
    await self.asave(update_fields=["processed", "processed_at", "processing_error"])
```

### Subscription Lifecycle Sync Pattern

```python
# Source: billing/controllers.py _handle_subscription_created (to be implemented)
async def _handle_subscription_created(self, provider: ProviderType, data: dict) -> None:
    from django_matt.billing.models import BillingCustomer, Subscription
    from asgiref.sync import sync_to_async

    provider_sub_id = data.get("id")
    customer_id = data.get("customer")
    if not provider_sub_id or not customer_id:
        return

    billing_customer = await BillingCustomer.objects.filter(
        **{f"{provider}_customer_id": customer_id}
    ).afirst()
    if not billing_customer:
        return

    subscription, created = await Subscription.objects.aupdate_or_create(
        provider=provider,
        provider_subscription_id=provider_sub_id,
        defaults={
            "customer": billing_customer,
            "status": data.get("status", Subscription.Status.ACTIVE),
            "current_period_start": _parse_timestamp(data.get("current_period_start")),
            "current_period_end": _parse_timestamp(data.get("current_period_end")),
            "cancel_at_period_end": data.get("cancel_at_period_end", False),
        },
    )

    # Fire signal for custom app logic
    from django.dispatch import Signal
    from django_matt.billing import subscription_synced
    await sync_to_async(subscription_synced.send)(
        sender=Subscription, subscription=subscription, provider=provider, raw_data=data
    )
```

### Deterministic Experiment Assignment (existing, verified)

```python
# Source: django_matt/experiments/manager.py ExperimentManager.assign_variant()
def _assign_variant(self, experiment: "Experiment", identifier: str) -> "Variant | None":
    """Assign user to variant using deterministic hash."""
    variants = list(experiment.variants.all().order_by("key"))
    if not variants:
        return None

    # Salt prevents correlation between experiments for same user
    hash_input = f"{experiment.key}:{identifier}:{experiment.metadata.get('salt', '')}"
    hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)

    if experiment.strategy == AssignmentStrategy.RANDOM.value:
        total_weight = sum(v.weight for v in variants)
        bucket = hash_value % total_weight
        cumulative = 0
        for variant in variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return variant

    return variants[0]
```

### Feature Flag @feature_flag Decorator (existing, correct)

```python
# Source: django_matt/flags/decorators.py
# Usage in controllers:
@feature_flag("my-flag")  # returns 404 when disabled
async def my_endpoint(request):
    return {"data": "value"}

@feature_flag("my-flag", disabled_response={"error": "maintenance"})
async def custom_disabled(request):
    return {"data": "value"}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Stripe API v1/v2 | Stripe API 2024-12-18.acacia | Config already set | Use `stripe.Webhook.construct_event()` not raw HMAC |
| scipy for stats | Pure Python chi-square/z-test | This codebase (custom) | No scipy dep; StatisticalAnalyzer is complete and tested |
| ldclient v5 | ldclient-py v9+ | 2023 | `import ldclient; ldclient.set_config(ldclient.Config(sdk_key))` |

**Deprecated/outdated:**
- `WebhookEvent.mark_processed()` (sync): superseded by `amark_processed()` (to be added) — only the sync version needed for non-async callers
- Stub lifecycle handlers: will be replaced with real ORM sync implementation

---

## Open Questions

1. **PayPal webhook signature verification**
   - What we know: PayPal's official webhook verification requires an async call to PayPal's API to validate the signature (or manual HMAC with the webhook ID). The current `paypal.py` implementation accepts any valid JSON as a signed webhook.
   - What's unclear: Whether to implement real PayPal HMAC verification or keep the current parse-only approach for tests.
   - Recommendation: Keep current approach (parse JSON, return event) for now — full PayPal HMAC verification requires the `WEBHOOK_ID` and a REST call. Log a TODO in the code and document that full verification requires live credentials.

2. **Django signals for billing events**
   - What we know: CONTEXT.md says "fires Django signal after sync for custom logic"
   - What's unclear: Where to define the signal objects — in `billing/__init__.py` (importable top-level) or `billing/signals.py`
   - Recommendation: Create `billing/signals.py` with `subscription_synced = Signal()`, `subscription_canceled = Signal()`, etc. Import and re-export from `billing/__init__.py`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-django, asyncio_mode=auto (no @pytest.mark.asyncio needed) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/test_billing.py tests/test_flags.py tests/test_analytics.py tests/test_experiments.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BILL-01 | Stripe webhook arrives, signature verified, subscription created/updated in DB | integration (db) | `uv run pytest tests/test_billing.py -k "webhook" -x` | ✅ (partial — sync bug blocks) |
| BILL-02 | PayPal webhook parsed and subscription lifecycle updated | integration (db) | `uv run pytest tests/test_billing.py -k "paypal" -x` | ✅ (partial) |
| BILL-03 | Polar webhook HMAC verified and subscription lifecycle updated | integration (db) | `uv run pytest tests/test_billing.py -k "polar" -x` | ✅ (partial) |
| BILL-04 | Subscription.status updated to "canceled" after cancel webhook | integration (db) | `uv run pytest tests/test_billing.py -k "subscription_lifecycle" -x` | ❌ Wave 0 |
| BILL-05 | 400 on bad signature, 200 on valid, idempotent duplicate skip | unit + integration | `uv run pytest tests/test_billing.py -k "webhook" -x` | ✅ |
| FLAG-01 | Boolean/percentage/variant flag model evaluates correctly | unit | `uv run pytest tests/test_flags.py -k "FeatureFlag" -x` | ✅ |
| FLAG-02 | DatabaseBackend.is_enabled() returns correct value with TTL cache | unit (mocked ORM) | `uv run pytest tests/test_flags.py -k "DatabaseBackend" -x` | ❌ Wave 0 |
| FLAG-03 | RedisBackend returns correct value for percentage rollout | unit (mocked redis) | `uv run pytest tests/test_flags.py -k "RedisBackend" -x` | ✅ (3 tests, currently skip) |
| FLAG-04 | LaunchDarklyBackend delegates to ldclient | unit (importorskip) | `uv run pytest tests/test_flags.py -k "LaunchDarkly" -x` | ❌ Wave 0 |
| FLAG-05 | UnleashBackend delegates to UnleashClient | unit (importorskip) | `uv run pytest tests/test_flags.py -k "Unleash" -x` | ❌ Wave 0 |
| FLAG-06 | @feature_flag returns 404 when disabled, 200 when enabled | unit | `uv run pytest tests/test_flags.py -k "feature_flag" -x` | ✅ |
| FLAG-07 | FlagMiddleware sets flag context on request | unit | `uv run pytest tests/test_flags.py -k "Middleware" -x` | ❌ Wave 0 |
| ANLYT-01 | EventTracker.track_event() stores event via backend | unit | `uv run pytest tests/test_analytics.py -k "track_event" -x` | ✅ |
| ANLYT-02 | AnalyticsMiddleware creates session, tracks page views | unit | `uv run pytest tests/test_analytics.py -k "middleware" -x` | ✅ |
| ANLYT-03 | Funnel with 3 steps returns conversion rates per step | integration (db) | `uv run pytest tests/test_analytics.py -k "funnel" -x` | ❌ Wave 0 |
| ANLYT-04 | get_event_metrics returns daily count breakdown | integration (db) | `uv run pytest tests/test_analytics.py -k "aggregat" -x` | ❌ Wave 0 |
| EXP-01 | Two users assigned to consistent variant across calls | unit | `uv run pytest tests/test_experiments.py -k "assignment" -x` | ❌ Wave 0 |
| EXP-02 | Multi-armed bandit selects variant per epsilon-greedy | unit | `uv run pytest tests/test_experiments.py -k "bandit" -x` | ✅ |
| EXP-03 | StatisticalAnalyzer.compare_variants() detects significance | unit | `uv run pytest tests/test_experiments.py -k "significance" -x` | ✅ (via compare_variants tests) |
| EXP-04 | @experiment injects variant kwarg into async handler | unit | `uv run pytest tests/test_experiments.py -k "decorator" -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_billing.py tests/test_flags.py tests/test_analytics.py tests/test_experiments.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_billing.py` — add `TestSubscriptionLifecycleSync` class: end-to-end webhook → DB sync for BILL-01/04
- [ ] `tests/test_billing.py` — fix `TestWebhookController::test_handle_stripe_webhook_success` (currently fails — sync ORM bug)
- [ ] `tests/test_billing.py` — add `mock_stripe_event()`, `mock_paypal_event()`, `mock_polar_event()` helper functions
- [ ] `tests/test_flags.py` — add `TestDatabaseBackend` class with TTL cache test (FLAG-02)
- [ ] `tests/test_flags.py` — add `TestLaunchDarklyBackend` with `pytest.importorskip("ldclient")` (FLAG-04)
- [ ] `tests/test_flags.py` — add `TestUnleashBackend` with `pytest.importorskip("UnleashClient")` (FLAG-05)
- [ ] `tests/test_flags.py` — add `TestFlagMiddleware` class (FLAG-07)
- [ ] `tests/test_analytics.py` — add `TestFunnelAnalysis` class with 3-step funnel test (ANLYT-03)
- [ ] `tests/test_analytics.py` — add `TestAggregatorDB` class with daily metrics test (ANLYT-04)
- [ ] `tests/test_experiments.py` — add `TestDeterministicAssignment` class verifying same user always gets same variant (EXP-01)
- [ ] `tests/test_experiments.py` — add `TestExperimentDecorator` class verifying variant kwarg injection (EXP-04)

---

## Sources

### Primary (HIGH confidence)

- Direct source code inspection: `django_matt/billing/controllers.py`, `billing/models.py`, `billing/providers/stripe.py` — confirmed sync ORM bug and stub handlers
- Direct test run: `uv run pytest tests/test_billing.py tests/test_flags.py tests/test_analytics.py tests/test_experiments.py` — confirmed 203 passing, 1 failing (`test_handle_stripe_webhook_success`)
- Django 5.2 async ORM docs (confirmed via Phase 1 decisions in STATE.md) — `asave()`, `acreate()`, `aupdate_or_create()` available since Django 4.1
- `experiments/analysis.py` — StatisticalAnalyzer is pure-Python chi-square + z-test, no scipy dep required

### Secondary (MEDIUM confidence)

- `stripe` SDK 14.x: `stripe.Webhook.construct_event()` is the canonical verification method — stable across v10-v14
- Redis 6.x client: `redis.from_url()` is the standard connection factory — unchanged since Redis 4.x

### Tertiary (LOW confidence)

- LaunchDarkly Python SDK v9 API: `ldclient.set_config()` + `ldclient.get()` — may have changed in v9; verify with `pytest.importorskip("ldclient")` gate

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stripe and redis are already base deps, no guessing about versions
- Architecture: HIGH — all modules exist, code read directly, one failing test confirmed
- Pitfalls: HIGH — failing test is a live reproduction of the main pitfall
- Test gaps: HIGH — manually inspected all test files to identify missing coverage

**Research date:** 2026-03-08
**Valid until:** 2026-06-08 (stable domain — Stripe API version pinned in config, Django 5.2 LTS)

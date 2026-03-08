# Phase 5: Billing, Feature Flags, and Analytics - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete Stripe/PayPal/Polar billing with webhook verification and subscription lifecycle management. Complete feature flags with DB/Redis/LaunchDarkly/Unleash backends, decorators, and middleware. Complete analytics event tracking with session aggregation and funnel analysis. Complete A/B experiments with deterministic assignment and statistical significance analysis.

All four modules have substantial existing code — this is a completion/audit phase, not greenfield.

</domain>

<decisions>
## Implementation Decisions

### Webhook Handling
- Signature verification failures: reject with 400, log with payload hash for debugging
- Built-in idempotency: track processed webhook event IDs in cache/DB, skip duplicates automatically
- Subscription lifecycle sync: auto-sync on webhook — handler creates/updates local Subscription model from provider event data, fires Django signal after sync for custom logic
- Mock event factories: provide `mock_stripe_event()`, `mock_paypal_event()`, `mock_polar_event()` with valid signatures for testing

### Flag Evaluation Strategy
- Percentage rollouts: hash-based deterministic — `hash(flag_key + user_id) % 100 < percentage`, same user always gets same result
- Caching: TTL cache with configurable duration (default 30s), using Django cache framework (existing backends.py pattern)
- Org-scoping: flags are org-aware — `is_enabled()` accepts `organization` param, flags can target specific orgs via FlagOverride (aligns with Phase 4 multi-tenancy)
- `@feature_flag` decorator: returns 404 by default when flag disabled, configurable via `disabled_response` parameter

### Analytics Retention & Aggregation
- Retention: configurable TTL via `ANALYTICS_RETENTION_DAYS` setting (default 90), management command + optional Celery task for cleanup
- Funnel analysis: defined steps — developer declares funnel steps, query returns conversion rate between steps
- Aggregation: on-read with caching — compute via Django ORM aggregation at query time, cache results with TTL
- Backends: DB default + pluggable — database backend ships by default, pluggable interface for external services (Mixpanel, Amplitude, etc.)

### Experiment Assignment & Stats
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

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Key success criteria are well-defined:
1. Stripe webhook signature verification + subscription lifecycle test with mock payload
2. Redis backend percentage rollout test
3. `@feature_flag("my-flag")` returns 404 when disabled, normal response when enabled
4. Analytics event tracking + session aggregation + funnel conversion rate test
5. A/B experiment deterministic assignment + statistical significance test

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `billing/providers/base.py`: BillingProvider ABC with all data classes (CustomerData, SubscriptionData, WebhookEvent, etc.)
- `billing/providers/stripe.py` (39k), `paypal.py` (29k), `polar.py` (26k): Substantial provider implementations
- `billing/controllers.py` (30k): Full REST endpoints for checkout, subscriptions, customers, invoices, webhooks
- `flags/backends.py` (28k): All four backends (DB, Redis, LD, Unleash) with FlagBackend ABC
- `flags/models.py` (20k): FeatureFlag model with FlagType (BOOLEAN/PERCENTAGE/VARIANT), FlagOverride model
- `flags/decorators.py` (11k): `@feature_flag` decorator and related helpers
- `flags/middleware.py` (7.8k): Request-scoped flag evaluation
- `analytics/tracker.py` (19k): EventTracker with batch support
- `analytics/aggregations.py` (28k): Aggregation query builders
- `analytics/backends.py` (37k): Pluggable backend architecture
- `experiments/models.py` (21k): Experiment, Variant, ExperimentAssignment, ExperimentResult models
- `experiments/analysis.py` (19k): Statistical analysis module
- `experiments/flags_integration.py` (11k): Experiment-flag bridge

### Established Patterns
- Provider pattern: ABC base + concrete implementations per provider (billing/providers/)
- Backend pattern: ABC base + concrete implementations per storage (flags/backends.py, analytics/backends.py)
- Config pattern: `@dataclass` config loaded from Django settings (billing/config.py)
- Decorator pattern: function decorators wrapping controller endpoints (flags/decorators.py, experiments/decorators.py)
- Async-first: all controller handlers are async, sync ORM wrapped via `sync_to_async()`

### Integration Points
- Billing controllers register on MattAPI via `api.register_controller(BillingController, prefix="/billing")`
- Flags middleware integrates in Django MIDDLEWARE list
- Analytics middleware tracks page views automatically
- Experiments tie into flags via `flags_integration.py`
- Multi-tenancy: org parameter flows through from Phase 4 middleware to flag/analytics checks

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-billing-feature-flags-and-analytics*
*Context gathered: 2026-03-08*

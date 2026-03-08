---
phase: 05-billing-feature-flags-and-analytics
plan: 01
subsystem: payments
tags: [stripe, paypal, polar, webhooks, django-signals, async-orm, testing]

# Dependency graph
requires:
  - phase: 04-auth-hardening-and-multi-tenancy
    provides: async ORM patterns, sync_to_async usage, async test patterns

provides:
  - WebhookEvent.amark_processed() async method (no SynchronousOnlyOperation)
  - Real subscription lifecycle sync (Stripe/PayPal/Polar -> local Subscription model)
  - Django signals for subscription events (subscription_synced, subscription_canceled, invoice_paid, webhook_received)
  - Mock event factories for webhook testing (mock_stripe_event, mock_paypal_event, mock_polar_event)
  - End-to-end webhook lifecycle tests (TestWebhookLifecycleSync, 13 tests)

affects: [05-02-feature-flags, 05-03-analytics, 06-websockets-messaging, saas-examples]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - aupdate_or_create pattern for idempotent webhook-to-DB sync
    - sync_to_async(signal.send) for firing Django signals from async handlers
    - Module-level get_provider usage (not local import) so mock patches work in tests
    - hmac.new + orjson.dumps for deterministic mock payload generation

key-files:
  created:
    - django_matt/billing/signals.py
    - django_matt/billing/testing.py
  modified:
    - django_matt/billing/models.py
    - django_matt/billing/controllers.py
    - django_matt/billing/__init__.py
    - tests/test_billing.py

key-decisions:
  - "amark_processed uses asave(update_fields=[...]) — targeted async write, no full model reload"
  - "webhook_received signal fires BEFORE sync (allows pre-processing hooks); subscription_synced fires AFTER"
  - "_process_webhook_event removed local get_provider import — module-level import required for @patch mocking"
  - "mock_stripe_event uses t={ts}.{payload} HMAC signing matching Stripe's exact algorithm"
  - "mock_paypal_event builds transmission_id|time|webhook_id|crc32 message matching PayPal's verification"
  - "Subscription created without BillingCustomer logs warning and returns (no crash) — missing customer is a data-sync race, not a hard error"

patterns-established:
  - "Async webhook handler pattern: verify -> aget_or_create WebhookEvent -> fire webhook_received -> process -> amark_processed"
  - "Signal firing from async: await sync_to_async(signal.send)(sender=Model, **kwargs)"
  - "Testing mock factory tuple return: (payload_bytes, signature_header_string)"

requirements-completed: [BILL-01, BILL-02, BILL-03, BILL-04, BILL-05]

# Metrics
duration: 25min
completed: 2026-03-08
---

# Phase 5 Plan 01: Billing Webhook Lifecycle Sync Summary

**Webhook-to-DB pipeline for all three providers (Stripe/PayPal/Polar): async ORM fix, real subscription sync, Django signals, and mock factories with 13 end-to-end tests.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-08T06:00:00Z
- **Completed:** 2026-03-08T06:25:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Fixed `SynchronousOnlyOperation` bug: `WebhookEvent.mark_processed()` (sync) blocked async handlers; added `amark_processed()` using `asave()`
- Implemented real subscription lifecycle handlers (previously logging stubs): `_handle_subscription_created/updated/canceled` each call `Subscription.objects.aupdate_or_create` and fire `subscription_synced` signal
- Created `billing/signals.py` with 4 signals: `subscription_synced`, `subscription_canceled`, `invoice_paid`, `webhook_received`
- Created `billing/testing.py` with 3 mock factories that produce valid HMAC-signed payloads matching each provider's exact verification algorithm
- Added 13 end-to-end tests in `TestWebhookLifecycleSync` covering BILL-01 through BILL-05

## Task Commits

1. **Task 1: Fix async ORM + lifecycle handlers + signals + testing factories** - `7dc3b16` (feat)
2. **Task 2: End-to-end webhook lifecycle tests** - `c75a7c6` (test)

## Files Created/Modified

- `django_matt/billing/models.py` - Added `amark_processed()` async method to `WebhookEvent`
- `django_matt/billing/controllers.py` - Fixed `amark_processed`, implemented 3 subscription handlers + invoice handler, added `_parse_timestamp` helper, removed duplicate local import, added `webhook_received` signal fire
- `django_matt/billing/signals.py` - New file: 4 Django signals for billing lifecycle events
- `django_matt/billing/testing.py` - New file: 3 mock event factories (Stripe, PayPal, Polar)
- `django_matt/billing/__init__.py` - Re-exports signals and testing helpers with `__all__` entries
- `tests/test_billing.py` - Added `TestWebhookLifecycleSync` class (13 tests)

## Decisions Made

- `amark_processed` uses `asave(update_fields=[...])` — targeted write without full model reload
- `webhook_received` signal fires before processing (pre-hook); `subscription_synced` fires after sync (post-hook)
- `_process_webhook_event` uses module-level `get_provider` (not local import) so `@patch("django_matt.billing.controllers.get_provider")` patches work correctly in tests
- Mock factories return `(payload_bytes, signature)` tuples using exact HMAC algorithms matching provider specs
- Missing BillingCustomer during sync logs a warning and returns rather than raising — data-sync race condition is non-fatal

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Local `get_provider` import inside `_process_webhook_event` bypassed mock patches**
- **Found during:** Task 2 (running tests — `test_stripe_webhook_creates_subscription` failed with BillingConfigError)
- **Issue:** The method had `from django_matt.billing.providers import get_provider` locally, which bypassed the module-level `@patch("django_matt.billing.controllers.get_provider")` decorator in tests
- **Fix:** Removed local import; method now uses the module-level `get_provider` already imported at the top
- **Files modified:** `django_matt/billing/controllers.py`
- **Verification:** All 13 `TestWebhookLifecycleSync` tests pass after fix
- **Committed in:** `c75a7c6` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary correctness fix. No scope creep.

## Issues Encountered

- Pre-existing test failure: `TestPayPalProvider::test_verify_webhook_valid_json` (line 1500) was failing before this plan's changes because `PayPalProvider.verify_webhook` requires PAYPAL-TRANSMISSION-* headers but the test didn't provide them. Logged to deferred-items (out of scope per deviation rule boundary — pre-existing failure in unrelated test).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Billing webhook pipeline is complete and tested; ready for 05-02 (feature flags) and 05-03 (analytics)
- Signals allow saas-starter and other examples to hook into subscription events without subclassing controllers
- Mock factories enable fast testing in any downstream plan that exercises billing webhooks

---
*Phase: 05-billing-feature-flags-and-analytics*
*Completed: 2026-03-08*

## Self-Check: PASSED

- FOUND: django_matt/billing/signals.py
- FOUND: django_matt/billing/testing.py
- FOUND: django_matt/billing/models.py (with amark_processed)
- FOUND: django_matt/billing/controllers.py (with aupdate_or_create x3)
- FOUND: .planning/phases/05-billing-feature-flags-and-analytics/05-01-SUMMARY.md
- FOUND commit: 7dc3b16 (feat task 1)
- FOUND commit: c75a7c6 (test task 2)
- FOUND commit: 32f730e (docs metadata)

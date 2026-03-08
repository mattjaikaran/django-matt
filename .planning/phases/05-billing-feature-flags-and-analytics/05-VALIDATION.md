---
phase: 5
slug: billing-feature-flags-and-analytics
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-django, asyncio_mode=auto |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_billing.py tests/test_flags.py tests/test_analytics.py tests/test_experiments.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_billing.py tests/test_flags.py tests/test_analytics.py tests/test_experiments.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | BILL-01 | integration | `uv run pytest tests/test_billing.py -k "webhook" -x` | ✅ (partial) | ⬜ pending |
| 05-01-02 | 01 | 1 | BILL-02 | integration | `uv run pytest tests/test_billing.py -k "paypal" -x` | ✅ (partial) | ⬜ pending |
| 05-01-03 | 01 | 1 | BILL-03 | integration | `uv run pytest tests/test_billing.py -k "polar" -x` | ✅ (partial) | ⬜ pending |
| 05-01-04 | 01 | 1 | BILL-04 | integration | `uv run pytest tests/test_billing.py -k "subscription_lifecycle" -x` | ❌ W0 | ⬜ pending |
| 05-01-05 | 01 | 1 | BILL-05 | unit+integration | `uv run pytest tests/test_billing.py -k "webhook" -x` | ✅ | ⬜ pending |
| 05-02-01 | 02 | 1 | FLAG-01 | unit | `uv run pytest tests/test_flags.py -k "FeatureFlag" -x` | ✅ | ⬜ pending |
| 05-02-02 | 02 | 1 | FLAG-02 | unit | `uv run pytest tests/test_flags.py -k "DatabaseBackend" -x` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 1 | FLAG-03 | unit | `uv run pytest tests/test_flags.py -k "RedisBackend" -x` | ✅ (skip) | ⬜ pending |
| 05-02-04 | 02 | 1 | FLAG-04 | unit | `uv run pytest tests/test_flags.py -k "LaunchDarkly" -x` | ❌ W0 | ⬜ pending |
| 05-02-05 | 02 | 1 | FLAG-05 | unit | `uv run pytest tests/test_flags.py -k "Unleash" -x` | ❌ W0 | ⬜ pending |
| 05-02-06 | 02 | 1 | FLAG-06 | unit | `uv run pytest tests/test_flags.py -k "feature_flag" -x` | ✅ | ⬜ pending |
| 05-02-07 | 02 | 1 | FLAG-07 | unit | `uv run pytest tests/test_flags.py -k "Middleware" -x` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | ANLYT-01 | unit | `uv run pytest tests/test_analytics.py -k "track_event" -x` | ✅ | ⬜ pending |
| 05-03-02 | 03 | 2 | ANLYT-02 | unit | `uv run pytest tests/test_analytics.py -k "middleware" -x` | ✅ | ⬜ pending |
| 05-03-03 | 03 | 2 | ANLYT-03 | integration | `uv run pytest tests/test_analytics.py -k "funnel" -x` | ❌ W0 | ⬜ pending |
| 05-03-04 | 03 | 2 | ANLYT-04 | integration | `uv run pytest tests/test_analytics.py -k "aggregat" -x` | ❌ W0 | ⬜ pending |
| 05-03-05 | 03 | 2 | EXP-01 | unit | `uv run pytest tests/test_experiments.py -k "assignment" -x` | ❌ W0 | ⬜ pending |
| 05-03-06 | 03 | 2 | EXP-02 | unit | `uv run pytest tests/test_experiments.py -k "bandit" -x` | ✅ | ⬜ pending |
| 05-03-07 | 03 | 2 | EXP-03 | unit | `uv run pytest tests/test_experiments.py -k "significance" -x` | ✅ | ⬜ pending |
| 05-03-08 | 03 | 2 | EXP-04 | unit | `uv run pytest tests/test_experiments.py -k "decorator" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_billing.py` — add `TestSubscriptionLifecycleSync` class for BILL-01/04
- [ ] `tests/test_billing.py` — fix `test_handle_stripe_webhook_success` (sync ORM bug)
- [ ] `tests/test_billing.py` — add `mock_stripe_event()`, `mock_paypal_event()`, `mock_polar_event()` helpers
- [ ] `tests/test_flags.py` — add `TestDatabaseBackend` class with TTL cache test (FLAG-02)
- [ ] `tests/test_flags.py` — add `TestLaunchDarklyBackend` with `pytest.importorskip("ldclient")` (FLAG-04)
- [ ] `tests/test_flags.py` — add `TestUnleashBackend` with `pytest.importorskip("UnleashClient")` (FLAG-05)
- [ ] `tests/test_flags.py` — add `TestFlagMiddleware` class (FLAG-07)
- [ ] `tests/test_analytics.py` — add `TestFunnelAnalysis` class with 3-step funnel test (ANLYT-03)
- [ ] `tests/test_analytics.py` — add `TestAggregatorDB` class with daily metrics test (ANLYT-04)
- [ ] `tests/test_experiments.py` — add `TestDeterministicAssignment` class (EXP-01)
- [ ] `tests/test_experiments.py` — add `TestExperimentDecorator` class (EXP-04)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PayPal webhook HMAC verification with live API | BILL-02 | Requires live PayPal REST call for cert validation | Mock tests cover parsing; live verification documented as limitation |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

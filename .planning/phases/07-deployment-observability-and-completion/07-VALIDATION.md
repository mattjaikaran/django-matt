---
phase: 07
slug: deployment-observability-and-completion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q --timeout=10` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | DEPLOY-01..06 | unit | `uv run pytest tests/test_deployment.py -x -q` | ✅ | ⬜ pending |
| 07-02-01 | 02 | 1 | OBS-01..04 | unit | `uv run pytest tests/test_observability.py -x -q` | ✅ | ⬜ pending |
| 07-03-01 | 03 | 1 | AUDIT-01..03 | unit | `uv run pytest tests/test_audit.py -x -q` | ✅ | ⬜ pending |
| 07-03-02 | 03 | 1 | FILE-01..05 | unit | `uv run pytest tests/test_files.py -x -q` | ✅ | ⬜ pending |
| 07-03-03 | 03 | 1 | TASK-01..04 | unit | `uv run pytest tests/test_tasks.py -x -q` | ✅ | ⬜ pending |
| 07-04-01 | 04 | 2 | ADMIN-01..03, GQL-01..03 | unit | `uv run pytest tests/test_admin.py tests/test_graphql.py -x -q` | ✅ | ⬜ pending |
| 07-04-02 | 04 | 2 | HTMX-01..02, COMP-01 | unit | `uv run pytest tests/test_htmx.py tests/test_components.py -x -q` | ✅ | ⬜ pending |
| 07-04-03 | 04 | 2 | AI-01..04, ML-01..02 | unit | `uv run pytest tests/test_ai.py tests/test_ml.py -x -q` | ✅ | ⬜ pending |
| 07-05-01 | 05 | 3 | PERF-01..03 | unit | `uv run pytest tests/test_performance.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fly.io/Railway deploy | DEPLOY-03..04 | Requires live platform accounts | Inspect generated configs for ASGI + CONN_MAX_AGE settings |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

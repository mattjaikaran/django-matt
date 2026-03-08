---
phase: 6
slug: real-time-notifications-and-communications
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_websockets.py tests/test_messaging.py tests/test_notifications.py tests/test_email_service.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_websockets.py tests/test_messaging.py tests/test_notifications.py tests/test_email_service.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | RT-01 | unit | `uv run pytest tests/test_websockets.py -x -q` | ✅ | ⬜ pending |
| 06-01-02 | 01 | 1 | RT-02 | unit | `uv run pytest tests/test_websockets.py -x -q` | ✅ | ⬜ pending |
| 06-01-03 | 01 | 1 | RT-03 | unit | `uv run pytest tests/test_websockets.py -x -q` | ✅ | ⬜ pending |
| 06-02-01 | 02 | 1 | MSG-01 | unit | `uv run pytest tests/test_messaging.py -x -q` | ✅ | ⬜ pending |
| 06-02-02 | 02 | 1 | MSG-02 | unit | `uv run pytest tests/test_messaging.py -x -q` | ✅ | ⬜ pending |
| 06-02-03 | 02 | 1 | MSG-03 | unit/async | `uv run pytest tests/test_messaging.py -x -q` | ✅ | ⬜ pending |
| 06-03-01 | 03 | 1 | NOTIF-01 | unit | `uv run pytest tests/test_notifications.py -x -q` | ✅ | ⬜ pending |
| 06-03-02 | 03 | 1 | NOTIF-02 | unit | `uv run pytest tests/test_notifications.py -x -q` | ✅ | ⬜ pending |
| 06-03-03 | 03 | 1 | NOTIF-03 | unit | `uv run pytest tests/test_notifications.py -x -q` | ✅ | ⬜ pending |
| 06-03-04 | 03 | 1 | NOTIF-04 | unit | `uv run pytest tests/test_notifications.py -x -q` | ✅ | ⬜ pending |
| 06-03-05 | 03 | 1 | NOTIF-05 | unit | `uv run pytest tests/test_notifications.py -x -q` | ✅ | ⬜ pending |
| 06-03-06 | 03 | 1 | EMAIL-01 | unit | `uv run pytest tests/test_email_service.py -x -q` | ✅ | ⬜ pending |
| 06-03-07 | 03 | 1 | EMAIL-02 | unit | `uv run pytest tests/test_email_service.py -x -q` | ✅ | ⬜ pending |
| 06-03-08 | 03 | 1 | EMAIL-03 | unit | `uv run pytest tests/test_email_service.py -x -q` | ✅ | ⬜ pending |
| 06-03-09 | 03 | 1 | EMAIL-04 | unit | `uv run pytest tests/test_email_service.py -x -q` | ✅ | ⬜ pending |
| 06-03-10 | 03 | 1 | EMAIL-05 | unit | `uv run pytest tests/test_email_service.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* Test files already exist:
- `tests/test_websockets.py` — 728 lines
- `tests/test_messaging.py` — 300 lines (enums/schemas only — needs model/service/consumer tests)
- `tests/test_notifications.py` — 833 lines
- `tests/test_email_service.py` — 1009 lines

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

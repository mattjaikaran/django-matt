---
phase: 4
slug: auth-hardening-and-multi-tenancy
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_auth.py tests/test_blacklist.py tests/test_multitenancy.py -x -q --tb=short` |
| **Full suite command** | `uv run pytest tests/ -x -q --tb=short` |
| **Estimated runtime** | ~45 seconds (quick), ~120 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_auth.py tests/test_blacklist.py tests/test_multitenancy.py -x -q --tb=short`
- **After every plan wave:** Run `uv run pytest tests/ -x -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | AUTH-02 | integration | `uv run pytest tests/test_blacklist.py -x` | ✅ partial | ⬜ pending |
| 04-01-02 | 01 | 1 | AUTH-02 | integration | `uv run pytest tests/test_auth.py -k "change_password" -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | AUTH-12 | integration | `uv run pytest tests/test_auth.py -k "csrf" -x` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | AUTH-06, AUTH-07 | integration | `uv run pytest tests/test_auth.py -k "password_reset or magic_link" -x` | ✅ | ⬜ pending |
| 04-01-05 | 01 | 1 | AUTH-11 | unit | `uv run pytest tests/test_auth_api_keys.py -x` | ✅ | ⬜ pending |
| 04-02-01 | 02 | 1 | AUTH-08 | integration | `uv run pytest tests/test_auth_oauth.py -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | AUTH-09 | integration + unit | `uv run pytest tests/test_auth_sso.py -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 1 | AUTH-10 | unit | `uv run pytest tests/test_auth_passkeys.py -x` | ✅ | ⬜ pending |
| 04-03-01 | 03 | 2 | TENANT-01, TENANT-02 | integration | `uv run pytest tests/test_multitenancy.py -k "Organization or Team" -x` | ✅ partial | ⬜ pending |
| 04-03-02 | 03 | 2 | TENANT-03, AUTH-04 | unit | `uv run pytest tests/test_multitenancy.py -k "permission or membership" -x` | ❌ W0 | ⬜ pending |
| 04-03-03 | 03 | 2 | TENANT-04 | unit | `uv run pytest tests/test_multitenancy.py -k "MiddlewareAsync" -x` | ❌ W0 | ⬜ pending |
| 04-03-04 | 03 | 2 | TENANT-05 | integration | `uv run pytest tests/test_multitenancy.py -k "non_member" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth.py::test_logout_blacklists_token` — stub for AUTH-02 logout revocation
- [ ] `tests/test_auth.py::test_change_password_revokes_old_tokens` — stub for AUTH-02 bulk revocation
- [ ] `tests/test_auth.py::test_jwt_endpoint_no_csrf_required` — stub for AUTH-12
- [ ] `tests/test_multitenancy.py::TestTenantMiddlewareAsync` — stubs for TENANT-04
- [ ] `tests/test_multitenancy.py::test_non_member_gets_403` — stub for TENANT-05
- [ ] `tests/test_multitenancy.py::TestOrgPermissionClasses` — stubs for IsOrgMember/IsOrgAdmin/IsOrgOwner
- [ ] `tests/test_auth_oauth.py::TestOAuthGoogleIntegration` — stub for AUTH-08
- [ ] `tests/test_auth_oauth.py::TestOAuthGitHubIntegration` — stub for AUTH-08
- [ ] `tests/test_auth_sso.py::TestOIDCIntegration` — stub for AUTH-09

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

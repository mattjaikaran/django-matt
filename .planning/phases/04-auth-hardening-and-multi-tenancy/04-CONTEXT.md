# Phase 4: Auth Hardening and Multi-Tenancy - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden JWT revocation, CSRF safety, and password flows; verify OAuth/SSO/Passkeys work end-to-end; wire Organization/Team/Membership with org-scoped API access. Most code already exists — this phase fixes gaps, adds async parity to multitenancy, wires subsystems together, and proves correctness with integration tests.

Requirements: AUTH-01 through AUTH-13, TENANT-01 through TENANT-05.

</domain>

<decisions>
## Implementation Decisions

### Token revocation policy
- Default blacklist backend: **cache** (Django cache — Redis in prod, locmem in dev). No DB migration needed, auto-expires with TTL.
- Revocation triggers: logout, password change (revokes ALL active tokens for user), and admin revoke-all endpoint
- Admin revoke-all endpoint access: Claude's discretion based on permission patterns
- Safety warnings: both `matt doctor` Warning-tier check AND Django startup warning when `DEBUG=False` and blacklist backend is `"null"`

### Org-token binding
- Default mode: **middleware-only** — org resolved per-request via X-Organization-ID header, URL kwarg, or session. Tokens stay org-agnostic.
- Optional strict mode: config flag enables org_id embedded in JWT claims. Switching orgs requires new token pair.
- Multi-org user without explicit org: Claude's discretion (middleware already supports last-used org via session)
- Org switch in strict mode: new full token pair (access + refresh) scoped to new org
- Old org-scoped tokens on switch: Claude's discretion based on cache backend capabilities

### Tenant isolation strictness
- Cross-org access response: **403 Forbidden** (explicit denial, standard B2B SaaS pattern)
- Query scoping: **auto-scope by default** — tenant-aware controllers automatically filter querysets by org. Opt-out for admin/superuser views.
- Permission classes: **both** org-aware permission classes (IsOrgMember, IsOrgAdmin, IsOrgOwner) AND async-compatible decorators. Classes for controller-level, decorators for method-level.
- Superuser bypass: **configurable** — `TENANT_SUPERUSER_BYPASS=True` by default. Can be disabled for strict multi-tenant deployments.

### Auth flow testing priorities
- OAuth: Google + GitHub get full integration tests. Apple + Microsoft get unit tests (shared base pattern).
- SSO: OIDC full integration test. SAML basic unit tests (XML parsing/validation, no full flow).
- Passkeys: `pytest.importorskip('webauthn')` — skip gracefully when not installed
- Rate limiting on auth endpoints: Claude's discretion — assess whether basic auth rate limiting belongs here or deferred to Phase 7 throttling module (PERF-03)

### Claude's Discretion
- Admin revoke-all endpoint: superuser-only vs superuser + org admin (for their org)
- Multi-org user default org resolution strategy
- Org switch token blacklisting behavior in strict mode
- Auth endpoint rate limiting: implement here or defer to Phase 7
- Async migration approach for multitenancy controllers (full rewrite vs sync_to_async wrappers)
- Whether `allow_any` decorator flag should be wired into controller dispatch or left as-is

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The user wants production-quality security defaults that work out of the box.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `auth/blacklist/`: Full backend system (Null/Cache/DB) with public API in `core.py` — needs default change from null to cache
- `auth/jwt.py`: Complete token lifecycle with sync+async parity — needs `change_password` to call bulk revocation
- `auth/decorators/`: All handle async/sync detection via `inspect.iscoroutinefunction` — model for multitenancy decorator async support
- `auth/controllers.py`: `AuthController` with full endpoint set — reference pattern for multitenancy controller refactor
- `multitenancy/middleware.py`: Both sync and async variants exist — async variant (`TenantMiddlewareAsync`) needs test coverage
- `multitenancy/decorators.py`: 7 decorators implemented but sync-only — need async wrapper pattern from auth decorators
- `multitenancy/controllers.py`: 4 controllers fully implemented but sync — need async conversion
- `permissions/common.py`: Base permission classes — need org-aware additions (IsOrgMember, IsOrgAdmin, IsOrgOwner)
- `auth/schemas.py`: `TokenPayload` already has `org_id: str | None` field — ready for strict mode population

### Established Patterns
- Sync/async detection: `inspect.iscoroutinefunction(func)` in decorator wrappers (auth/decorators/)
- Permission classes: `BasePermission.has_permission(request, view)` + `has_object_permission(request, view, obj)`
- Error responses: `JsonResponse({"detail": ..., "code": ...}, status=...)` consistent format
- Config pattern: `DJANGO_MATT_*` settings dict with dataclass config (JWTConfig, MagicLinkConfig, etc.)
- Optional deps: `pytest.importorskip()` for test-time, custom error classes with install hints at runtime

### Integration Points
- `auth/jwt.py` `create_access_token` / `acreate_access_token`: add optional `org_id` claim for strict mode
- `auth/controllers.py` `change_password`: wire bulk token revocation after password change
- `multitenancy/middleware.py`: TenantMiddleware connects to `request.organization` — controllers read from this
- `permissions/common.py`: New org permission classes integrate with controller `permission_classes` list
- `auth/session/csrf.py`: CSRF exemption for JWT endpoints — verify correct in router/URL config

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-auth-hardening-and-multi-tenancy*
*Context gathered: 2026-03-07*

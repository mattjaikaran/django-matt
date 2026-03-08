# Phase 4: Auth Hardening and Multi-Tenancy - Research

**Researched:** 2026-03-07
**Domain:** Django async auth, JWT revocation, CSRF, OAuth/SSO/Passkeys, multi-tenant B2B permissions
**Confidence:** HIGH (all findings from direct codebase inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Token revocation policy**
- Default blacklist backend: **cache** (Django cache — Redis in prod, locmem in dev). No DB migration needed, auto-expires with TTL.
- Revocation triggers: logout, password change (revokes ALL active tokens for user), and admin revoke-all endpoint
- Admin revoke-all endpoint access: Claude's discretion based on permission patterns
- Safety warnings: both `matt doctor` Warning-tier check AND Django startup warning when `DEBUG=False` and blacklist backend is `"null"`

**Org-token binding**
- Default mode: **middleware-only** — org resolved per-request via X-Organization-ID header, URL kwarg, or session. Tokens stay org-agnostic.
- Optional strict mode: config flag enables org_id embedded in JWT claims. Switching orgs requires new token pair.
- Multi-org user without explicit org: Claude's discretion (middleware already supports last-used org via session)
- Org switch in strict mode: new full token pair (access + refresh) scoped to new org
- Old org-scoped tokens on switch: Claude's discretion based on cache backend capabilities

**Tenant isolation strictness**
- Cross-org access response: **403 Forbidden** (explicit denial, standard B2B SaaS pattern)
- Query scoping: **auto-scope by default** — tenant-aware controllers automatically filter querysets by org. Opt-out for admin/superuser views.
- Permission classes: **both** org-aware permission classes (IsOrgMember, IsOrgAdmin, IsOrgOwner) AND async-compatible decorators. Classes for controller-level, decorators for method-level.
- Superuser bypass: **configurable** — `TENANT_SUPERUSER_BYPASS=True` by default. Can be disabled for strict multi-tenant deployments.

**Auth flow testing priorities**
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | JWT authentication with access and refresh token flow | Exists and works — jwt.py fully implemented |
| AUTH-02 | JWT token blacklist with bulk purge for revocation | Blacklist system exists; default is "null" — must change to "cache"; bulk revocation (for password change) is MISSING |
| AUTH-03 | Session-based authentication for browser clients | session/ module exists; CSRFMiddleware and session backend implemented |
| AUTH-04 | Permission classes: IsAuthenticated, IsAdmin, IsOwner, HasRole, HasPermission | All exist in permissions/common.py — need org-aware additions |
| AUTH-05 | RBAC — role-based access control with role assignment and checking | auth/rbac/ module exists; needs verification of correctness |
| AUTH-06 | Password reset via email link flow | Implemented in AuthController.request_password_reset + confirm |
| AUTH-07 | Magic link passwordless login | Implemented in AuthController; averify_magic_link_token is async |
| AUTH-08 | OAuth provider login (Google, GitHub, and extensible for others) | auth/oauth/ module exists; needs integration test for Google + GitHub |
| AUTH-09 | SSO / SAML integration | auth/sso/ module exists; needs OIDC integration test + SAML unit tests |
| AUTH-10 | Passkey / WebAuthn authentication | auth/passkeys/ module exists; pytest.importorskip guard needed |
| AUTH-11 | API key authentication with scoped permissions | auth/api_keys/ module exists |
| AUTH-12 | CSRF exemption correctly applied for JWT-authenticated API endpoints | CSRFMiddleware lives in session/ module; JWT endpoints need `_csrf_exempt` flag via router |
| AUTH-13 | Permission decorators: @jwt_required, @jwt_optional, @requires_role(), @requires_permission() | Decorators exist in auth/decorators/; async-aware via inspect.iscoroutinefunction |
| TENANT-01 | Organization model with create/read/update/delete | Organization model fully implemented; controllers are sync-only — need async conversion |
| TENANT-02 | Team model with membership management | Team + TeamMembership models fully implemented |
| TENANT-03 | Membership model with role-based team permissions | Membership model fully implemented with role hierarchy |
| TENANT-04 | Tenant-aware middleware scoping queries to current organization | Both TenantMiddleware (sync) and TenantMiddlewareAsync exist; async variant lacks test coverage |
| TENANT-05 | Tenant-aware controllers with automatic organization filtering | Controllers exist (4) but are sync-only; need async conversion and org-scoped queryset helpers |
</phase_requirements>

---

## Summary

Phase 4 is a hardening and wiring phase, not a build-from-scratch phase. Nearly all subsystems already exist:
JWT, blacklist, session, CSRF, OAuth, SSO, Passkeys, API keys, RBAC, Organization/Team/Membership models,
middleware, controllers, and decorators. The gaps are specific and well-bounded:

1. **JWT bulk revocation is missing.** `change_password` issues new tokens but does NOT blacklist the user's
   existing tokens. There is no `revoke_all_tokens_for_user()` function. The blacklist default is `"null"`,
   meaning revocation is silently disabled unless the operator explicitly configures it. This must be fixed:
   default to `"cache"`, add bulk revocation, and add startup/doctor warnings when misconfigured.

2. **Multitenancy controllers are 100% sync.** `OrganizationController`, `TeamController`,
   `MembershipController`, and `InvitationController` all use synchronous ORM calls (`objects.get()`,
   `.save()`, etc.) with no `async def` or `sync_to_async` wrapping. They will block the event loop
   in async Django. Full async rewrite using `aget()`, `asave()`, `aexists()`, etc. is the correct approach.

3. **Org-aware permission classes don't exist.** `permissions/common.py` has `IsAuthenticated`, `IsAdmin`,
   `IsOwner`, `HasRole`, `HasPermission` — but no `IsOrgMember`, `IsOrgAdmin`, `IsOrgOwner`. These classes
   need to be added to bridge the multitenancy decorators to the controller `permission_classes` list pattern.

4. **Multitenancy decorators are sync-only.** The 7 decorators in `multitenancy/decorators.py` all use
   sync wrappers. They need the `inspect.iscoroutinefunction(func)` async detection pattern from
   `auth/decorators/jwt.py` to work with async controller methods.

5. **CSRF exemption is not wired to JWT endpoints in the router.** The `CSRFMiddleware` in session/ checks
   `request._csrf_exempt` and `view.func._csrf_exempt`, but the MattAPI router does not set this flag.
   JWT-authenticated endpoints must be verified to bypass CSRF middleware correctly.

6. **Auth integration tests are weak for OAuth/SSO/Passkeys.** Unit tests exist, but the required
   "logs in via OAuth (Google) and via magic link — both flows complete" integration test is missing.

**Primary recommendation:** Proceed in three sub-phases — (a) JWT hardening (blacklist default + bulk
revocation + CSRF wiring), (b) multitenancy async conversion + org permission classes, (c) auth integration
tests.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 5.2+ | ORM, middleware, settings, test client | Project baseline |
| Python | 3.12+ | Async/await, type hints | Project baseline |
| Pydantic v2 | 2.x | Schema validation | Project baseline |
| orjson | latest | JSON serialization | Project baseline — mandatory base dep |
| asgiref | bundled | sync_to_async, async_to_sync | Required for ASGI Django |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-django | latest | Django test integration | All tests |
| pytest-asyncio (asyncio_mode=auto) | latest | Async test support | All async tests — no @pytest.mark.asyncio needed |
| python-jose / webauthn | optional | Passkeys library | Only when webauthn installed; pytest.importorskip guard |
| redis-py / django-redis | optional | Production Redis cache | Real revocation in prod; locmem used in tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Cache blacklist | Database blacklist | Cache is faster, auto-expiring, no migration; DB required for cross-process clusters without shared cache |
| sync_to_async wrappers | Full async rewrite | Full async rewrite preferred — wrappers add thread overhead and obscure the intent; rewrite once and maintain clearly |
| Middleware-only org resolution | JWT claim embedding | JWT embedding is opt-in strict mode; middleware-only is the default per CONTEXT.md |

**Installation:** No new packages needed. All dependencies already in the project.

---

## Architecture Patterns

### Recommended Project Structure (existing — no changes needed)
```
django_matt/
├── auth/
│   ├── blacklist/
│   │   ├── config.py          # BlacklistConfig reads DJANGO_MATT_JWT
│   │   ├── backends.py        # Null/Cache/Database backends, all async-aware
│   │   └── core.py            # Public API: blacklist_token, ablacklist_token, etc.
│   ├── jwt.py                 # create/verify/refresh tokens — add bulk_revoke_user_tokens
│   ├── controllers.py         # AuthController — fix change_password to bulk-revoke
│   ├── decorators/
│   │   └── jwt.py             # jwt_required, jwt_optional — async-aware (reference pattern)
│   └── schemas.py             # TokenPayload.org_id already present
├── multitenancy/
│   ├── middleware.py          # TenantMiddleware + TenantMiddlewareAsync
│   ├── models.py              # Organization, Team, Membership, Invitation
│   ├── controllers.py         # NEEDS async conversion (all 4 controllers)
│   ├── decorators.py          # NEEDS async wrapper pattern from auth/decorators/jwt.py
│   └── utils.py               # user_is_org_admin, user_is_org_owner (sync — used in async context via sync_to_async or needs async variants)
└── permissions/
    └── common.py              # NEEDS IsOrgMember, IsOrgAdmin, IsOrgOwner additions
```

### Pattern 1: Async Controller Method (reference from AuthController)
**What:** Async Django view using `await` for all ORM calls, orjson for parsing
**When to use:** All multitenancy controller methods after async conversion

```python
# Source: django_matt/auth/controllers.py (existing pattern)
@post("login")
async def login(self, request: HttpRequest) -> JsonResponse:
    try:
        body = orjson.loads(request.body) if request.body else {}
        data = LoginRequest.model_validate(body)
    except orjson.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON", "code": "invalid_json"}, status=400)

    try:
        user = await User.objects.aget(email=data.email)
    except User.DoesNotExist:
        return JsonResponse({"detail": "Invalid credentials", "code": "invalid_credentials"}, status=401)
    # ...
```

### Pattern 2: Async Decorator with sync/async Detection
**What:** Decorator that wraps async and sync views depending on what it decorates
**When to use:** All new multitenancy decorators must follow this

```python
# Source: django_matt/auth/decorators/jwt.py (reference pattern)
import inspect
from functools import wraps

def requires_org_membership(func):
    @wraps(func)
    async def async_wrapper(self_or_request, *args, **kwargs):
        request = get_request(self_or_request, args, kwargs)
        org = getattr(request, "organization", None)
        if not org:
            return JsonResponse({"detail": "Organization context required"}, status=400)
        # async ORM check
        membership = await Membership.objects.filter(
            organization=org, user=request.user
        ).afirst()
        if not membership:
            return JsonResponse({"detail": "Not a member of this organization"}, status=403)
        return await func(self_or_request, *args, **kwargs)

    @wraps(func)
    def sync_wrapper(self_or_request, *args, **kwargs):
        # sync version
        ...

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
```

### Pattern 3: Org-Aware Permission Class
**What:** BasePermission subclass that checks org membership from request
**When to use:** Controller-level protection via `permission_classes = [IsOrgMember]`

```python
# Source: pattern derived from django_matt/permissions/common.py (existing base)
class IsOrgMember(BasePermission):
    message = "Organization membership required."
    status_code = 403

    def has_permission(self, request, view=None) -> bool:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        org = getattr(request, "organization", None)
        if org is None:
            return False
        # Superuser bypass (configurable)
        from django.conf import settings
        if getattr(settings, "TENANT_SUPERUSER_BYPASS", True) and user.is_superuser:
            return True
        return org.is_member(user)  # sync — called in middleware pipeline
```

### Pattern 4: Bulk Token Revocation
**What:** Function to invalidate all active tokens for a user by JTI tracking or time-based invalidation
**When to use:** Password change, admin revoke-all endpoint

```python
# To implement in django_matt/auth/jwt.py
async def abulk_revoke_tokens_for_user(user, *, current_access_jti: str | None = None) -> None:
    """
    Revoke all active tokens for a user.

    For cache backend: stores a per-user revocation timestamp in cache.
    verify_access_token checks this sentinel during validation.
    For null backend: no-op (logged as warning if DEBUG=False).
    """
    from django_matt.auth.blacklist.core import ablacklist_token
    # Strategy: write a per-user sentinel key with TTL = max token lifetime
    # All tokens issued before this timestamp are considered revoked
    # Implementation: cache.set(f"user_revoked:{user.pk}", now, timeout=max_token_ttl)
```

### Pattern 5: CSRF Exemption for JWT Endpoints
**What:** Router marks JWT-protected views as CSRF-exempt at registration time
**When to use:** All views registered through MattAPI router (JWT auth doesn't need CSRF)

The `CSRFMiddleware` in `auth/session/middleware.py` checks:
```python
# Source: django_matt/auth/session/middleware.py lines 113-120
if getattr(request, "_csrf_exempt", False):
    return None  # Skip CSRF check
if view and getattr(view.func, "_csrf_exempt", False):
    return None  # Skip CSRF check
```

The router must set `view_func._csrf_exempt = True` for all registered endpoints,
or the MattAPI `csrf=False` flag (line 71 in api.py) must propagate this attribute
to URL view functions at registration time.

### Anti-Patterns to Avoid
- **Sync ORM in async controllers:** `Organization.objects.get()` in an `async def` method blocks the event loop. Always use `.aget()`, `.aexists()`, `.asave()`, `.adelete()`.
- **Checking blacklist default without startup warning:** Operators leaving `BLACKLIST_BACKEND="null"` in production silently disables revocation. The startup warning (`AppConfig.ready()`) and `matt doctor` check prevent this.
- **ORM in permission class constructor:** `IsOrgMember.__init__` must not query the DB. Queries happen only in `has_permission()`.
- **Decorators assuming sync context:** All new multitenancy decorators must detect `iscoroutinefunction(func)` and return the appropriate wrapper.
- **Cross-org data leakage via missing queryset filter:** Tenant-aware controllers must always filter by `request.organization`. Missing this filter is the most dangerous bug in multi-tenant code.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cache TTL management | Custom expiry tracking | Django cache `timeout=` param | Django cache handles TTL automatically; CacheBlacklistBackend already uses this |
| Token JTI generation | Custom random string | `secrets.token_urlsafe(32)` via existing `generate_jti()` | Already implemented and correct |
| Async/sync detection | Custom coroutine check | `inspect.iscoroutinefunction(func)` | Already used in auth/decorators/jwt.py — copy this pattern |
| Password hashing | Custom bcrypt | Django's `user.set_password()` / `user.check_password()` | AuthController already uses this |
| Role hierarchy comparison | Custom ordering | `MembershipRole.get_priority()` and `can_manage()` | Already implemented in multitenancy/models.py |
| Org model lookup | Custom UUID parsing | `uuid.UUID(id)` then ORM query pattern | Already used in OrganizationController.retrieve() |
| CSRF token generation | Custom HMAC | `auth/session/csrf.py` utilities | Full implementation already exists |

**Key insight:** The hardening work is wiring up what already exists correctly, not building new subsystems.
The highest-value tasks are: changing the default, adding the missing bulk revocation, and making multitenancy
controllers properly async.

---

## Common Pitfalls

### Pitfall 1: Null Blacklist Backend as Default
**What goes wrong:** Blacklist backend defaults to `"null"`. Logout does not actually revoke tokens.
A user who logs out can reuse their access token until it expires (up to 15 minutes by default).
**Why it happens:** `config.py` has `BLACKLIST_BACKEND` defaulting to `"null"` for safety at install time.
**How to avoid:** Change the default to `"cache"` in config. Existing tests for NullBlacklistBackend
assert `config.backend == "null"` — these tests need to be updated to explicitly pass `BLACKLIST_BACKEND="null"`.
**Warning signs:** Test `TestBlacklistConfig.test_default_backend_is_null` will need updating.

### Pitfall 2: Password Change Does Not Bulk-Revoke Tokens
**What goes wrong:** `change_password` in `AuthController` calls `user.set_password()` and issues new tokens
but does NOT revoke old tokens. An attacker who stole a token can continue using it after the victim changes
their password.
**Why it happens:** Bulk revocation function doesn't exist yet. The controller generates new tokens but
doesn't invalidate the old ones.
**How to avoid:** Implement `abulk_revoke_tokens_for_user(user)` in jwt.py and call it from
`change_password` before issuing new tokens. Use a per-user cache sentinel key approach:
`cache.set(f"jwt_user_revoked:{user.pk}", now().timestamp(), timeout=max_token_lifetime)`.
Then `verify_access_token` checks this sentinel. This avoids needing to track individual JTIs for bulk ops.
**Warning signs:** Test that issues token, changes password, then reuses old token — should get 401.

### Pitfall 3: Sync ORM in Async Multitenancy Controllers
**What goes wrong:** All 4 multitenancy controllers call sync ORM methods inside (what will eventually be)
async request handlers. In ASGI, this raises `SynchronousOnlyOperation` or blocks the event loop.
**Why it happens:** Controllers were written before async priority was established for this phase.
`utils.py` functions `user_is_org_admin()`, `user_is_org_owner()`, `user_can_manage_team()` all use
sync ORM internally.
**How to avoid:** Convert all controller methods to `async def`. Replace `Organization.objects.get()`
with `Organization.objects.aget()`, etc. For utility functions: either create async variants (`auser_is_org_admin`)
or inline the queries in the async controllers.
**Warning signs:** Errors like "You cannot call this from an async context".

### Pitfall 4: CSRF Middleware Blocking JWT-Authenticated Endpoints
**What goes wrong:** If `CSRFMiddleware` is in the stack and API endpoints aren't correctly flagged as
exempt, POST/PUT/DELETE requests without a CSRF token return 403 even with a valid JWT.
**Why it happens:** `CSRFMiddleware` checks `view.func._csrf_exempt` but the MattAPI router's
`csrf=False` flag (in `api.py` line 71) may not propagate `_csrf_exempt = True` to the actual view
function wrapper. The inspector views use Django's `@method_decorator(csrf_exempt)` — the router
needs to do the same for all registered API views.
**How to avoid:** In `MattAPI.__init__` or `register_controller`, wrap all view functions with
`csrf_exempt = True` attribute when `self.csrf = False`. Verify with a test: POST to a JWT-protected
endpoint without a CSRF header and assert 200 (not 403).
**Warning signs:** 403 responses on POST endpoints that succeed with GET.

### Pitfall 5: TenantMiddlewareAsync Without Test Coverage
**What goes wrong:** `TenantMiddlewareAsync` exists but has no tests. Any bugs in the async resolution
path (header, URL kwarg, session, user fallback) go undetected.
**Why it happens:** Tests only cover `TenantMiddleware` (sync). Async middleware was written in parallel.
**How to avoid:** Add `TestTenantMiddlewareAsync` test class mirroring `TestTenantMiddleware` but using
`AsyncClient` or `AsyncRequestFactory`. Cover all 4 resolution strategies.
**Warning signs:** Async requests resolving wrong org or `None` unexpectedly.

### Pitfall 6: Cross-Org Data Leak in Controllers
**What goes wrong:** A controller method retrieves a resource by ID without filtering by org. A member of
Org A can access resources belonging to Org B by guessing UUIDs.
**Why it happens:** Existing controllers filter by `organization` in some methods but not others.
For example, `TeamController.retrieve()` checks org membership but doesn't filter by `request.organization`
in the queryset — it looks up the team globally and then checks membership.
**How to avoid:** Always chain `.filter(organization=request.organization)` before `.aget()`. The response
code for a resource outside the user's org MUST be 404 (not 403 — don't reveal the resource exists).
**Warning signs:** Being able to GET `/teams/{uuid-from-org-b}` while authenticated to Org A.

---

## Code Examples

Verified patterns from existing codebase:

### Blacklist a Single Token (Async)
```python
# Source: django_matt/auth/blacklist/core.py
from django_matt.auth.blacklist.core import ablacklist_token

await ablacklist_token(token_payload.jti, token_payload.exp)
```

### Check if Token is Blacklisted (in verify_access_token)
```python
# Source: django_matt/auth/jwt.py lines 355-363
async def averify_access_token(token: str) -> TokenPayload:
    payload = decode_token(token, verify_type="access")
    if payload.jti:
        from django_matt.auth.blacklist.core import ais_token_blacklisted
        if await ais_token_blacklisted(payload.jti):
            raise InvalidTokenError("Token has been revoked")
    return payload
```

### Resolve Org in Async Middleware
```python
# Source: django_matt/multitenancy/middleware.py lines 256-270 (TenantMiddlewareAsync)
async def _resolve_from_header(self, request, Organization):
    org_id = request.headers.get(self.header_id)
    if org_id:
        try:
            return await Organization.objects.filter(id=org_id, is_active=True).afirst()
        except (ValueError, Organization.DoesNotExist):
            pass
    return None
```

### Async Controller Method (reference template for multitenancy conversion)
```python
# Source: django_matt/auth/controllers.py (AuthController pattern)
@get("")
@jwt_required
async def list_organizations(self, request: HttpRequest) -> JsonResponse:
    memberships = await Membership.objects.filter(
        user=request.user,
        organization__is_active=True,
    ).select_related("organization").values_list(
        "organization__id", "organization__name", "role", flat=False
    ).ato_list()  # or async list comprehension
    ...
```

### Check Blacklist Config Default (current state — to be changed)
```python
# Source: django_matt/auth/blacklist/config.py line 19
# CURRENT (must change): default is "null"
backend: str = self._config.get("BLACKLIST_BACKEND", "null")
# TARGET (post-phase-4): default is "cache"
backend: str = self._config.get("BLACKLIST_BACKEND", "cache")
```

### Django Startup Warning Pattern (AppConfig.ready)
```python
# Pattern to add: startup warning when backend is null in production
class DjangoMattConfig(AppConfig):
    def ready(self):
        from django.conf import settings
        from django_matt.auth.blacklist.config import blacklist_config
        import warnings
        if not settings.DEBUG and not blacklist_config.enabled:
            warnings.warn(
                "JWT blacklist backend is 'null' — token revocation is disabled. "
                "Set DJANGO_MATT_JWT['BLACKLIST_BACKEND'] = 'cache' for production.",
                stacklevel=2,
            )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `DJANGO_ALLOW_ASYNC_UNSAFE=True` | Removed — all sync ORM converted | Phase 1 | Cannot use sync ORM in async handlers |
| sync_to_async wrappers on model classmethods | Retained for custom classmethods with internal sync ORM | Phase 1 decision | `user_is_org_admin()` may need async variant instead of sync_to_async wrapper |
| utils/errors.py | Deleted — canonical is django_matt.core.errors | Phase 1 | Import from `django_matt.core.errors` only |
| NullBlacklistBackend as default | Must change to CacheBlacklistBackend | This phase | Tests for default=null need updating |

**Deprecated/outdated:**
- `DJANGO_ALLOW_ASYNC_UNSAFE=True`: Removed in Phase 1. Never bring this back.
- `from django_matt.utils.errors import ...`: Deleted in Phase 1. Use `django_matt.core.errors`.
- Sync ORM in controllers: Eliminated in Phase 1 for auth controllers. Multitenancy controllers still need this fix.

---

## Open Questions

1. **Bulk revocation implementation strategy**
   - What we know: Cache backend is the default; no per-user revocation sentinel exists
   - What's unclear: Per-JTI tracking (one cache key per token) vs per-user timestamp sentinel
     (one key per user, check `iat < revocation_time`). The timestamp approach is O(1) per check
     but requires `iat` to be trusted. The JTI approach requires knowing all active JTIs.
   - Recommendation: Use per-user timestamp sentinel. Store `jwt_user_revoked:{user.pk}` with
     `timeout = refresh_token_lifetime`. In `verify_access_token`, after decoding, check if
     `payload.iat < sentinel_time`. Simple, efficient, no token tracking needed.

2. **Admin revoke-all endpoint access control**
   - What we know: Must be restricted. Claude's discretion per CONTEXT.md.
   - What's unclear: Superuser-only (simpler) vs superuser + org admin for their own org (more useful for B2B)
   - Recommendation: Superuser-only for global revoke-all; org admin can revoke members within their org.
     Two separate endpoints: `POST /admin/users/{id}/revoke-tokens` (superuser-only) and
     `POST /organizations/{id}/members/{user_id}/revoke-tokens` (org admin).

3. **Rate limiting on auth endpoints (defer or implement)**
   - What we know: Auth rate limiting belongs conceptually in Phase 7 (PERF-03)
   - What's unclear: Whether security requirements demand basic throttling now
   - Recommendation: Defer to Phase 7. Auth endpoints don't require rate limiting to pass Phase 4
     success criteria. Add a TODO comment in auth controllers noting this gap.

4. **`allow_any` decorator flag wiring**
   - What we know: CONTEXT.md lists this as Claude's discretion
   - What's unclear: Whether it's wired into controller dispatch currently
   - Recommendation: Leave as-is for now. The `AllowAny` permission class covers the use case.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django + pytest-asyncio |
| Config file | `pyproject.toml` (asyncio_mode = "auto") |
| Quick run command | `uv run pytest tests/test_auth.py tests/test_blacklist.py tests/test_multitenancy.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | JWT token creation, validation, refresh | unit | `uv run pytest tests/test_auth.py::TestJWT -x` | ✅ |
| AUTH-02 | Blacklist token on logout; bulk revoke on password change | integration | `uv run pytest tests/test_blacklist.py tests/test_auth.py::TestAuthController::test_logout_blacklists_token -x` | ✅ partial (logout test missing; bulk revoke test missing — Wave 0) |
| AUTH-03 | Session auth backend | unit | `uv run pytest tests/test_auth.py -k session -x` | ✅ |
| AUTH-04 | IsAuthenticated, IsAdmin, IsOwner, HasRole, HasPermission | unit | `uv run pytest tests/test_auth.py -k "permission" -x` | ✅ (IsOrgMember etc. Wave 0) |
| AUTH-05 | RBAC role assignment and checking | unit | `uv run pytest tests/test_auth.py -k "rbac or role" -x` | ✅ |
| AUTH-06 | Password reset flow | integration | `uv run pytest tests/test_auth.py::TestAuthController::test_password_reset -x` | ✅ |
| AUTH-07 | Magic link flow | integration | `uv run pytest tests/test_auth.py -k "magic_link" -x` | ✅ |
| AUTH-08 | OAuth Google + GitHub integration | integration | `uv run pytest tests/test_auth_oauth.py -x` | ✅ (integration tests to add — Wave 0) |
| AUTH-09 | OIDC integration; SAML unit | integration + unit | `uv run pytest tests/test_auth_sso.py -x` | ✅ (OIDC integration to add — Wave 0) |
| AUTH-10 | Passkeys graceful skip without webauthn | unit | `uv run pytest tests/test_auth_passkeys.py -x` | ✅ |
| AUTH-11 | API key auth | unit | `uv run pytest tests/test_auth_api_keys.py -x` | ✅ |
| AUTH-12 | JWT endpoint has no CSRF requirement | integration | `uv run pytest tests/test_auth.py::test_jwt_endpoint_no_csrf_required -x` | ❌ Wave 0 |
| AUTH-13 | @jwt_required, @jwt_optional, @requires_role, @requires_permission | unit | `uv run pytest tests/test_auth.py -k "decorator" -x` | ✅ |
| TENANT-01 | Organization CRUD | integration | `uv run pytest tests/test_multitenancy.py::TestOrganizationController -x` | ✅ (async tests needed — Wave 0) |
| TENANT-02 | Team CRUD + membership | integration | `uv run pytest tests/test_multitenancy.py::TestTeamController -x` | ✅ (async tests needed — Wave 0) |
| TENANT-03 | Membership roles | unit | `uv run pytest tests/test_multitenancy.py::TestMembershipModel -x` | ✅ |
| TENANT-04 | TenantMiddlewareAsync | unit | `uv run pytest tests/test_multitenancy.py::TestTenantMiddlewareAsync -x` | ❌ Wave 0 |
| TENANT-05 | Org-scoped queryset; non-member gets 403 | integration | `uv run pytest tests/test_multitenancy.py::test_non_member_gets_403 -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth.py tests/test_blacklist.py tests/test_multitenancy.py -x -q --tb=short`
- **Per wave merge:** `uv run pytest tests/ -x -q --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth.py::TestAuthController::test_logout_blacklists_token` — covers AUTH-02 logout revocation
- [ ] `tests/test_auth.py::TestAuthController::test_change_password_revokes_old_tokens` — covers AUTH-02 bulk revocation
- [ ] `tests/test_auth.py::test_jwt_endpoint_no_csrf_required` — covers AUTH-12
- [ ] `tests/test_multitenancy.py::TestTenantMiddlewareAsync` — covers TENANT-04
- [ ] `tests/test_multitenancy.py::test_non_member_gets_403` — covers TENANT-05 (cross-org 403 not 500)
- [ ] `tests/test_multitenancy.py::TestOrgPermissionClasses` — covers IsOrgMember/IsOrgAdmin/IsOrgOwner classes
- [ ] `tests/test_auth_oauth.py::TestOAuthGoogleIntegration` and `TestOAuthGitHubIntegration` — covers AUTH-08
- [ ] `tests/test_auth_sso.py::TestOIDCIntegration` — covers AUTH-09

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection:
  - `django_matt/auth/blacklist/` — full blacklist system, all 3 backends, config, core API
  - `django_matt/auth/jwt.py` — complete token lifecycle, verified no bulk revocation exists
  - `django_matt/auth/controllers.py` — AuthController endpoints, confirmed change_password gap
  - `django_matt/auth/decorators/jwt.py` — async/sync detection pattern (reference for multitenancy)
  - `django_matt/auth/session/csrf.py` — CSRF implementation
  - `django_matt/auth/session/middleware.py` — CSRFMiddleware, `_csrf_exempt` flag check
  - `django_matt/auth/middleware.py` — JWTAuthenticationMiddleware, JWTAuthenticationMiddlewareAsync
  - `django_matt/multitenancy/middleware.py` — TenantMiddleware + TenantMiddlewareAsync
  - `django_matt/multitenancy/models.py` — Organization, Team, Membership, Invitation, role hierarchy
  - `django_matt/multitenancy/controllers.py` — 4 sync-only controllers confirmed
  - `django_matt/multitenancy/decorators.py` — 7 sync-only decorators confirmed
  - `django_matt/multitenancy/utils.py` — sync utility functions (user_is_org_admin etc.)
  - `django_matt/permissions/common.py` — existing permission classes; no org-aware classes
  - `django_matt/auth/schemas.py` — TokenPayload.org_id already present
  - `django_matt/api.py` — `csrf=False` flag exists, propagation needs verification
  - `tests/test_blacklist.py` — existing blacklist test coverage
  - `tests/test_multitenancy.py` — 191 tests, no async middleware tests found
  - `tests/conftest.py` — asyncio_mode=auto confirmed, table creation pattern

### Secondary (MEDIUM confidence)
- `.planning/phases/04-auth-hardening-and-multi-tenancy/04-CONTEXT.md` — user decisions
- `.planning/STATE.md` — accumulated decisions from prior phases
- `.planning/REQUIREMENTS.md` — all 101 v1 requirements with traceability

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all from direct code inspection, no assumptions
- Architecture: HIGH — patterns extracted directly from existing code
- Pitfalls: HIGH — specific line references provided for all gaps identified
- Test gaps: HIGH — collected-only analysis of existing test IDs vs missing tests

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable codebase)

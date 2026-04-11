# Multi-tenant SaaS Example

Multi-tenant SaaS application demonstrating django-matt's tenancy, interceptors, events, and feature flags.

## Features Demonstrated

- **Multi-tenancy** — organization-scoped resources with slug-based resolution
- **Interceptors** — `TenantInterceptor` resolves tenant from headers, `FeatureGateInterceptor` gates by plan
- **Event Bus** — domain events for tenant lifecycle (`tenant.created`, `project.created`, `member.invited`)
- **Feature Flags** — plan-based feature gating (archive is Pro+ only)
- **Controllers** — async API controllers with typed schemas

## Architecture

```
GET  /organizations/              → list all orgs
POST /organizations/              → create org → emit tenant.created
GET  /organizations/{id}/         → org details

GET  /projects/                   → list projects (tenant-scoped via X-Tenant-Slug)
POST /projects/                   → create project → emit project.created
GET  /projects/{id}/              → project details
POST /projects/{id}/archive       → archive (Pro+ only, gated by FeatureGateInterceptor)
```

## Interceptor Chain

```
Request → TenantInterceptor.before() → [resolve org from header]
        → FeatureGateInterceptor.before() → [check plan]
        → Controller method
        → FeatureGateInterceptor.after()
        → TenantInterceptor.after() → [add X-Tenant-Id header]
        → Response
```

## Setup

```bash
cd examples/multitenant-saas
uv run python manage.py migrate
uv run uvicorn mt_project.asgi:application --reload
```

## Usage

```bash
# Create an organization
curl -X POST http://localhost:8000/organizations/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "slug": "acme", "plan": "pro"}'

# List projects (tenant-scoped)
curl http://localhost:8000/projects/ \
  -H "X-Tenant-Slug: acme"

# Create a project
curl -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Slug: acme" \
  -d '{"name": "Website Redesign"}'

# Archive (Pro+ only — free plan gets 403)
curl -X POST http://localhost:8000/projects/{id}/archive \
  -H "X-Tenant-Slug: acme"
```

## Key Files

| File | Purpose |
|------|---------|
| `api/controllers.py` | Org and project controllers with interceptors |
| `api/interceptors.py` | TenantInterceptor + FeatureGateInterceptor |
| `tenants/events.py` | Domain event handlers |
| `tenants/models.py` | Organization, Membership, Project |
| `tenants/schemas.py` | Pydantic ModelSchema definitions |

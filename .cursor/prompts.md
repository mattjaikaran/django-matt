# Framework Development Prompts

## **CRUD Generation**
```cursor
Generate CRUD for a `{{ModelName}}` model with:
- Run: python manage.py generate_crud {{app}}.{{ModelName}} --full
- This creates: controller, schemas, service layer, admin, tests
- Service layer is where business logic goes
- Controller stays thin - delegates to service
```

## **Service Layer Pattern**
```cursor
Create a service for `{{ModelName}}` that handles:
- Complex business logic beyond simple CRUD
- External service calls (payments, emails, etc.)
- Transaction management with django.db.transaction
- Event dispatching and notifications
Keep controllers thin - they only handle HTTP concerns.
```

## **Admin Dashboard**
```cursor
Create a custom admin dashboard using django_matt.admin:
- Use `auto_dashboard()` to generate from registered models
- Add `StatWidget` for key metrics
- Add `model_time_series_chart()` for trends
- Use `DashboardAdminSite` as your admin site class
```

## **Custom Admin Page**
```cursor
Create a custom admin page using `@pages.register()`:
- Define URL path and title
- Add permission checks if needed
- Use `pages.render()` for consistent Unfold styling
- Group related pages with `AdminPageGroup`
```

## **Type Synchronization**
```cursor
Generate a migration-aware script that:
1. Compares Django model `{{ModelName}}` changes
2. Updates TypeScript interfaces in `frontend/src/types/{{modelName}}.ts`
3. Run: python manage.py sync_types --target typescript --watch
```

## **Auth System**
```cursor
Implement authentication using django_matt.auth:
- JWT: `@jwt_required`, `@jwt_optional` decorators
- OAuth: Register OAuthController for social login
- Passkeys: Register PasskeyController for WebAuthn
- Permissions: `@requires_permission()`, `@requires_role()`
```

## **Performance Optimization**
```cursor
Analyze the endpoint `{{EndpointPath}}` and:
1. Use `optimize_queryset()` for auto select_related/prefetch_related
2. Add `@cache_response(timeout=300)` for cacheable endpoints
3. Use `distributed_cache.get_or_set()` for expensive computations
4. Check N+1 queries with QueryLoggingMiddleware
```

## **Multi-Tenant Setup**
```cursor
Set up multi-tenancy for a B2B application:
- Models: Organization, Team, Membership from django_matt.multitenancy
- Middleware: TenantContextMiddleware for automatic filtering
- Admin: Use MultiTenantAdminMixin to filter by organization
```

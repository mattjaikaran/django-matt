# Migration Guides

Guides for migrating to django-matt from other Python API frameworks.

## Available Guides

### [From Django REST Framework](from-drf.md)

For teams with existing DRF applications. Covers:
- Serializers to Pydantic schemas
- ViewSets to Controllers and APIViewSets
- Authentication (simplejwt to built-in JWT)
- Permissions, pagination, filtering, throttling
- Testing with AsyncAPITestClient
- Complete before/after app conversion
- Incremental migration strategy (run DRF and django-matt side by side)

### [From Django Ninja](from-django-ninja.md)

For projects using Django Ninja and its ecosystem (ninja-extra, ninja-jwt, ninja-crud). Covers:
- NinjaAPI to MattAPI (near-identical API surface)
- Schema Config to Meta class
- Controllers (ninja-extra to APIController)
- JWT (ninja-jwt to built-in auth)
- CRUD views (ninja-crud to ViewSets)
- Dependency injection differences
- Import mapping reference

### [From FastAPI](from-fastapi.md)

For Python developers coming from FastAPI/SQLAlchemy. Covers:
- SQLAlchemy models to Django ORM
- Shared Pydantic v2 patterns
- Depends() comparison
- Async patterns (both are async-first)
- Middleware differences
- Background tasks
- What you gain (admin, auto-migrations, auth, billing)
- What you trade (raw ASGI speed, SQLAlchemy flexibility)

## Framework Comparison

See [Framework Comparison](../comparison.md) for a detailed feature matrix comparing django-matt, DRF, Django Ninja, and FastAPI -- including performance notes, when to choose each, and honest trade-offs.

## General Migration Tips

1. **Migrate incrementally.** django-matt can run alongside DRF or Django Ninja in the same project. Mount new endpoints on `/api/v2/` while keeping old ones on `/api/v1/`.

2. **Start with new features.** Write new endpoints in django-matt. Convert existing ones only when you need to touch them.

3. **Schemas are portable.** If you already have Pydantic schemas (from Django Ninja or FastAPI), they work with django-matt with minimal changes.

4. **Test after each endpoint.** Convert one controller/viewset at a time and verify with tests before moving on.

5. **Async conversion is optional.** django-matt supports both sync and async views. You can convert to async incrementally or not at all.

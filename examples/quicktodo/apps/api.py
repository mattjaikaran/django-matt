from django_matt import MattAPI
from django_matt.auth import jwt_required

from apps.organizations.controllers import register_org_routes
from apps.todos.controllers import register_todo_routes
from apps.users.controllers import register_auth_routes

api = MattAPI(
    title="QuickTodo API",
    version="1.0.0",
    description="Multi-tenant todo API built with django-matt",
)

# Register all routes
register_auth_routes(api)
register_org_routes(api)
register_todo_routes(api)


@api.get("health", tags=["Health"])
async def health_check(request) -> dict:
    return {"status": "healthy"}


@api.get("protected", tags=["Health"])
@jwt_required
async def protected_endpoint(request) -> dict:
    return {"message": f"Hello, {request.user.email}!"}

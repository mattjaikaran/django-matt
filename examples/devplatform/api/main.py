from django_matt import DjangoMattAPI
from django_matt.auth import jwt_required

from apps.analytics.controllers import register_analytics_routes
from apps.billing.controllers import register_billing_routes
from apps.dashboard.controllers import register_dashboard_routes
from apps.gateway.controllers import register_gateway_routes
from apps.keys.controllers import register_key_routes
from apps.organizations.controllers import register_org_routes
from apps.projects.controllers import register_project_routes
from apps.users.controllers import register_auth_routes
from apps.webhooks.controllers import register_webhook_routes

api = DjangoMattAPI(title="DevPlatform API",
version="1.0.0",
description="API management SaaS built with django-matt",)

# Register all routes
register_auth_routes(api)
register_org_routes(api)
register_project_routes(api)
register_key_routes(api)
register_gateway_routes(api)
register_analytics_routes(api)
register_webhook_routes(api)
register_billing_routes(api)
register_dashboard_routes(api)


@api.get("health", tags=["Health"])
async def health_check(request) -> dict:
    return {"status": "healthy"}


@api.get("protected", tags=["Health"])
@jwt_required
async def protected_endpoint(request) -> dict:
    return {"message": f"Hello, {request.user.email}!"}

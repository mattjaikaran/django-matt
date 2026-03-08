"""
Main API configuration for SaaS Starter.

This module configures the django-matt API with all routes,
middleware, and OpenAPI documentation.
"""

from django_matt import MattAPI
from django_matt.openapi import OpenAPIConfig

from .analytics import AnalyticsController
from .auth import AuthController
from .billing import BillingController
from .comments import CommentController
from .health import HealthController
from .notifications import NotificationController
from .organizations import OrganizationController
from .projects import ProjectController
from .tasks import TaskController
from .teams import TeamController

# Create the main API instance
api = MattAPI(
    title="SaaS Starter API",
    version="1.0.0",
    description="""
    A comprehensive SaaS API built with django-matt.

    ## Features

    - **Authentication**: JWT tokens, OAuth (Google, GitHub), Magic Links
    - **Organizations**: Multi-tenant workspace management
    - **Projects**: Project and task management with real-time updates
    - **Billing**: Stripe integration for subscriptions and invoices
    - **Notifications**: In-app and email notifications

    ## Authentication

    Most endpoints require authentication. Include the JWT token in the Authorization header:

    ```
    Authorization: Bearer <access_token>
    ```

    ## Rate Limiting

    API requests are rate limited based on your plan:
    - Free: 100 requests/minute
    - Pro: 1000 requests/minute
    - Enterprise: Unlimited

    ## Webhooks

    Webhook endpoints are available at `/api/webhooks/` for:
    - Stripe events
    - GitHub integrations
    """,
    openapi_config=OpenAPIConfig(
        servers=[
            {"url": "http://localhost:8000", "description": "Development"},
            {"url": "https://api.saas-starter.example.com", "description": "Production"},
        ],
        tags=[
            {"name": "Auth", "description": "Authentication and authorization"},
            {"name": "Users", "description": "User management"},
            {"name": "Organizations", "description": "Organization management"},
            {"name": "Teams", "description": "Team management within organizations"},
            {"name": "Projects", "description": "Project management"},
            {"name": "Tasks", "description": "Task management"},
            {"name": "Comments", "description": "Task comments and discussions"},
            {"name": "Billing", "description": "Subscription and payment management"},
            {"name": "Notifications", "description": "Notification management"},
            {"name": "Analytics", "description": "Analytics and tracking"},
            {"name": "Health", "description": "Health checks and status"},
        ],
        security_schemes={
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            },
        },
    ),
)

# Register all controllers
api.register_controller(HealthController)
api.register_controller(AuthController)
api.register_controller(OrganizationController)
api.register_controller(TeamController)
api.register_controller(ProjectController)
api.register_controller(TaskController)
api.register_controller(CommentController)
api.register_controller(BillingController)
api.register_controller(NotificationController)
api.register_controller(AnalyticsController)

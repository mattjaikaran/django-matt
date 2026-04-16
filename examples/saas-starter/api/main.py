"""
Main API configuration for SaaS Starter.

This module configures the django-matt API with all routes,
middleware, and OpenAPI documentation.
"""

from django_matt import MattAPI

from api.analytics import AnalyticsController
from api.auth import AuthController
from api.billing import BillingController, WebhookController
from api.comments import CommentController
from api.health import HealthController
from api.notifications import NotificationController
from api.organizations import OrganizationController
from api.projects import ProjectController
from api.tasks import TaskController
from api.teams import TeamController

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
    servers=[
        {"url": "http://localhost:8000", "description": "Development"},
        {"url": "https://api.saas-starter.example.com", "description": "Production"},
    ],
)

# Register all controllers
api.register_controllers(
    HealthController,
    AuthController,
    OrganizationController,
    TeamController,
    ProjectController,
    TaskController,
    CommentController,
    NotificationController,
    AnalyticsController,
    BillingController,
    WebhookController,
)

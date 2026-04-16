"""
Main API configuration for SaaS Starter.

This module configures the django-matt API with all routes,
middleware, and OpenAPI documentation.

NOTE: The controllers under ``api/analytics.py``, ``api/auth.py``, etc. were
scaffolded against an early django-matt API (``@api_controller`` +
``@APIController.post`` decorators) that was retired before 0.9. They need
porting to the current ``prefix = "..."`` / ``@api.get(...)`` style before
they can be re-wired into this module. See each file's TODO banner.
"""

from django_matt import MattAPI

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


@api.get("", tags=["Health"])
async def root(request) -> dict:
    """Placeholder root endpoint. Port the real controllers and register them here."""
    return {
        "status": "ok",
        "message": "SaaS Starter API scaffold — controllers pending migration to django-matt 0.9 API",
    }

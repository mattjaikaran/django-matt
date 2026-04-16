"""
API routes — wire up tenant and project controllers.
"""

from django_matt.api import MattAPI

from api.controllers import OrganizationController, ProjectController

api = MattAPI(
    title="Multi-tenant SaaS API",
    version="1.0.0",
    description="Multi-tenant SaaS with events, interceptors, and feature flags",
)

api.register_controller(OrganizationController)
api.register_controller(ProjectController)

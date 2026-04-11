"""
Domain event handlers for tenant lifecycle.

Uses django-matt's event bus for cross-cutting concerns.
"""

import logging

from django_matt.events.decorators import on

logger = logging.getLogger(__name__)


@on("tenant.created")
async def on_tenant_created(*, org_id: str, name: str, plan: str, **kwargs):
    """Initialize defaults for a new tenant (e.g., seed data, billing setup)."""
    logger.info("New tenant created: %s (plan=%s)", name, plan)


@on("tenant.plan.changed")
async def on_plan_changed(*, org_id: str, old_plan: str, new_plan: str, **kwargs):
    """React to plan upgrades/downgrades — adjust feature flag overrides."""
    logger.info("Tenant %s changed plan: %s → %s", org_id, old_plan, new_plan)


@on("project.created")
async def on_project_created(*, org_id: str, project_id: str, name: str, **kwargs):
    """Track project creation for usage analytics."""
    logger.info("Project created in org %s: %s (%s)", org_id, name, project_id)


@on("member.invited")
async def on_member_invited(*, org_id: str, user_id: str, role: str, **kwargs):
    """Send welcome notification to new member."""
    logger.info("Member %s invited to org %s as %s", user_id, org_id, role)

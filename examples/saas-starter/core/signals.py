"""
Signal handlers for core app.

Handles:
- User creation (auto-create personal org)
- Organization events
- Membership changes
"""

from django.conf import settings
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import User, Organization, Membership, MembershipRole


@receiver(post_save, sender=User)
def create_personal_organization(sender, instance, created, **kwargs):
    """
    Automatically create a personal organization for new users.
    This is optional and controlled by settings.
    """
    if not created:
        return

    # Check if auto-creation is enabled
    multitenancy_settings = getattr(settings, "MATT_MULTITENANCY", {})
    if not multitenancy_settings.get("AUTO_CREATE_PERSONAL_ORG", True):
        return

    # Create personal organization
    org = Organization.objects.create(
        name=f"{instance.display_name}'s Workspace",
        slug=f"personal-{str(instance.id)[:8]}",
        owner=instance,
        is_personal=True,
        plan="free",
        plan_limits=settings.BILLING_PRODUCTS.get("free", {}).get("limits", {}),
    )

    # Create owner membership
    Membership.objects.create(
        user=instance,
        organization=org,
        role=MembershipRole.OWNER,
    )


@receiver(post_save, sender=Organization)
def ensure_owner_membership(sender, instance, created, **kwargs):
    """
    Ensure organization owner has a membership.
    """
    if created and instance.owner:
        Membership.objects.get_or_create(
            user=instance.owner,
            organization=instance,
            defaults={"role": MembershipRole.OWNER},
        )


@receiver(pre_delete, sender=Organization)
def cleanup_organization(sender, instance, **kwargs):
    """
    Clean up related resources when organization is deleted.
    """
    # Cancel any active subscriptions (handled by billing app)
    # Log the deletion for audit purposes
    from .models import AuditLog

    if instance.owner:
        AuditLog.objects.create(
            user=instance.owner,
            organization=instance,
            action="organization.deleted",
            data={
                "organization_name": instance.name,
                "organization_slug": instance.slug,
            },
        )

"""
Service layer for the SaaS Starter core app.

Encapsulates business logic for User, Organization, Membership, and
Invitation models, keeping controllers as thin HTTP adapters.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django_matt.services import CRUDService, NotFoundError, ValidationError

from .models import Invitation, Membership, MembershipRole, Organization, User

# =============================================================================
# User Service
# =============================================================================


class UserService(CRUDService["User"]):
    """Service for user CRUD and session helpers."""

    model = User

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def get_by_email(self, email: str) -> User:
        """
        Fetch a user by email address.
        Raises NotFoundError if no matching user exists.
        """
        return await self.get_by(email=email)

    async def update_last_login(self, user: User) -> User:
        """Stamp last_login_at and last_activity_at on the user record."""
        now = timezone.now()
        user.last_login_at = now
        user.last_activity_at = now
        await user.asave(update_fields=["last_login_at", "last_activity_at", "updated_at"])
        return user


# =============================================================================
# Organization Service
# =============================================================================


class OrganizationService(CRUDService["Organization"]):
    """Service for organization CRUD."""

    model = Organization

    def get_queryset(self):
        return super().get_queryset().select_related("owner")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def get_by_slug(self, slug: str) -> Organization:
        """
        Fetch an active organization by slug.
        Raises NotFoundError if not found.
        """
        return await self.get_by(slug=slug, is_active=True)

    async def get_for_user(self, user: User) -> list[Organization]:
        """Return all active organizations the user belongs to."""
        return [
            o
            async for o in self.get_queryset().filter(
                memberships__user=user,
                memberships__is_active=True,
                is_active=True,
            )
        ]


# =============================================================================
# Membership Service
# =============================================================================


class MembershipService(CRUDService["Membership"]):
    """Service for organization membership management."""

    model = Membership

    def get_queryset(self):
        return super().get_queryset().select_related("user", "organization")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def for_org(self, org: Organization) -> list[Membership]:
        """Return all active memberships for an organization."""
        return [
            m
            async for m in self.get_queryset().filter(
                organization=org, is_active=True
            ).order_by("user__email")
        ]

    async def for_user(self, user: User) -> list[Membership]:
        """Return all active memberships for a user."""
        return [
            m
            async for m in self.get_queryset().filter(user=user, is_active=True)
        ]

    async def add_member(
        self,
        org: Organization,
        user: User,
        role: str = MembershipRole.MEMBER,
    ) -> Membership:
        """
        Add ``user`` to ``org`` with the given role, or re-activate an
        existing inactive membership.
        """
        async with transaction.atomic():
            membership, created = await Membership.objects.aget_or_create(
                user=user,
                organization=org,
                defaults={"role": role, "is_active": True},
            )
            if not created and not membership.is_active:
                membership.is_active = True
                membership.role = role
                await membership.asave(update_fields=["is_active", "role", "updated_at"])

        self._log.info(
            "member %s added to org %s with role %s", user.pk, org.pk, role
        )
        return membership

    async def change_role(self, pk, role: str) -> Membership:
        """Update the role of a membership record."""
        if role not in MembershipRole.values:
            raise ValidationError(f"Invalid role '{role}'", field="role")
        return await self.update_fields(pk, role=role)

    async def remove_member(self, pk) -> bool:
        """
        Soft-deactivate a membership.

        Returns True on success. Does not permanently delete the record
        so audit history is preserved.
        """
        membership = await self.get(pk)
        membership.is_active = False
        await membership.asave(update_fields=["is_active", "updated_at"])
        self._log.info("membership pk=%s deactivated", pk)
        return True


# =============================================================================
# Invitation Service
# =============================================================================


class InvitationService(CRUDService["Invitation"]):
    """Service for org invitation lifecycle."""

    model = Invitation

    _TOKEN_TTL_HOURS = 72

    def get_queryset(self):
        return super().get_queryset().select_related("organization", "invited_by")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def create_invite(
        self,
        org: Organization,
        email: str,
        role: str = MembershipRole.MEMBER,
        invited_by: User | None = None,
    ) -> Invitation:
        """
        Create a pending invitation for ``email`` to join ``org``.

        Raises ValidationError if a pending, non-expired invitation already
        exists for this email + org combination.
        """
        existing = await Invitation.objects.filter(
            organization=org,
            email=email,
            status="pending",
            expires_at__gt=timezone.now(),
        ).aexists()

        if existing:
            raise ValidationError(
                f"A pending invitation for {email} already exists", field="email"
            )

        token = secrets.token_urlsafe(32)
        invitation = await Invitation.objects.acreate(
            organization=org,
            email=email,
            role=role,
            token=token,
            invited_by=invited_by,
            expires_at=timezone.now() + timedelta(hours=self._TOKEN_TTL_HOURS),
        )
        self._log.info(
            "invitation created for %s to org %s by %s",
            email,
            org.pk,
            invited_by.pk if invited_by else "system",
        )
        return invitation

    async def accept(self, token: str, user: User) -> Membership:
        """
        Accept an invitation via its token.

        Creates (or reactivates) the org membership and marks the invitation
        as accepted. Raises ValidationError for expired or already-used tokens.
        """
        try:
            invitation = await Invitation.objects.select_related("organization").aget(
                token=token
            )
        except Invitation.DoesNotExist as exc:
            raise NotFoundError("Invitation not found") from exc

        if not invitation.is_valid:
            raise ValidationError("Invitation is expired or has already been used")

        async with transaction.atomic():
            membership_service = MembershipService()
            membership = await membership_service.add_member(
                org=invitation.organization,
                user=user,
                role=invitation.role,
            )
            invitation.status = "accepted"
            invitation.accepted_at = timezone.now()
            await invitation.asave(update_fields=["status", "accepted_at"])

        return membership

    async def revoke(self, pk) -> Invitation:
        """Mark an invitation as revoked."""
        invitation = await self.get(pk)
        invitation.status = "revoked"
        await invitation.asave(update_fields=["status"])
        self._log.info("invitation pk=%s revoked", pk)
        return invitation

"""
Tests for the Django Matt multitenancy module.

Covers:
- MembershipRole enum and role hierarchy
- Organization CRUD and member management
- Team management within organizations
- Membership model properties and constraints
- TeamMembership management
- Invitation lifecycle (create, accept, decline, revoke, resend, expire)
- Tenant context middleware (sync and async)
- Tenant context management (set/get/clear)
- Decorators (requires_organization, requires_org_membership, requires_org_role,
  requires_org_admin, requires_org_owner, requires_min_org_role, requires_team_membership)
- Utility functions (sync and async)
- Cross-tenant data isolation
- Schemas validation
- Invitation email config
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

import pytest

from django_matt.multitenancy.decorators import (
    requires_min_org_role,
    requires_org_admin,
    requires_org_membership,
    requires_org_owner,
    requires_org_role,
    requires_organization,
    requires_team_membership,
)
from django_matt.multitenancy.middleware import (
    TenantMiddleware,
    TenantMiddlewareAsync,
    clear_current_tenant,
    get_current_organization,
    get_current_tenant,
    set_current_tenant,
)
from django_matt.multitenancy.models import (
    Invitation,
    InvitationStatus,
    Membership,
    MembershipRole,
    Organization,
    Team,
    TeamMembership,
    generate_invitation_token,
    get_invitation_expiry,
)
from django_matt.multitenancy.schemas import (
    InvitationCreate,
    MembershipUpdate,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    TeamCreate,
    TenantContext,
)
from django_matt.multitenancy.utils import (
    create_organization_with_owner,
    create_team_with_members,
    get_organization_members,
    get_team_members,
    get_user_organizations,
    get_user_teams,
    transfer_ownership,
    user_can_manage_team,
    user_has_org_permission,
    user_is_org_admin,
    user_is_org_owner,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_a():
    return User.objects.create_user(
        username="alice", email="alice@example.com", password="password123"
    )


@pytest.fixture
def user_b():
    return User.objects.create_user(
        username="bob", email="bob@example.com", password="password123"
    )


@pytest.fixture
def user_c():
    return User.objects.create_user(
        username="carol", email="carol@example.com", password="password123"
    )


@pytest.fixture
def org_a(user_a):
    return create_organization_with_owner(
        name="Org Alpha", slug="org-alpha", owner=user_a
    )


@pytest.fixture
def org_b(user_b):
    return create_organization_with_owner(
        name="Org Beta", slug="org-beta", owner=user_b
    )


@pytest.fixture
def team_a(org_a):
    return Team.objects.create(
        organization=org_a, name="Team Alpha", slug="team-alpha"
    )


@pytest.fixture
def rf():
    return RequestFactory()


# ===========================================================================
# MembershipRole
# ===========================================================================


class TestMembershipRole:
    def test_choices(self):
        choices = MembershipRole.choices()
        assert len(choices) == 4
        values = [c[0] for c in choices]
        assert "owner" in values
        assert "admin" in values
        assert "member" in values
        assert "viewer" in values

    def test_get_priority(self):
        assert MembershipRole.get_priority("owner") == 100
        assert MembershipRole.get_priority("admin") == 75
        assert MembershipRole.get_priority("member") == 50
        assert MembershipRole.get_priority("viewer") == 25
        assert MembershipRole.get_priority("unknown") == 0

    def test_can_manage(self):
        assert MembershipRole.can_manage("owner", "admin") is True
        assert MembershipRole.can_manage("owner", "member") is True
        assert MembershipRole.can_manage("admin", "member") is True
        assert MembershipRole.can_manage("admin", "viewer") is True
        # same level cannot manage
        assert MembershipRole.can_manage("admin", "admin") is False
        assert MembershipRole.can_manage("owner", "owner") is False
        # lower cannot manage higher
        assert MembershipRole.can_manage("member", "admin") is False
        assert MembershipRole.can_manage("viewer", "member") is False


class TestInvitationStatus:
    def test_choices(self):
        choices = InvitationStatus.choices()
        values = [c[0] for c in choices]
        assert "pending" in values
        assert "accepted" in values
        assert "declined" in values
        assert "expired" in values
        assert "revoked" in values


# ===========================================================================
# Organization model
# ===========================================================================


class TestOrganizationModel:
    def test_create(self):
        org = Organization.objects.create(name="Test Org", slug="test-org")
        assert org.pk is not None
        assert org.is_active is True
        assert org.settings == {}
        assert str(org) == "Test Org"

    def test_add_member(self, org_a, user_b):
        membership = org_a.add_member(user_b, role=MembershipRole.MEMBER.value)
        assert membership.role == "member"
        assert membership.organization == org_a
        assert membership.user == user_b

    def test_add_member_updates_role(self, org_a, user_b):
        org_a.add_member(user_b, role="member")
        membership = org_a.add_member(user_b, role="admin")
        assert membership.role == "admin"

    def test_remove_member(self, org_a, user_b):
        org_a.add_member(user_b)
        assert org_a.remove_member(user_b) is True
        assert org_a.is_member(user_b) is False

    def test_remove_nonexistent_member(self, org_a, user_b):
        assert org_a.remove_member(user_b) is False

    def test_is_member(self, org_a, user_a, user_b):
        assert org_a.is_member(user_a) is True
        assert org_a.is_member(user_b) is False

    def test_get_member_role(self, org_a, user_a, user_b):
        assert org_a.get_member_role(user_a) == "owner"
        assert org_a.get_member_role(user_b) is None

    def test_get_members(self, org_a, user_a, user_b):
        org_a.add_member(user_b)
        members = org_a.get_members()
        assert members.count() == 2

    def test_get_teams(self, org_a, team_a):
        teams = org_a.get_teams()
        assert teams.count() == 1
        assert teams.first() == team_a

    def test_get_owners(self, org_a, user_a, user_b):
        org_a.add_member(user_b, role="admin")
        owners = org_a.get_owners()
        assert owners.count() == 1
        assert owners.first().user == user_a

    def test_get_admins(self, org_a, user_a, user_b):
        org_a.add_member(user_b, role="admin")
        admins = org_a.get_admins()
        assert admins.count() == 2  # owner + admin

    def test_slug_unique(self, org_a):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Organization.objects.create(name="Another", slug="org-alpha")


# ===========================================================================
# Team model
# ===========================================================================


class TestTeamModel:
    def test_create(self, org_a):
        team = Team.objects.create(
            organization=org_a, name="Engineering", slug="engineering"
        )
        assert team.pk is not None
        assert str(team) == "Org Alpha - Engineering"

    def test_unique_slug_per_org(self, org_a, team_a):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Team.objects.create(
                organization=org_a, name="Duplicate", slug="team-alpha"
            )

    def test_same_slug_different_org(self, org_a, org_b):
        Team.objects.create(organization=org_a, name="T1", slug="shared-slug")
        team2 = Team.objects.create(
            organization=org_b, name="T2", slug="shared-slug"
        )
        assert team2.pk is not None

    def test_add_member_requires_org_membership(self, org_a, team_a, user_b):
        with pytest.raises(ValueError, match="is not a member"):
            team_a.add_member(user_b)

    def test_add_member(self, org_a, team_a, user_a):
        tm = team_a.add_member(user_a)
        assert isinstance(tm, TeamMembership)
        assert tm.role == "member"
        assert team_a.is_member(user_a) is True

    def test_remove_member(self, org_a, team_a, user_a):
        team_a.add_member(user_a)
        assert team_a.remove_member(user_a) is True
        assert team_a.is_member(user_a) is False

    def test_remove_nonexistent_member(self, team_a, user_b):
        assert team_a.remove_member(user_b) is False

    def test_get_members(self, org_a, team_a, user_a):
        team_a.add_member(user_a)
        members = team_a.get_members()
        assert members.count() == 1

    def test_cascade_delete_org(self, org_a, team_a):
        team_id = team_a.pk
        org_a.delete()
        assert not Team.objects.filter(pk=team_id).exists()


# ===========================================================================
# Membership model
# ===========================================================================


class TestMembershipModel:
    def test_str(self, org_a, user_a):
        m = Membership.objects.get(organization=org_a, user=user_a)
        assert "owner" in str(m)

    def test_unique_together(self, org_a, user_a):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Membership.objects.create(
                organization=org_a, user=user_a, role="member"
            )

    def test_is_owner_property(self, org_a, user_a, user_b):
        owner_m = Membership.objects.get(organization=org_a, user=user_a)
        assert owner_m.is_owner is True

        org_a.add_member(user_b, role="member")
        member_m = Membership.objects.get(organization=org_a, user=user_b)
        assert member_m.is_owner is False

    def test_is_admin_property(self, org_a, user_a, user_b, user_c):
        owner_m = Membership.objects.get(organization=org_a, user=user_a)
        assert owner_m.is_admin is True

        org_a.add_member(user_b, role="admin")
        admin_m = Membership.objects.get(organization=org_a, user=user_b)
        assert admin_m.is_admin is True

        org_a.add_member(user_c, role="member")
        member_m = Membership.objects.get(organization=org_a, user=user_c)
        assert member_m.is_admin is False

    def test_permission_properties(self, org_a, user_a, user_b):
        owner_m = Membership.objects.get(organization=org_a, user=user_a)
        assert owner_m.can_invite is True
        assert owner_m.can_manage_members is True
        assert owner_m.can_manage_teams is True
        assert owner_m.can_delete_organization is True

        org_a.add_member(user_b, role="viewer")
        viewer_m = Membership.objects.get(organization=org_a, user=user_b)
        assert viewer_m.can_invite is False
        assert viewer_m.can_manage_members is False
        assert viewer_m.can_delete_organization is False

    def test_cascade_delete_org(self, org_a, user_a):
        org_a.delete()
        assert not Membership.objects.filter(user=user_a).exists()

    def test_cascade_delete_user(self, org_a, user_a):
        user_a.delete()
        assert not Membership.objects.filter(organization=org_a).exists()


# ===========================================================================
# Invitation model
# ===========================================================================


class TestInvitationModel:
    def test_create_invitation(self, org_a, user_a):
        inv = Invitation.objects.create(
            organization=org_a,
            email="new@example.com",
            invited_by=user_a,
        )
        assert inv.status == "pending"
        assert inv.token is not None
        assert len(inv.token) > 20
        assert inv.is_pending is True
        assert inv.can_accept is True
        assert str(inv) == "Invitation to Org Alpha for new@example.com"

    def test_accept_invitation(self, org_a, user_a, user_b):
        inv = Invitation.objects.create(
            organization=org_a,
            email=user_b.email,
            role="member",
            invited_by=user_a,
        )
        membership = inv.accept(user_b)
        assert membership.role == "member"
        assert membership.organization == org_a
        inv.refresh_from_db()
        assert inv.status == "accepted"
        assert inv.accepted_at is not None

    def test_accept_invitation_with_team(self, org_a, team_a, user_a, user_b):
        inv = Invitation.objects.create(
            organization=org_a,
            team=team_a,
            email=user_b.email,
            role="member",
            invited_by=user_a,
        )
        membership = inv.accept(user_b)
        assert membership is not None
        assert team_a.is_member(user_b) is True

    def test_accept_expired_invitation(self, org_a, user_a, user_b):
        inv = Invitation.objects.create(
            organization=org_a,
            email=user_b.email,
            invited_by=user_a,
            expires_at=timezone.now() - timedelta(days=1),
        )
        with pytest.raises(ValueError, match="expired"):
            inv.accept(user_b)
        inv.refresh_from_db()
        assert inv.status == "expired"

    def test_accept_already_accepted(self, org_a, user_a, user_b):
        inv = Invitation.objects.create(
            organization=org_a,
            email=user_b.email,
            invited_by=user_a,
        )
        inv.accept(user_b)
        with pytest.raises(ValueError, match="cannot be accepted"):
            inv.accept(user_b)

    def test_decline_invitation(self, org_a, user_a):
        inv = Invitation.objects.create(
            organization=org_a,
            email="new@example.com",
            invited_by=user_a,
        )
        inv.decline()
        assert inv.status == "declined"

    def test_decline_non_pending(self, org_a, user_a, user_b):
        inv = Invitation.objects.create(
            organization=org_a,
            email=user_b.email,
            invited_by=user_a,
        )
        inv.accept(user_b)
        with pytest.raises(ValueError, match="Cannot decline"):
            inv.decline()

    def test_revoke_invitation(self, org_a, user_a):
        inv = Invitation.objects.create(
            organization=org_a,
            email="new@example.com",
            invited_by=user_a,
        )
        inv.revoke()
        assert inv.status == "revoked"

    def test_revoke_non_pending(self, org_a, user_a):
        inv = Invitation.objects.create(
            organization=org_a,
            email="new@example.com",
            invited_by=user_a,
        )
        inv.decline()
        with pytest.raises(ValueError, match="Cannot revoke"):
            inv.revoke()

    def test_resend_invitation(self, org_a, user_a):
        inv = Invitation.objects.create(
            organization=org_a,
            email="new@example.com",
            invited_by=user_a,
        )
        old_token = inv.token
        inv.resend()
        assert inv.token != old_token
        assert inv.status == "pending"
        assert inv.expires_at > timezone.now()

    def test_is_expired_property(self, org_a, user_a):
        inv = Invitation.objects.create(
            organization=org_a,
            email="new@example.com",
            invited_by=user_a,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert inv.is_expired is True
        assert inv.is_pending is False
        assert inv.can_accept is False


class TestInvitationTokenAndExpiry:
    def test_generate_token_unique(self):
        tokens = {generate_invitation_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_get_invitation_expiry_default(self):
        expiry = get_invitation_expiry()
        assert expiry > timezone.now()
        # roughly 7 days (delta.days can be 6 due to sub-second timing)
        delta = expiry - timezone.now()
        assert 5 < delta.total_seconds() / 86400 < 8

    def test_get_invitation_expiry_custom(self, settings):
        settings.INVITATION_EXPIRY_DAYS = 14
        expiry = get_invitation_expiry()
        delta = expiry - timezone.now()
        assert 13 < delta.total_seconds() / 86400 < 15


# ===========================================================================
# Tenant context (contextvars)
# ===========================================================================


class TestTenantContext:
    def test_set_get_clear(self, org_a):
        assert get_current_tenant() is None
        set_current_tenant(org_a)
        assert get_current_tenant() == org_a
        assert get_current_organization() == org_a
        clear_current_tenant()
        assert get_current_tenant() is None
        assert get_current_organization() is None

    def test_set_none(self):
        set_current_tenant(None)
        assert get_current_tenant() is None


# ===========================================================================
# TenantMiddleware (sync)
# ===========================================================================


class TestTenantMiddlewareSync:
    def _make_middleware(self, get_response=None):
        if get_response is None:
            get_response = lambda request: HttpResponse("ok")
        return TenantMiddleware(get_response)

    def test_resolve_from_header_id(self, rf, org_a):
        mw = self._make_middleware()
        request = rf.get("/api/test/", HTTP_X_ORGANIZATION_ID=str(org_a.id))
        response = mw(request)
        assert request.organization == org_a
        assert request.tenant == org_a
        assert response.status_code == 200

    def test_resolve_from_header_slug(self, rf, org_a):
        mw = self._make_middleware()
        request = rf.get("/api/test/", HTTP_X_ORGANIZATION_SLUG=org_a.slug)
        response = mw(request)
        assert request.organization == org_a

    def test_resolve_from_session(self, rf, org_a):
        mw = self._make_middleware()
        request = rf.get("/api/test/")
        request.session = {"current_organization_id": str(org_a.id)}
        response = mw(request)
        assert request.organization == org_a

    def test_resolve_from_user_membership(self, rf, org_a, user_a):
        mw = self._make_middleware()
        request = rf.get("/api/test/")
        request.user = user_a
        response = mw(request)
        assert request.organization == org_a

    def test_no_tenant_resolved(self, rf):
        mw = self._make_middleware()
        request = rf.get("/api/test/")
        request.user = AnonymousUser()
        response = mw(request)
        assert request.organization is None
        assert response.status_code == 200

    def test_required_path_no_tenant(self, rf, settings):
        settings.TENANT_REQUIRED_PATHS = ["/api/"]
        settings.TENANT_EXEMPT_PATHS = []
        mw = TenantMiddleware(lambda r: HttpResponse("ok"))
        request = rf.get("/api/test/")
        request.user = AnonymousUser()
        response = mw(request)
        assert response.status_code == 400

    def test_exempt_path_no_tenant(self, rf, settings):
        settings.TENANT_REQUIRED_PATHS = ["/"]
        settings.TENANT_EXEMPT_PATHS = ["/auth/"]
        mw = TenantMiddleware(lambda r: HttpResponse("ok"))
        request = rf.get("/auth/login/")
        request.user = AnonymousUser()
        response = mw(request)
        assert response.status_code == 200

    def test_inactive_org_not_resolved(self, rf, org_a):
        org_a.is_active = False
        org_a.save()
        mw = self._make_middleware()
        request = rf.get("/api/test/", HTTP_X_ORGANIZATION_ID=str(org_a.id))
        mw(request)
        assert request.organization is None

    def test_clears_context_after_request(self, rf, org_a):
        mw = self._make_middleware()
        request = rf.get("/api/test/", HTTP_X_ORGANIZATION_ID=str(org_a.id))
        mw(request)
        assert get_current_tenant() is None

    def test_invalid_uuid_header(self, rf):
        mw = self._make_middleware()
        request = rf.get("/api/test/", HTTP_X_ORGANIZATION_ID="not-a-uuid")
        request.user = AnonymousUser()
        mw(request)
        assert request.organization is None


# ===========================================================================
# TenantMiddlewareAsync
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestTenantMiddlewareAsync:
    async def test_resolve_from_header_id(self, rf, org_a):
        async def get_response(request):
            return HttpResponse("ok")

        mw = TenantMiddlewareAsync(get_response)
        request = rf.get("/api/test/", HTTP_X_ORGANIZATION_ID=str(org_a.id))
        request.user = AnonymousUser()
        response = await mw(request)
        assert request.organization == org_a
        assert response.status_code == 200

    async def test_resolve_from_header_slug(self, rf, org_a):
        async def get_response(request):
            return HttpResponse("ok")

        mw = TenantMiddlewareAsync(get_response)
        request = rf.get("/api/test/", HTTP_X_ORGANIZATION_SLUG=org_a.slug)
        request.user = AnonymousUser()
        response = await mw(request)
        assert request.organization == org_a

    async def test_resolve_from_user(self, rf, org_a, user_a):
        async def get_response(request):
            return HttpResponse("ok")

        mw = TenantMiddlewareAsync(get_response)
        request = rf.get("/api/test/")
        request.user = user_a
        response = await mw(request)
        assert request.organization == org_a

    async def test_no_tenant(self, rf):
        async def get_response(request):
            return HttpResponse("ok")

        mw = TenantMiddlewareAsync(get_response)
        request = rf.get("/api/test/")
        request.user = AnonymousUser()
        response = await mw(request)
        assert request.organization is None

    async def test_required_path_no_tenant(self, rf, settings):
        settings.TENANT_REQUIRED_PATHS = ["/api/"]
        settings.TENANT_EXEMPT_PATHS = []

        async def get_response(request):
            return HttpResponse("ok")

        mw = TenantMiddlewareAsync(get_response)
        request = rf.get("/api/test/")
        request.user = AnonymousUser()
        response = await mw(request)
        assert response.status_code == 400

    async def test_clears_context_after_request(self, rf, org_a):
        async def get_response(request):
            return HttpResponse("ok")

        mw = TenantMiddlewareAsync(get_response)
        request = rf.get("/api/test/", HTTP_X_ORGANIZATION_ID=str(org_a.id))
        request.user = AnonymousUser()
        await mw(request)
        assert get_current_tenant() is None


# ===========================================================================
# Decorators (sync)
# ===========================================================================


class TestRequiresOrganization:
    def test_no_org_returns_400(self, rf):
        @requires_organization
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.organization = None
        clear_current_tenant()
        response = view(request)
        assert response.status_code == 400

    def test_with_org_passes(self, rf, org_a):
        @requires_organization
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()


class TestRequiresOrgMembership:
    def test_unauthenticated_returns_401(self, rf):
        @requires_org_membership
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = AnonymousUser()
        response = view(request)
        assert response.status_code == 401

    def test_no_org_returns_400(self, rf, user_a):
        @requires_org_membership
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        request.organization = None
        clear_current_tenant()
        response = view(request)
        assert response.status_code == 400

    def test_not_member_returns_403(self, rf, org_a, user_b):
        @requires_org_membership
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 403
        clear_current_tenant()

    def test_member_passes(self, rf, org_a, user_a):
        @requires_org_membership
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()


class TestRequiresOrgRole:
    def test_wrong_role_returns_403(self, rf, org_a, user_b):
        org_a.add_member(user_b, role="viewer")

        @requires_org_role("admin")
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 403
        clear_current_tenant()

    def test_correct_role_passes(self, rf, org_a, user_a):
        @requires_org_role("owner")
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()

    def test_multiple_roles(self, rf, org_a, user_b):
        org_a.add_member(user_b, role="admin")

        @requires_org_role(["admin", "owner"])
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()


class TestRequiresOrgAdmin:
    def test_member_returns_403(self, rf, org_a, user_b):
        org_a.add_member(user_b, role="member")

        @requires_org_admin
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 403
        clear_current_tenant()

    def test_admin_passes(self, rf, org_a, user_b):
        org_a.add_member(user_b, role="admin")

        @requires_org_admin
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()

    def test_owner_passes(self, rf, org_a, user_a):
        @requires_org_admin
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()


class TestRequiresOrgOwner:
    def test_admin_returns_403(self, rf, org_a, user_b):
        org_a.add_member(user_b, role="admin")

        @requires_org_owner
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 403
        clear_current_tenant()

    def test_owner_passes(self, rf, org_a, user_a):
        @requires_org_owner
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()


class TestRequiresMinOrgRole:
    def test_viewer_below_member(self, rf, org_a, user_b):
        org_a.add_member(user_b, role="viewer")

        @requires_min_org_role("member")
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 403
        clear_current_tenant()

    def test_member_meets_member(self, rf, org_a, user_b):
        org_a.add_member(user_b, role="member")

        @requires_min_org_role("member")
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()

    def test_owner_meets_any_min(self, rf, org_a, user_a):
        @requires_min_org_role("viewer")
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        request.organization = org_a
        set_current_tenant(org_a)
        response = view(request)
        assert response.status_code == 200
        clear_current_tenant()


class TestRequiresTeamMembership:
    def test_no_team_id_returns_400(self, rf, user_a):
        @requires_team_membership("team_id")
        def view(request, **kwargs):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        response = view(request)
        assert response.status_code == 400

    def test_nonexistent_team_returns_404(self, rf, user_a):
        @requires_team_membership("team_id")
        def view(request, **kwargs):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        response = view(request, team_id=uuid.uuid4())
        assert response.status_code == 404

    def test_not_team_member_returns_403(self, rf, org_a, team_a, user_b):
        @requires_team_membership("team_id")
        def view(request, **kwargs):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        response = view(request, team_id=team_a.pk)
        assert response.status_code == 403

    def test_team_member_passes(self, rf, org_a, team_a, user_a):
        team_a.add_member(user_a)

        @requires_team_membership("team_id")
        def view(request, **kwargs):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_a
        response = view(request, team_id=team_a.pk)
        assert response.status_code == 200


# ===========================================================================
# Async decorator variants
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestAsyncDecorators:
    async def test_requires_organization_async(self, rf, org_a):
        @requires_organization
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.organization = None
        clear_current_tenant()
        response = await view(request)
        assert response.status_code == 400

        request.organization = org_a
        set_current_tenant(org_a)
        response = await view(request)
        assert response.status_code == 200
        clear_current_tenant()

    async def test_requires_org_membership_async(self, rf, org_a, user_a, user_b):
        @requires_org_membership
        async def view(request):
            return HttpResponse("ok")

        # not member
        request = rf.get("/")
        request.user = user_b
        request.organization = org_a
        set_current_tenant(org_a)
        response = await view(request)
        assert response.status_code == 403

        # member
        request.user = user_a
        response = await view(request)
        assert response.status_code == 200
        clear_current_tenant()

    async def test_requires_org_role_async(self, rf, org_a, user_a, user_b):
        await sync_to_async(org_a.add_member)(user_b, role="viewer")

        @requires_org_role("owner")
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.organization = org_a
        set_current_tenant(org_a)

        request.user = user_b
        response = await view(request)
        assert response.status_code == 403

        request.user = user_a
        response = await view(request)
        assert response.status_code == 200
        clear_current_tenant()

    async def test_requires_min_org_role_async(self, rf, org_a, user_a, user_b):
        await sync_to_async(org_a.add_member)(user_b, role="viewer")

        @requires_min_org_role("admin")
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.organization = org_a
        set_current_tenant(org_a)

        request.user = user_b
        response = await view(request)
        assert response.status_code == 403

        request.user = user_a
        response = await view(request)
        assert response.status_code == 200
        clear_current_tenant()

    async def test_requires_team_membership_async(
        self, rf, org_a, team_a, user_a, user_b
    ):
        await sync_to_async(team_a.add_member)(user_a)

        @requires_team_membership("team_id")
        async def view(request, **kwargs):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user_b
        response = await view(request, team_id=team_a.pk)
        assert response.status_code == 403

        request.user = user_a
        response = await view(request, team_id=team_a.pk)
        assert response.status_code == 200


# ===========================================================================
# Utility functions (sync)
# ===========================================================================


class TestUtilsSync:
    def test_get_user_organizations(self, org_a, org_b, user_a, user_b):
        org_b.add_member(user_a, role="member")
        orgs = get_user_organizations(user_a)
        assert orgs.count() == 2

    def test_get_user_organizations_excludes_inactive(self, org_a, user_a):
        org_a.is_active = False
        org_a.save()
        orgs = get_user_organizations(user_a)
        assert orgs.count() == 0

    def test_get_user_teams(self, org_a, team_a, user_a):
        team_a.add_member(user_a)
        teams = get_user_teams(user_a)
        assert teams.count() == 1

    def test_get_user_teams_filtered_by_org(
        self, org_a, org_b, user_a, user_b, team_a
    ):
        team_a.add_member(user_a)
        # user_a is in org_a's team; create team in org_b
        org_b.add_member(user_a, role="member")
        team_b = Team.objects.create(
            organization=org_b, name="Team Beta", slug="team-beta"
        )
        team_b.add_member(user_a)

        teams = get_user_teams(user_a, organization=org_a)
        assert teams.count() == 1
        assert teams.first() == team_a

    def test_get_organization_members(self, org_a, user_a, user_b):
        org_a.add_member(user_b, role="member")
        members = get_organization_members(org_a)
        assert members.count() == 2

    def test_get_organization_members_filtered_by_role(self, org_a, user_a, user_b):
        org_a.add_member(user_b, role="member")
        owners = get_organization_members(org_a, role="owner")
        assert owners.count() == 1

    def test_get_team_members(self, org_a, team_a, user_a):
        team_a.add_member(user_a)
        members = get_team_members(team_a)
        assert members.count() == 1

    def test_user_is_org_admin(self, org_a, user_a, user_b, user_c):
        org_a.add_member(user_b, role="admin")
        org_a.add_member(user_c, role="member")
        assert user_is_org_admin(user_a, org_a) is True  # owner
        assert user_is_org_admin(user_b, org_a) is True  # admin
        assert user_is_org_admin(user_c, org_a) is False  # member

    def test_user_is_org_owner(self, org_a, user_a, user_b):
        org_a.add_member(user_b, role="admin")
        assert user_is_org_owner(user_a, org_a) is True
        assert user_is_org_owner(user_b, org_a) is False

    def test_user_can_manage_team_as_org_admin(self, org_a, team_a, user_a):
        assert user_can_manage_team(user_a, team_a) is True

    def test_user_can_manage_team_as_team_admin(self, org_a, team_a, user_b):
        org_a.add_member(user_b, role="member")
        team_a.add_member(user_b, role="admin")
        assert user_can_manage_team(user_b, team_a) is True

    def test_user_cannot_manage_team_as_member(self, org_a, team_a, user_b):
        org_a.add_member(user_b, role="member")
        team_a.add_member(user_b, role="member")
        assert user_can_manage_team(user_b, team_a) is False

    def test_user_has_org_permission(self, org_a, user_a, user_b, user_c):
        org_a.add_member(user_b, role="admin")
        org_a.add_member(user_c, role="viewer")
        assert user_has_org_permission(user_a, org_a, "admin") is True
        assert user_has_org_permission(user_b, org_a, "admin") is True
        assert user_has_org_permission(user_c, org_a, "admin") is False
        assert user_has_org_permission(user_c, org_a, "viewer") is True

    def test_user_has_org_permission_nonmember(self, org_a, user_b):
        assert user_has_org_permission(user_b, org_a, "viewer") is False


class TestCreateOrganizationWithOwner:
    def test_creates_org_and_membership(self, user_a):
        org = create_organization_with_owner(
            name="New Org", slug="new-org", owner=user_a
        )
        assert org.pk is not None
        assert org.is_member(user_a) is True
        assert org.get_member_role(user_a) == "owner"

    def test_with_extra_fields(self, user_a):
        org = create_organization_with_owner(
            name="Custom",
            slug="custom",
            owner=user_a,
            description="A custom org",
            settings={"plan": "pro"},
        )
        assert org.description == "A custom org"
        assert org.settings == {"plan": "pro"}


class TestCreateTeamWithMembers:
    def test_creates_team_with_members(self, org_a, user_a, user_b):
        org_a.add_member(user_b, role="member")
        team = create_team_with_members(
            organization=org_a,
            name="Dev Team",
            slug="dev-team",
            members=[user_a, user_b],
        )
        assert team.pk is not None
        assert team.is_member(user_a) is True
        assert team.is_member(user_b) is True

    def test_skips_nonmember_users(self, org_a, user_a, user_b):
        # user_b not in org, should be skipped
        team = create_team_with_members(
            organization=org_a,
            name="Dev Team",
            slug="dev-team-2",
            members=[user_a, user_b],
        )
        assert team.is_member(user_a) is True
        assert team.is_member(user_b) is False

    def test_no_members(self, org_a):
        team = create_team_with_members(
            organization=org_a,
            name="Empty Team",
            slug="empty-team",
        )
        assert team.pk is not None


class TestTransferOwnership:
    def test_transfer(self, org_a, user_a, user_b):
        org_a.add_member(user_b, role="admin")
        result = transfer_ownership(org_a, user_a, user_b)
        assert result is True
        assert org_a.get_member_role(user_b) == "owner"
        assert org_a.get_member_role(user_a) == "admin"

    def test_transfer_non_owner_raises(self, org_a, user_a, user_b):
        org_a.add_member(user_b, role="admin")
        with pytest.raises(ValueError, match="not the owner"):
            transfer_ownership(org_a, user_b, user_a)

    def test_transfer_to_non_member_raises(self, org_a, user_a, user_b):
        with pytest.raises(ValueError, match="must be a member"):
            transfer_ownership(org_a, user_a, user_b)


# ===========================================================================
# Async utility functions
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestUtilsAsync:
    async def test_acreate_organization_with_owner(self, user_a):
        from django_matt.multitenancy.utils import acreate_organization_with_owner

        org = await acreate_organization_with_owner(
            name="Async Org", slug="async-org", owner=user_a
        )
        assert org.pk is not None
        exists = await Membership.objects.filter(
            organization=org, user=user_a, role="owner"
        ).aexists()
        assert exists is True

    async def test_auser_is_org_admin(self, org_a, user_a, user_b):
        from django_matt.multitenancy.utils import auser_is_org_admin

        assert await auser_is_org_admin(user_a, org_a) is True
        assert await auser_is_org_admin(user_b, org_a) is False

    async def test_auser_is_org_owner(self, org_a, user_a, user_b):
        from django_matt.multitenancy.utils import auser_is_org_owner

        assert await auser_is_org_owner(user_a, org_a) is True
        await sync_to_async(org_a.add_member)(user_b, role="admin")
        assert await auser_is_org_owner(user_b, org_a) is False

    async def test_auser_can_manage_team(self, org_a, team_a, user_a, user_b):
        from django_matt.multitenancy.utils import auser_can_manage_team

        assert await auser_can_manage_team(user_a, team_a) is True
        await sync_to_async(org_a.add_member)(user_b, role="member")
        assert await auser_can_manage_team(user_b, team_a) is False


# ===========================================================================
# Cross-tenant data isolation
# ===========================================================================


class TestCrossTenantIsolation:
    def test_org_members_isolated(self, org_a, org_b, user_a, user_b):
        assert org_a.is_member(user_a) is True
        assert org_a.is_member(user_b) is False
        assert org_b.is_member(user_b) is True
        assert org_b.is_member(user_a) is False

    def test_teams_isolated_by_org(self, org_a, org_b):
        Team.objects.create(organization=org_a, name="TA", slug="t1")
        Team.objects.create(organization=org_b, name="TB", slug="t1")
        assert org_a.get_teams().count() == 1
        assert org_b.get_teams().count() == 1
        assert org_a.get_teams().first().name == "TA"

    def test_memberships_isolated(self, org_a, org_b, user_a, user_b, user_c):
        org_a.add_member(user_c, role="member")
        org_b.add_member(user_c, role="admin")
        assert org_a.get_member_role(user_c) == "member"
        assert org_b.get_member_role(user_c) == "admin"

    def test_invitations_isolated(self, org_a, org_b, user_a, user_b):
        Invitation.objects.create(
            organization=org_a, email="x@example.com", invited_by=user_a
        )
        Invitation.objects.create(
            organization=org_b, email="x@example.com", invited_by=user_b
        )
        assert Invitation.objects.filter(organization=org_a).count() == 1
        assert Invitation.objects.filter(organization=org_b).count() == 1

    def test_team_memberships_isolated(self, org_a, org_b, user_a, user_b):
        team_a = Team.objects.create(organization=org_a, name="TA", slug="ta")
        team_b = Team.objects.create(organization=org_b, name="TB", slug="tb")
        team_a.add_member(user_a)
        team_b.add_member(user_b)
        assert team_a.is_member(user_a) is True
        assert team_a.is_member(user_b) is False
        assert team_b.is_member(user_b) is True
        assert team_b.is_member(user_a) is False


# ===========================================================================
# Schema validation
# ===========================================================================


class TestSchemas:
    def test_organization_create_valid(self):
        schema = OrganizationCreate(
            name="Test", slug="test-org", description="desc"
        )
        assert schema.name == "Test"
        assert schema.slug == "test-org"

    def test_organization_create_invalid_slug(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OrganizationCreate(name="Test", slug="Invalid Slug!")

    def test_organization_update_partial(self):
        schema = OrganizationUpdate(name="Updated")
        data = schema.model_dump(exclude_unset=True)
        assert "name" in data
        assert "slug" not in data

    def test_organization_response_from_model(self, org_a):
        response = OrganizationResponse.model_validate(org_a)
        assert response.id == org_a.id
        assert response.name == org_a.name
        assert response.slug == org_a.slug

    def test_team_create_valid(self):
        schema = TeamCreate(name="Dev", slug="dev")
        assert schema.name == "Dev"

    def test_team_create_invalid_slug(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TeamCreate(name="Dev", slug="BAD SLUG")

    def test_membership_update_valid(self):
        schema = MembershipUpdate(role="admin")
        assert schema.role == "admin"

    def test_membership_update_invalid_role(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MembershipUpdate(role="superuser")

    def test_invitation_create_valid(self):
        schema = InvitationCreate(email="test@example.com", role="member")
        assert schema.email == "test@example.com"

    def test_invitation_create_invalid_email(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            InvitationCreate(email="not-an-email", role="member")

    def test_tenant_context_properties(self):
        ctx = TenantContext(
            organization_id=uuid.uuid4(), organization_slug="test"
        )
        assert ctx.has_organization is True
        assert ctx.has_team is False

        empty = TenantContext()
        assert empty.has_organization is False


# ===========================================================================
# Invitation email config
# ===========================================================================


class TestInvitationEmailConfig:
    def test_default_config(self):
        from django_matt.multitenancy.emails import InvitationEmailConfig

        config = InvitationEmailConfig()
        assert "{organization}" in config.email_subject
        assert config.accept_path == "/invitations/accept"

    def test_custom_config(self, settings):
        settings.DJANGO_MATT_MULTITENANCY = {
            "INVITATION_EMAIL_SUBJECT": "Join {organization} now!",
            "INVITATION_BASE_URL": "https://app.example.com",
            "INVITATION_ACCEPT_PATH": "/join",
        }
        from django_matt.multitenancy.emails import InvitationEmailConfig

        config = InvitationEmailConfig()
        assert config.email_subject == "Join {organization} now!"
        assert config.base_url == "https://app.example.com"
        assert config.accept_path == "/join"


# ===========================================================================
# TenantRequiredMixin
# ===========================================================================


class TestTenantRequiredMixin:
    def test_get_organization(self, rf, org_a):
        from django_matt.multitenancy.middleware import TenantRequiredMixin

        mixin = TenantRequiredMixin()
        mixin.request = rf.get("/")
        mixin.request.organization = org_a
        assert mixin.get_organization() == org_a
        assert mixin.get_tenant() == org_a

    def test_get_organization_raises_without_context(self, rf):
        from django_matt.multitenancy.middleware import TenantRequiredMixin

        mixin = TenantRequiredMixin()
        mixin.request = rf.get("/")
        mixin.request.organization = None
        with pytest.raises(ValueError, match="No organization context"):
            mixin.get_organization()

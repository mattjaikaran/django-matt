import pytest
from django.test import Client

from apps.organizations.models import Membership, MembershipRole, Organization
from apps.projects.models import Project
from apps.users.models import User


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@example.com",
        username="testuser",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin@example.com",
        username="admin",
        password="adminpass123",
    )


@pytest.fixture
def organization(db):
    return Organization.objects.create(
        name="Test Org",
        slug="test-org",
    )


@pytest.fixture
def membership(user, organization):
    return Membership.objects.create(
        user=user,
        organization=organization,
        role=MembershipRole.OWNER.value,
    )


@pytest.fixture
def project(organization):
    return Project.objects.create(
        organization=organization,
        name="Test Project",
        slug="test-project",
        environment="development",
    )


@pytest.fixture
def auth_headers(client, user):
    response = client.post(
        "/api/auth/login",
        data={"email": user.email, "password": "testpass123"},
        content_type="application/json",
    )
    token = response.json()["access_token"]
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

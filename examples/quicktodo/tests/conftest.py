import pytest
from django.test import Client

from apps.organizations.models import Membership, MembershipRole, Organization
from apps.todos.models import Todo, TodoList
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
def other_user(db):
    return User.objects.create_user(
        email="other@example.com",
        username="otheruser",
        password="testpass123",
    )


@pytest.fixture
def organization(db):
    return Organization.objects.create(
        name="Test Org",
        slug="test-org",
        description="A test organization",
    )


@pytest.fixture
def membership(user, organization):
    return Membership.objects.create(
        user=user,
        organization=organization,
        role=MembershipRole.OWNER.value,
    )


@pytest.fixture
def member_membership(other_user, organization):
    return Membership.objects.create(
        user=other_user,
        organization=organization,
        role=MembershipRole.MEMBER.value,
    )


@pytest.fixture
def todo_list(organization, user, membership):
    return TodoList.objects.create(
        organization=organization,
        name="Test List",
        description="A test todo list",
        created_by=user,
    )


@pytest.fixture
def todo(todo_list, user):
    return Todo.objects.create(
        todo_list=todo_list,
        title="Test Todo",
        description="A test todo item",
        status="pending",
        priority="medium",
        assignee=user,
    )


@pytest.fixture
def auth_headers(client, user):
    """Get auth headers by logging in."""
    response = client.post(
        "/api/auth/login",
        data={"email": user.email, "password": "testpass123"},
        content_type="application/json",
    )
    token = response.json()["access_token"]
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

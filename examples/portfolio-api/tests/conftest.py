import pytest
from django.test import Client

from apps.contact.models import ContactMessage
from apps.experience.models import Experience
from apps.projects.models import Project
from apps.skills.models import Skill
from apps.users.models import User


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",
        name="Admin User",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def auth_headers(client, admin_user):
    response = client.post(
        "/api/auth/login",
        data={"email": admin_user.email, "password": "adminpass123"},
        content_type="application/json",
    )
    token = response.json()["access_token"]
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def sample_project(db):
    return Project.objects.create(
        title="Test Project",
        slug="test-project",
        description="A test project",
        long_description="Long description here",
        tech_stack=["Python", "Django"],
        featured=True,
        order=1,
        is_published=True,
    )


@pytest.fixture
def sample_skill(db):
    return Skill.objects.create(
        name="Python",
        category="backend",
        level=5,
        icon="python",
        order=1,
    )


@pytest.fixture
def sample_experience(db):
    return Experience.objects.create(
        company="Test Corp",
        role="Senior Engineer",
        location="Remote",
        start_date="2022-01-01",
        is_current=True,
        description="Built things.",
        tech_used=["Python", "Django"],
        order=1,
    )


@pytest.fixture
def sample_message(db):
    return ContactMessage.objects.create(
        name="John Doe",
        email="john@example.com",
        subject="Hello",
        message="Just saying hi!",
    )
